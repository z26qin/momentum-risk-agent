"""Code-first routing over independent mechanism specialists."""

from __future__ import annotations

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable, Mapping

from src.agent.loop import (
    MAX_STEPS,
    OVERALL_DEADLINE_SECONDS,
    AgentRunResult,
    run_agent,
)
from src.agent.models import OrchestratorTrace, ToolObservation
from src.agent.planner import Planner
from src.agent.signals import no_meaningful_risk_signal
from src.agent.specialists import BY_NAME, SCHEDULE, select_specialists
from src.agent.synthesis import build_combined_pm_note, sanitize_text
from src.agent.tracing import (
    langsmith_extra_kwargs,
    orchestrator_inputs,
    orchestrator_outputs,
    parent_run,
    traceable,
)
from src.risk_state.models import InvestigationCase, RiskState
from src.tools.registry import ToolRegistry

Monotonic = Callable[[], float]


@dataclass(frozen=True)
class OrchestratedRunResult:
    run_id: str
    as_of_date: str
    stop_reason: str
    report: str
    trace: OrchestratorTrace
    risk_state: RiskState
    spawned: tuple[str, ...]
    specialist_results: dict[str, AgentRunResult]
    observations: tuple[ToolObservation, ...]
    routing: dict


@dataclass(frozen=True)
class _Job:
    case: InvestigationCase
    max_steps: int
    deadline: float
    planners: Mapping[str, Planner]
    registries: Mapping[str, ToolRegistry]
    use_llm: bool | None
    monotonic: Monotonic
    run_id: str


def _run_sync(factory):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(factory())).result()


def run_orchestrated_investigation(
    case: InvestigationCase, **kwargs
) -> OrchestratedRunResult:
    return _run_sync(lambda: run_orchestrated_investigation_async(case, **kwargs))


@traceable(
    name="orchestrated_investigation",
    run_type="chain",
    process_inputs=orchestrator_inputs,
    process_outputs=orchestrator_outputs,
)
async def run_orchestrated_investigation_async(
    case: InvestigationCase,
    max_steps: int = MAX_STEPS,
    *,
    overall_deadline_seconds: float = OVERALL_DEADLINE_SECONDS,
    planners: Mapping[str, Planner] | None = None,
    registries: Mapping[str, ToolRegistry] | None = None,
    use_llm: bool | None = None,
    monotonic: Monotonic = time.monotonic,
) -> OrchestratedRunResult:
    risk = case.risk_state
    run_id = uuid.uuid4().hex[:12]
    spawned = select_specialists(risk)
    quiet = no_meaningful_risk_signal(risk)
    deadline = float(overall_deadline_seconds)
    routing = {
        "quiet": quiet,
        "spawned": list(spawned),
        "schedule": SCHEDULE,
        "deadline_seconds": deadline,
    }
    job = _Job(
        case=case,
        max_steps=max_steps,
        deadline=deadline,
        planners=planners or {},
        registries=registries or {},
        use_llm=use_llm,
        monotonic=monotonic,
        run_id=run_id,
    )
    specialist_results, decisions = await _gather(spawned, job)
    stop_reason = _combined_stop(spawned, specialist_results, quiet)
    report, calibrated = build_combined_pm_note(
        risk_state=risk,
        spawned=spawned,
        specialist_results=specialist_results,
        stop_reason=stop_reason,
    )
    observations = tuple(
        observation
        for name in spawned
        if name in specialist_results
        for observation in specialist_results[name].observations
    )
    trace = OrchestratorTrace(
        run_id=run_id,
        as_of_date=risk.as_of_date.isoformat(),
        assessment_cutoff=risk.assessment_cutoff.isoformat(),
        spawned=list(spawned),
        routing=routing,
        decisions=[
            {
                "actor": "orchestrator",
                "action": "spawn" if spawned else "skip",
                "specialists": list(spawned),
                "reason": "NO_INVESTIGATION_NEEDED" if quiet else "deterministic_mechanisms",
                "schedule": SCHEDULE,
            },
            *decisions,
        ],
        specialist_traces={name: result.trace for name, result in specialist_results.items()},
        errors=[error for result in specialist_results.values() for error in result.state.errors],
        stop_reason=stop_reason,
        final_assessment=sanitize_text(calibrated.get("current_read")),
        calibrated=calibrated,
        report=report,
    )
    return OrchestratedRunResult(
        run_id=run_id,
        as_of_date=risk.as_of_date.isoformat(),
        stop_reason=stop_reason,
        report=report,
        trace=trace,
        risk_state=risk,
        spawned=spawned,
        specialist_results=specialist_results,
        observations=observations,
        routing=routing,
    )


async def _gather(
    spawned: tuple[str, ...], job: _Job
) -> tuple[dict[str, AgentRunResult], list[dict]]:
    if not spawned:
        return {}, []
    parent = parent_run()
    tasks = {
        name: asyncio.create_task(
            asyncio.to_thread(_run_specialist, name, job, parent),
            name=f"specialist-{name}",
        )
        for name in spawned
    }
    _done, pending = await asyncio.wait(
        set(tasks.values()), timeout=max(0.01, job.deadline)
    )
    results: dict[str, AgentRunResult] = {}
    decisions: list[dict] = []
    for name in spawned:
        task = tasks[name]
        if task in pending:
            task.cancel()
            decisions.append(
                {"actor": name, "action": "skipped", "reason": "DEADLINE_EXCEEDED"}
            )
            continue
        try:
            result = task.result()
        except Exception as exc:  # noqa: BLE001 - specialists are isolated
            decisions.append(
                {"actor": name, "action": "failed", "reason": "UNRESOLVABLE", "error": str(exc)}
            )
            continue
        results[name] = result
        decisions.append(
            {
                "actor": name,
                "action": "completed",
                "stop_reason": result.stop_reason,
                "steps": result.state.step,
                "tools": [item.name for item in result.observations],
            }
        )
    return results, decisions


def _run_specialist(name: str, job: _Job, parent=None) -> AgentRunResult:
    spec = BY_NAME[name]
    registry = job.registries.get(name) or spec.registry()
    extra = langsmith_extra_kwargs(
        parent=parent,
        name=f"specialist_loop [{spec.focus}]",
        metadata={"specialist": name, "focus": spec.focus},
        tags=[name, spec.focus],
    )
    return run_agent(
        job.case,
        max_steps=job.max_steps,
        overall_deadline_seconds=job.deadline,
        planner=job.planners.get(name),
        registry=registry,
        use_llm=job.use_llm,
        focus=spec.focus,
        monotonic=job.monotonic,
        run_id=f"{job.run_id}-{name[:3]}",
        **extra,
    )


def _combined_stop(
    spawned: tuple[str, ...], results: Mapping[str, AgentRunResult], quiet: bool
) -> str:
    if not spawned:
        return "NO_INVESTIGATION_NEEDED" if quiet else "UNRESOLVABLE"
    reasons = [results[name].stop_reason for name in spawned if name in results]
    if not reasons:
        return "DEADLINE_EXCEEDED"
    for preferred in ("ESCALATED", "MALFORMED_PLANNER_OUTPUT", "PLANNER_TIMEOUT"):
        if preferred in reasons:
            return preferred
    return "EVIDENCE_SUFFICIENT" if "EVIDENCE_SUFFICIENT" in reasons else reasons[0]
