"""Code-first orchestrator over two mechanism-specialist monitors.

The deterministic monitor remains the source of truth. This module only
routes (in code) and synthesizes a PM note (in code). It never calls
market/evidence tools, never merges findings into a crash score, and never
lets specialists talk to each other.
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
from src.agent.report import (
    calibrated_buckets,
    contains_forbidden,
    sanitize_text,
    snapshot_observed,
)
from src.agent.state import fingerprint_risk_state, freeze_risk_state
from src.agent_prompts import (
    CROWDING_FLAGS,
    active_flags,
    crowding_signal_present,
    no_meaningful_risk_signal,
    recovery_setup_present,
)
from src.tools.registry import (
    CROWDING_TOOL_NAMES,
    RECOVERY_TOOL_NAMES,
    ToolRegistry,
    crowding_registry,
    recovery_registry,
)
from src.utils.io import DEFAULT_PROCESSED_DIR
from src.utils.market_time import assessment_timestamp

Monotonic = Callable[[], float]

CROWDING = "crowding"
RECOVERY = "recovery"

SPECIALIST_FOCUS = {
    CROWDING: "kl_crowding",
    RECOVERY: "dm_recovery",
}
SPECIALIST_LABELS = {
    CROWDING: "Crowding (Khandani–Lo)",
    RECOVERY: "Recovery (Daniel–Moskowitz)",
}
SPECIALIST_QUESTIONS = {
    CROWDING: "Is pressure a localized crowded unwind, or forced deleveraging?",
    RECOVERY: "Is this a recovery-driven loser rebound / lagging-leg crash setup?",
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
    """Deterministic routing. Quiet books spawn nobody — hard invariant."""

    if no_meaningful_risk_signal(risk_state) or quiet_scorecard(risk_state):
        return ()
    spawned: list[str] = []
    if crowding_signal_present(risk_state):
        spawned.append(CROWDING)
    if recovery_setup_present(risk_state):
        spawned.append(RECOVERY)
    return tuple(spawned)


def quiet_scorecard(risk_state: Mapping[str, Any]) -> bool:
    """True when the scorecard is quiet even if ``primary_driver`` is a leftover label.

    January 2024 compact assessments can still say ``primary_driver=crowded_unwind``
    while triggers are 0, unwind is NORMAL, and crowding flags are unconfirmed.
    That label must not spawn a search.
    """

    if int(risk_state.get("deterministic_trigger_count") or 0) > 0:
        return False
    if str(risk_state.get("mechanical_unwind_state") or "NORMAL") not in {"NORMAL", "", "None"}:
        return False
    flags = active_flags(risk_state)
    if flags & CROWDING_FLAGS:
        return False
    if recovery_setup_present(risk_state):
        return False
    return True


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
        frozen.get("data_cutoff")
        or frozen.get("evidence_cutoff")
        or assessment_timestamp(as_of_date)
    )
    run_id = uuid.uuid4().hex[:12]
    date = str(frozen.get("as_of_date") or as_of_date)
    prior = copy.deepcopy(dict(prior_state)) if prior_state is not None else None
    spawned = select_specialists(frozen)
    quiet = no_meaningful_risk_signal(frozen) or quiet_scorecard(frozen)
    routing = {
        "quiet": quiet,
        "crowding_signal": crowding_signal_present(frozen) and not quiet,
        "recovery_setup": recovery_setup_present(frozen) and not quiet,
        "spawned": list(spawned),
    }
    decisions: list[dict[str, Any]] = [
        {
            "actor": "orchestrator",
            "action": "spawn" if spawned else "skip",
            "specialists": list(spawned),
            "reason": (
                "NO_INVESTIGATION_NEEDED"
                if not spawned and routing["quiet"]
                else "deterministic_flags"
            ),
        }
    ]
    if verbose:
        print(f"Orchestrator: spawned={list(spawned) if spawned else []}")
        if not spawned:
            print("No specialists ran.")
        print()

    specialist_results: dict[str, AgentRunResult] = {}
    started = monotonic()
    deadline = float(overall_deadline_seconds)

    for name in spawned:
        remaining = deadline - (monotonic() - started)
        if remaining <= 0:
            decisions.append(
                {
                    "actor": "orchestrator",
                    "action": "skip",
                    "specialist": name,
                    "reason": "DEADLINE_EXCEEDED",
                }
            )
            if verbose:
                print(f"[{name}] skipped: shared deadline exhausted")
                print()
            continue
        registry = _registry_for(
            name, crowding_tools=crowding_tools, recovery_tools=recovery_tools
        )
        selected_planner = _planner_for(
            name,
            crowding_planner=crowding_planner,
            recovery_planner=recovery_planner,
            use_llm=use_llm,
            allowed_tools=registry.names(),
        )
        if verbose:
            print(f"=== Specialist: {SPECIALIST_LABELS[name]} ===")
            print(f"question: {SPECIALIST_QUESTIONS[name]}")
            print(f"tools={list(registry.names())}")
            print()
        result = run_agent(
            as_of_date=date,
            max_steps=max_steps,
            verbose=verbose,
            print_report=False,
            overall_deadline_seconds=remaining,
            risk_state=frozen,
            prior_state=prior,
            planner=selected_planner,
            registry=registry,
            focus=SPECIALIST_FOCUS[name],
            monotonic=monotonic,
            processed_dir=processed_dir,
            run_id=f"{run_id}-{name[:3]}",
        )
        specialist_results[name] = result
        tool_names = [item.name for item in result.observations]
        decisions.append(
            {
                "actor": name,
                "action": "completed",
                "stop_reason": result.stop_reason,
                "steps": result.state.step,
                "tools": tool_names,
            }
        )
        if verbose:
            print(f"[{name}] STOP: {result.stop_reason}")
            print()

    if fingerprint_risk_state(frozen) != fingerprint:
        raise RuntimeError("invariant violated: deterministic risk state changed")
    for result in specialist_results.values():
        result.state.assert_risk_unchanged()

    stop_reason = _combined_stop(spawned, specialist_results, routing["quiet"])
    report, calibrated = synthesize_combined_note(
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
        specialist_traces={
            name: specialist_results[name].trace for name in specialist_results
        },
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


def synthesize_combined_note(
    *,
    risk_state: Mapping[str, Any],
    spawned: Sequence[str],
    specialist_results: Mapping[str, AgentRunResult],
    stop_reason: str,
) -> tuple[str, dict[str, Any]]:
    """Assemble one PM note in code. Never average mechanism scores."""

    mechanism_buckets: dict[str, dict[str, Any]] = {}
    for name in spawned:
        result = specialist_results.get(name)
        if result is None:
            continue
        mechanism_buckets[name] = calibrated_buckets(result.state)

    observed = _unique(_prefixed_items(snapshot_observed(risk_state), None))
    inferred: list[str] = []
    against: list[str] = []
    not_confirmed: list[str] = []
    for name in spawned:
        buckets = mechanism_buckets.get(name)
        if not buckets:
            continue
        label = SPECIALIST_LABELS[name]
        observed.extend(
            _prefixed_items(_tool_only_observed(buckets["observed"], risk_state), label)
        )
        inferred.extend(_prefixed_items(buckets["inferred"], label))
        against.extend(_prefixed_items(buckets["contradicted"], label))
        not_confirmed.extend(_prefixed_items(buckets["not_confirmed"], label))

    observed = _clean_lines(observed) or ["No additional observations beyond the snapshot."]
    inferred = _clean_lines(inferred) or [
        "No additional inference beyond the deterministic snapshot."
    ]
    against = _clean_lines(against) or ["None"]
    not_confirmed = _clean_lines(not_confirmed) or ["None"]

    current_read = _combined_current_read(stop_reason, spawned, mechanism_buckets)
    what_changed = _combined_what_changed(risk_state, spawned, mechanism_buckets)
    next_check = _combined_next_check(risk_state, spawned, mechanism_buckets)
    path = _investigation_path(spawned, specialist_results, stop_reason)

    sections = [
        f"Current read\n{current_read}",
        f"Observed:\n{_bullets(observed)}",
        f"Inferred:\n{_bullets(inferred)}",
        f"Against:\n{_bullets(against)}",
        f"Not confirmed:\n{_bullets(not_confirmed)}",
    ]
    for name in spawned:
        buckets = mechanism_buckets.get(name)
        if not buckets:
            continue
        sections.append(_mechanism_section(name, buckets))
    sections.extend(
        [
            f"Investigation path:\n{path}",
            f"What changed:\n{what_changed}",
            f"Next useful check:\n{next_check}",
        ]
    )
    report = "\n\n".join(sections) + "\n"
    calibrated = {
        "observed": observed,
        "inferred": inferred,
        "contradicted": against,
        "not_confirmed": not_confirmed,
        "current_read": current_read,
        "what_changed": what_changed,
        "next_useful_check": next_check,
        "score_is_probability": False,
        "spawned": list(spawned),
        "mechanisms": mechanism_buckets,
    }
    return report, calibrated


def _registry_for(
    name: str,
    *,
    crowding_tools: ToolRegistry | None,
    recovery_tools: ToolRegistry | None,
) -> ToolRegistry:
    if name == CROWDING:
        return crowding_tools if crowding_tools is not None else crowding_registry()
    if name == RECOVERY:
        return recovery_tools if recovery_tools is not None else recovery_registry()
    raise KeyError(f"unknown specialist {name!r}")


def _planner_for(
    name: str,
    *,
    crowding_planner: Planner | None,
    recovery_planner: Planner | None,
    use_llm: bool | None,
    allowed_tools: Sequence[str],
) -> Planner:
    given = crowding_planner if name == CROWDING else recovery_planner
    return resolve_planner(
        planner=given,
        use_llm=use_llm,
        focus=SPECIALIST_FOCUS[name],
        allowed_tools=allowed_tools,
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
    if "ESCALATED" in reasons:
        return "ESCALATED"
    if "MALFORMED_PLANNER_OUTPUT" in reasons:
        return "MALFORMED_PLANNER_OUTPUT"
    if "PLANNER_TIMEOUT" in reasons:
        return "PLANNER_TIMEOUT"
    unique = list(dict.fromkeys(reasons))
    if len(unique) == 1:
        return unique[0]
    if "EVIDENCE_SUFFICIENT" in unique:
        return "EVIDENCE_SUFFICIENT"
    return unique[0]


def _combined_current_read(
    stop_reason: str,
    spawned: Sequence[str],
    buckets: Mapping[str, Mapping[str, Any]],
) -> str:
    if stop_reason == "NO_INVESTIGATION_NEEDED" or not spawned:
        return (
            "The deterministic state does not justify additional evidence search. "
            "Continue ordinary monitoring."
        )
    if len(spawned) == 1:
        only = buckets.get(spawned[0], {})
        text = sanitize_text(str(only.get("current_read") or ""))
        if text:
            return text
    if len(spawned) > 1:
        return (
            "Crowding and recovery were investigated separately. "
            "Findings are listed by mechanism and are not combined into one score. "
            "This is not a trade instruction."
        )
    return (
        "Investigation stopped with remaining uncertainty. "
        "The quantitative state is unchanged."
    )


def _combined_what_changed(
    risk_state: Mapping[str, Any],
    spawned: Sequence[str],
    buckets: Mapping[str, Mapping[str, Any]],
) -> str:
    for name in (RECOVERY, CROWDING):
        if name not in spawned:
            continue
        text = str((buckets.get(name) or {}).get("what_changed") or "").strip()
        if text and "No prior-date comparison" not in text:
            return text
    compare_to = risk_state.get("compare_to_date")
    if compare_to:
        return (
            f"Deterministic snapshot already compared with {compare_to}; "
            "this investigation did not recompute that delta."
        )
    return "No prior-date comparison was loaded for this investigation."


def _combined_next_check(
    risk_state: Mapping[str, Any],
    spawned: Sequence[str],
    buckets: Mapping[str, Mapping[str, Any]],
) -> str:
    for name in spawned:
        text = str((buckets.get(name) or {}).get("next_useful_check") or "").strip()
        if text:
            return text
    checks = list(risk_state.get("next_checks") or [])
    if checks:
        return str(checks[0])
    return "Continue ordinary monitoring of breadth, liquidity, and the concentrated names."


def _investigation_path(
    spawned: Sequence[str],
    results: Mapping[str, AgentRunResult],
    stop_reason: str,
) -> str:
    lines: list[str] = []
    if not spawned:
        lines.append("1. Orchestrator: no specialists spawned")
        lines.append(f"2. STOP: {stop_reason}")
        return "\n".join(lines)
    lines.append(f"1. Orchestrator spawned: {', '.join(spawned)}")
    step = 1
    for name in spawned:
        result = results.get(name)
        if result is None:
            step += 1
            lines.append(f"{step}. [{name}] skipped")
            continue
        for decision in result.state.decisions:
            step += 1
            tools = (
                [call.name for call in decision.tool_calls]
                if decision.action == "call_tools"
                else []
            )
            if tools:
                lines.append(f"{step}. [{name}] {decision.hypothesis} · tools={tools}")
            else:
                lines.append(
                    f"{step}. [{name}] {decision.action.upper()} ({decision.reason})"
                )
        step += 1
        lines.append(f"{step}. [{name}] STOP: {result.stop_reason}")
    step += 1
    lines.append(f"{step}. Combined STOP: {stop_reason}")
    return "\n".join(lines)


def _mechanism_section(name: str, buckets: Mapping[str, Any]) -> str:
    return (
        f"{SPECIALIST_LABELS[name]}\n"
        f"Question: {SPECIALIST_QUESTIONS[name]}\n"
        f"Observed:\n{_bullets(_clean_lines(list(buckets.get('observed') or [])))}\n\n"
        f"Inferred:\n{_bullets(_clean_lines(list(buckets.get('inferred') or [])))}\n\n"
        f"Against:\n{_bullets(_clean_lines(list(buckets.get('contradicted') or [])))}\n\n"
        f"Not confirmed:\n{_bullets(_clean_lines(list(buckets.get('not_confirmed') or [])))}"
    )


def _tool_only_observed(observed: Sequence[str], risk_state: Mapping[str, Any]) -> list[str]:
    snapshot = set(snapshot_observed(risk_state))
    return [item for item in observed if item not in snapshot]


def _prefixed_items(items: Sequence[str], label: str | None) -> list[str]:
    prefix = f"[{label}] " if label else ""
    return [f"{prefix}{item}" for item in items if str(item).strip()]


def _clean_lines(items: Sequence[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        text = sanitize_text(item)
        if not text:
            if contains_forbidden(item):
                cleaned.append("Model proposed forbidden action language; that text was dropped.")
            continue
        cleaned.append(text)
    return _unique(cleaned)


def _unique(items: Sequence[str]) -> list[str]:
    return [item for item in dict.fromkeys(items) if item]


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


# Referenced by tests / docs; not used at runtime by the orchestrator itself.
SPECIALIST_TOOL_ALLOWLIST = {
    CROWDING: CROWDING_TOOL_NAMES,
    RECOVERY: RECOVERY_TOOL_NAMES,
}
