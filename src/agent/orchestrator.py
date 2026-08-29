"""Code-first orchestrator over mechanism-specialist monitors.

Independent specialists overlap on a shared wall-clock deadline via
``asyncio.wait`` + ``asyncio.to_thread(run_agent)``. They do not talk to
each other. Findings are never merged into a crash score.
"""

from __future__ import annotations

import asyncio
import copy
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from src.agent.loop import (
    MAX_STEPS,
    OVERALL_DEADLINE_SECONDS,
    AgentRunResult,
    prepare_risk_snapshot,
    run_agent,
)
from src.agent.models import OrchestratorTrace, ToolObservation
from src.agent.planner import Planner
from src.agent.report import build_combined_pm_note, sanitize_text
from src.agent.specialists import BY_NAME, SCHEDULE, select_specialists
from src.agent_prompts import no_meaningful_risk_signal
from src.mvp.config import HISTORICAL_EXAMPLE_DATE
from src.tools.registry import ToolRegistry
from src.utils.io import DEFAULT_PROCESSED_DIR

Monotonic = Callable[[], float]


@dataclass(frozen=True)
class OrchestratedRunResult:
    run_id: str
    as_of_date: str
    stop_reason: str
    report: str
    trace: OrchestratorTrace
    risk_state: dict[str, Any]
    spawned: tuple[str, ...]
    specialist_results: dict[str, AgentRunResult]
    observations: tuple[ToolObservation, ...]
    routing: dict[str, Any]


@dataclass(frozen=True)
class _Job:
    """Shared inputs for every specialist on this investigation."""

    as_of_date: str
    max_steps: int
    deadline: float
    risk_state: Mapping[str, Any]
    prior_state: Mapping[str, Any] | None
    planners: Mapping[str, Planner]
    registries: Mapping[str, ToolRegistry]
    use_llm: bool | None
    monotonic: Monotonic
    processed_dir: Any
    run_id: str


def _run_sync(factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(factory())).result()


def run_orchestrated_investigation(*args, **kwargs) -> OrchestratedRunResult:
    """Sync CLI/test entry around ``run_orchestrated_investigation_async``."""

    return _run_sync(lambda: run_orchestrated_investigation_async(*args, **kwargs))


async def run_orchestrated_investigation_async(
    as_of_date: str = HISTORICAL_EXAMPLE_DATE,
    max_steps: int = MAX_STEPS,
    *,
    overall_deadline_seconds: float = OVERALL_DEADLINE_SECONDS,
    risk_state: Mapping[str, Any] | None = None,
    prior_state: Mapping[str, Any] | None = None,
    mvp_result: Any | None = None,
    planners: Mapping[str, Planner] | None = None,
    registries: Mapping[str, ToolRegistry] | None = None,
    use_llm: bool | None = None,
    monotonic: Monotonic = time.monotonic,
    processed_dir=DEFAULT_PROCESSED_DIR,
) -> OrchestratedRunResult:
    frozen, _, date, cutoff = prepare_risk_snapshot(
        as_of_date, risk_state=risk_state, mvp_result=mvp_result
    )
    run_id = uuid.uuid4().hex[:12]
    spawned = select_specialists(frozen)
    quiet = no_meaningful_risk_signal(frozen)
    deadline = float(overall_deadline_seconds)
    routing = {
        "quiet": quiet,
        "spawned": list(spawned),
        "schedule": SCHEDULE,
        "deadline_seconds": deadline,
    }
    job = _Job(
        as_of_date=date,
        max_steps=max_steps,
        deadline=deadline,
        risk_state=frozen,
        prior_state=prior_state,
        planners=planners or {},
        registries=registries or {},
        use_llm=use_llm,
        monotonic=monotonic,
        processed_dir=processed_dir,
        run_id=run_id,
    )
    specialist_results, spawn_decisions = await _gather(spawned, job)
    stop_reason = _combined_stop(spawned, specialist_results, quiet)
    report, calibrated = build_combined_pm_note(
        risk_state=frozen,
        spawned=spawned,
        specialist_results=specialist_results,
        stop_reason=stop_reason,
    )
    observations = tuple(
        item
        for name in spawned
        if name in specialist_results
        for item in specialist_results[name].observations
    )
    trace = OrchestratorTrace(
        run_id=run_id,
        as_of_date=date,
        assessment_cutoff=cutoff,
        spawned=list(spawned),
        routing=routing,
        decisions=[
            {
                "actor": "orchestrator",
                "action": "spawn" if spawned else "skip",
                "specialists": list(spawned),
                "reason": "NO_INVESTIGATION_NEEDED" if quiet else "deterministic_flags",
                "schedule": SCHEDULE,
            },
            *spawn_decisions,
        ],
        specialist_traces={name: specialist_results[name].trace for name in specialist_results},
        errors=[
            error
            for name in spawned
            if name in specialist_results
            for error in specialist_results[name].state.errors
        ],
        stop_reason=stop_reason,
        final_assessment=sanitize_text(calibrated.get("current_read")),
        calibrated=calibrated,
        report=report,
    )
    return OrchestratedRunResult(
        run_id=run_id,
        as_of_date=date,
        stop_reason=stop_reason,
        report=report,
        trace=trace,
        risk_state=copy.deepcopy(frozen),
        spawned=spawned,
        specialist_results=specialist_results,
        observations=observations,
        routing=routing,
    )


