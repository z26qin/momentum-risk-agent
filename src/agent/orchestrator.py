"""Code-first orchestrator over two mechanism-specialist monitors.

Routing is Python. Specialists do not talk to each other. Findings are never
merged into a crash score.
"""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from src.agent.loop import (
    MAX_STEPS,
    OVERALL_DEADLINE_SECONDS,
    AgentRunResult,
    _load_risk_state,
    run_agent,
)
from src.agent.models import OrchestratorTrace, ToolObservation
from src.agent.planner import Planner, resolve_planner
from src.agent.report import build_combined_pm_note, sanitize_text
from src.agent.state import fingerprint_risk_state, freeze_risk_state
from src.agent_prompts import (
    crowding_signal_present,
    no_meaningful_risk_signal,
    recovery_setup_present,
)
from src.tools.registry import ToolRegistry, crowding_registry, recovery_registry
from src.utils.io import DEFAULT_PROCESSED_DIR
from src.utils.market_time import assessment_timestamp

Monotonic = Callable[[], float]
CROWDING, RECOVERY = "crowding", "recovery"
SPECIALIST_FOCUS = {CROWDING: "kl_crowding", RECOVERY: "dm_recovery"}
SPECIALIST_LABELS = {
    CROWDING: "Crowding (Khandani–Lo)",
    RECOVERY: "Recovery (Daniel–Moskowitz)",
}


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
    planner_kind: str = "orchestrator"
    routing: dict[str, Any] = field(default_factory=dict)


def select_specialists(risk_state: Mapping[str, Any]) -> tuple[str, ...]:
    """Quiet books spawn nobody. Flags, not leftover primary_driver labels."""

    if no_meaningful_risk_signal(risk_state):
        return ()
    spawned: list[str] = []
    if crowding_signal_present(risk_state):
        spawned.append(CROWDING)
    if recovery_setup_present(risk_state):
        spawned.append(RECOVERY)
    return tuple(spawned)


def run_orchestrated_investigation(
    as_of_date: str = "2026-05-29",
    max_steps: int = MAX_STEPS,
    verbose: bool = False,
    *,
    overall_deadline_seconds: float = OVERALL_DEADLINE_SECONDS,
    risk_state: Mapping[str, Any] | None = None,
    prior_state: Mapping[str, Any] | None = None,
    mvp_result: Any | None = None,
    crowding_planner: Planner | None = None,
    recovery_planner: Planner | None = None,
    crowding_tools: ToolRegistry | None = None,
    recovery_tools: ToolRegistry | None = None,
    use_llm: bool | None = None,
    monotonic: Monotonic = time.monotonic,
    processed_dir=DEFAULT_PROCESSED_DIR,
) -> OrchestratedRunResult:
    loaded = _load_risk_state(as_of_date, risk_state=risk_state, mvp_result=mvp_result)
    frozen, fingerprint = freeze_risk_state(loaded)
    cutoff = str(
        frozen.get("data_cutoff") or frozen.get("evidence_cutoff") or assessment_timestamp(as_of_date)
    )
    run_id = uuid.uuid4().hex[:12]
    date = str(frozen.get("as_of_date") or as_of_date)
    prior = copy.deepcopy(dict(prior_state)) if prior_state is not None else None
    spawned = select_specialists(frozen)
    quiet = no_meaningful_risk_signal(frozen)
    routing = {
        "quiet": quiet,
        "crowding_signal": CROWDING in spawned,
        "recovery_setup": RECOVERY in spawned,
        "spawned": list(spawned),
    }
    decisions: list[dict[str, Any]] = [
        {
            "actor": "orchestrator",
            "action": "spawn" if spawned else "skip",
            "specialists": list(spawned),
            "reason": "NO_INVESTIGATION_NEEDED" if quiet else "deterministic_flags",
        }
    ]
    if verbose:
        print(f"Orchestrator: spawned={list(spawned)}\n")

    specialist_results: dict[str, AgentRunResult] = {}
    started = monotonic()
    planners = {CROWDING: crowding_planner, RECOVERY: recovery_planner}
    registries = {CROWDING: crowding_tools, RECOVERY: recovery_tools}
    defaults = {CROWDING: crowding_registry, RECOVERY: recovery_registry}

    for name in spawned:
        remaining = float(overall_deadline_seconds) - (monotonic() - started)
        if remaining <= 0:
            decisions.append(
                {"actor": "orchestrator", "action": "skip", "specialist": name, "reason": "DEADLINE_EXCEEDED"}
            )
            continue
        registry = registries[name] if registries[name] is not None else defaults[name]()
        planner = resolve_planner(
            planner=planners[name],
            use_llm=use_llm,
            focus=SPECIALIST_FOCUS[name],
            allowed_tools=registry.names(),
        )
        if verbose:
            print(f"=== {SPECIALIST_LABELS[name]} ===\n")
        result = run_agent(
            as_of_date=date,
            max_steps=max_steps,
            verbose=verbose,
            print_report=False,
            overall_deadline_seconds=remaining,
            risk_state=frozen,
            prior_state=prior,
            planner=planner,
            registry=registry,
            focus=SPECIALIST_FOCUS[name],
            monotonic=monotonic,
            processed_dir=processed_dir,
            run_id=f"{run_id}-{name[:3]}",
        )
        specialist_results[name] = result
        decisions.append(
            {
                "actor": name,
                "action": "completed",
                "stop_reason": result.stop_reason,
                "steps": result.state.step,
                "tools": [item.name for item in result.observations],
            }
        )

    if fingerprint_risk_state(frozen) != fingerprint:
        raise RuntimeError("invariant violated: deterministic risk state changed")
    for result in specialist_results.values():
        result.state.assert_risk_unchanged()

    stop_reason = _combined_stop(spawned, specialist_results, quiet)
    report, calibrated = build_combined_pm_note(
        risk_state=frozen,
        spawned=spawned,
        specialist_results=specialist_results,
        stop_reason=stop_reason,
    )
    if verbose:
        print(report)
    observations = tuple(
        item
        for name in spawned
        if name in specialist_results
        for item in specialist_results[name].observations
    )
    errors = [
        error
        for name in spawned
        if name in specialist_results
        for error in specialist_results[name].state.errors
    ]
    trace = OrchestratorTrace(
        run_id=run_id,
        as_of_date=date,
        assessment_cutoff=cutoff,
        spawned=list(spawned),
        routing=routing,
        decisions=decisions,
        specialist_traces={name: specialist_results[name].trace for name in specialist_results},
        errors=errors,
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


def _combined_stop(
    spawned: Sequence[str],
    results: Mapping[str, AgentRunResult],
    quiet: bool,
) -> str:
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