async def _gather(spawned: tuple[str, ...], job: _Job) -> tuple[dict[str, AgentRunResult], list[dict[str, Any]]]:
    if not spawned:
        return {}, []
    tasks = {
        name: asyncio.create_task(asyncio.to_thread(_run_specialist, name, job), name=f"specialist-{name}")
        for name in spawned
    }
    _done, pending = await asyncio.wait(set(tasks.values()), timeout=max(0.01, job.deadline))
    results: dict[str, AgentRunResult] = {}
    extra: list[dict[str, Any]] = []
    for name in spawned:
        task = tasks[name]
        if task in pending:
            task.cancel()
            extra.append({"actor": "orchestrator", "action": "skip", "specialist": name, "reason": "DEADLINE_EXCEEDED"})
            continue
        try:
            result = task.result()
        except Exception as exc:  # noqa: BLE001 - isolate one specialist
            extra.append({"actor": name, "action": "failed", "reason": "UNRESOLVABLE", "error": str(exc)})
            continue
        extra.append(
            {
                "actor": name,
                "action": "completed",
                "stop_reason": result.stop_reason,
                "steps": result.state.step,
                "tools": [item.name for item in result.observations],
            }
        )
        results[name] = result
    return results, extra


def _run_specialist(name: str, job: _Job) -> AgentRunResult:
    spec = BY_NAME[name]
    tools = job.registries.get(name) or spec.registry()
    return run_agent(
        as_of_date=job.as_of_date,
        max_steps=job.max_steps,
        overall_deadline_seconds=job.deadline,
        risk_state=job.risk_state,
        prior_state=job.prior_state,
        planner=job.planners.get(name),
        registry=tools,
        use_llm=job.use_llm,
        focus=spec.focus,
        monotonic=job.monotonic,
        processed_dir=job.processed_dir,
        run_id=f"{job.run_id}-{name[:3]}",
    )


def _combined_stop(spawned: tuple[str, ...], results: Mapping[str, AgentRunResult], quiet: bool) -> str:
    if not spawned:
        return "NO_INVESTIGATION_NEEDED" if quiet else "UNRESOLVABLE"
    reasons = [results[name].stop_reason for name in spawned if name in results]
    if not reasons:
        return "DEADLINE_EXCEEDED"
    for preferred in ("ESCALATED", "MALFORMED_PLANNER_OUTPUT", "PLANNER_TIMEOUT"):
        if preferred in reasons:
            return preferred
    unique = list(dict.fromkeys(reasons))
    return "EVIDENCE_SUFFICIENT" if "EVIDENCE_SUFFICIENT" in unique else unique[0]
