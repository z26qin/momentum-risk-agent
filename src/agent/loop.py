"""Bounded planner → executor investigation loop.

Model plans. Executor enforces permissions, validation, timeouts, dedup,
cutoff, and termination. The quantitative risk snapshot is never written.
"""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, get_args

from pydantic import ValidationError

from src.agent.executor import Executor
from src.agent.models import (
    AgentDecision,
    AgentRunTrace,
    MalformedPlannerOutput,
    StopReason,
    ToolObservation,
)
from src.agent.planner import HeuristicPlanner, Planner, resolve_planner
from src.agent.report import build_pm_note, calibrated_buckets, sanitize_text
from src.agent.state import AgentState, freeze_risk_state, risk_cutoff
from src.mvp.config import HISTORICAL_EXAMPLE_DATE
from src.tools.context import ToolContext
from src.tools.registry import ToolRegistry, default_registry
from src.utils.io import DEFAULT_PROCESSED_DIR

MAX_STEPS = 6
OVERALL_DEADLINE_SECONDS = 10.0
Monotonic = Callable[[], float]


@dataclass(frozen=True)
class AgentRunResult:
    run_id: str
    as_of_date: str
    stop_reason: str
    report: str
    trace: AgentRunTrace
    risk_state: dict[str, Any]
    observations: tuple[ToolObservation, ...]
    state: AgentState
    planner_kind: str


def parse_decision(raw: Any) -> AgentDecision:
    if isinstance(raw, AgentDecision):
        return raw
    try:
        return AgentDecision.model_validate(raw)
    except (ValidationError, TypeError, ValueError) as exc:
        raise MalformedPlannerOutput(str(exc)) from exc


def prepare_risk_snapshot(
    as_of_date: str,
    *,
    risk_state: Mapping[str, Any] | None = None,
    mvp_result: Any | None = None,
) -> tuple[dict[str, Any], str, str, str]:
    frozen, fingerprint = freeze_risk_state(
        _load_risk_state(as_of_date, risk_state=risk_state, mvp_result=mvp_result)
    )
    date = str(frozen.get("as_of_date") or as_of_date)
    return frozen, fingerprint, date, risk_cutoff(frozen, as_of_date)


def run_agent(
    as_of_date: str = HISTORICAL_EXAMPLE_DATE,
    max_steps: int = MAX_STEPS,
    *,
    overall_deadline_seconds: float = OVERALL_DEADLINE_SECONDS,
    risk_state: Mapping[str, Any] | None = None,
    prior_state: Mapping[str, Any] | None = None,
    mvp_result: Any | None = None,
    planner: Planner | None = None,
    registry: ToolRegistry | None = None,
    use_llm: bool | None = None,
    monotonic: Monotonic = time.monotonic,
    processed_dir=DEFAULT_PROCESSED_DIR,
    focus: str | None = None,
    run_id: str | None = None,
) -> AgentRunResult:
    frozen, fingerprint, date, cutoff = prepare_risk_snapshot(
        as_of_date, risk_state=risk_state, mvp_result=mvp_result
    )
    run_id = run_id or uuid.uuid4().hex[:12]
    tools = registry or default_registry()
    selected = resolve_planner(
        planner=planner,
        use_llm=use_llm,
        focus=focus,
        allowed_tools=tools.names(),
    )
    deadline = float(overall_deadline_seconds)
    state = AgentState(
        as_of_date=date,
        assessment_cutoff=cutoff,
        run_id=run_id,
        max_steps=max(1, int(max_steps)),
        overall_deadline_seconds=deadline,
        remaining_seconds=deadline,
        _risk_state=frozen,
        _risk_fingerprint=fingerprint,
        prior_state=copy.deepcopy(dict(prior_state)) if prior_state is not None else None,
        focus=focus,
    )
    ctx = ToolContext(
        as_of_date=state.as_of_date,
        assessment_cutoff=state.assessment_cutoff,
        risk_state=state._risk_state,
        prior_state=state.prior_state,
        processed_dir=processed_dir,
    )
    fallback = HeuristicPlanner(focus=focus) if str(selected.kind).startswith("llm") else None
    try:
        planner_kind = _run_loop(
            state,
            planner=selected,
            fallback=fallback,
            executor=Executor(tools, monotonic=monotonic),
            ctx=ctx,
            monotonic=monotonic,
            started=monotonic(),
        )
    finally:
        state.assert_risk_unchanged()
    report = build_pm_note(state)
    return AgentRunResult(
        run_id=run_id,
        as_of_date=state.as_of_date,
        stop_reason=state.stop_reason or "MAX_STEPS",
        report=report,
        trace=_build_trace(state, planner_kind, report),
        risk_state=state.risk_state,
        observations=tuple(state.observations),
        state=state,
        planner_kind=planner_kind,
    )


def _run_loop(
    state: AgentState,
    *,
    planner: Planner,
    fallback: Planner | None,
    executor: Executor,
    ctx: ToolContext,
    monotonic: Monotonic,
    started: float,
) -> str:
    active = planner
    while state.status == "running":
        remaining = state.overall_deadline_seconds - (monotonic() - started)
        state.remaining_seconds = remaining
        if remaining <= 0:
            _stop(state, "DEADLINE_EXCEEDED")
            return active.kind
        if state.step >= state.max_steps:
            _stop(state, "MAX_STEPS")
            return active.kind
        try:
            decision = parse_decision(active.decide(state))
        except (TimeoutError, MalformedPlannerOutput) as exc:
            if fallback is not None and active is not fallback:
                label = "timeout" if isinstance(exc, TimeoutError) else "malformed planner output"
                state.errors.append(f"{label}; falling back to heuristic")
                active = fallback
                continue
            if isinstance(exc, TimeoutError):
                state.errors.append(str(exc))
                _stop(state, "PLANNER_TIMEOUT")
            else:
                state.errors.append(f"malformed planner output: {exc}")
                _stop(state, "MALFORMED_PLANNER_OUTPUT")
            return active.kind
        state.step += 1
        state.decisions.append(decision)
        state.last_decision = decision
        if decision.hypothesis and decision.hypothesis not in state.investigated_hypotheses:
            state.investigated_hypotheses.append(decision.hypothesis)
        for question in decision.open_questions:
            if question not in state.open_questions:
                state.open_questions.append(question)
        if decision.action in {"finish", "escalate"}:
            _stop(state, _map_stop_reason(decision))
            return active.kind
        batch = executor.execute_decision(decision, state, ctx, remaining_seconds=remaining)
        state.observations.extend(batch)
        _ingest_evidence(state, batch)
        if monotonic() - started >= state.overall_deadline_seconds:
            _stop(state, "DEADLINE_EXCEEDED")
            return active.kind
        if batch and all(item.status == "duplicate" for item in batch):
            _stop(state, "UNRESOLVABLE")
            return active.kind
    return active.kind


def _ingest_evidence(state: AgentState, batch: list[ToolObservation]) -> None:
    seen = {(item.get("evidence_id"), item.get("headline")) for item in state.evidence}
    for observation in batch:
        if observation.status != "ok" or not isinstance(observation.payload, dict):
            continue
        for doc in observation.payload.get("documents") or []:
            if not isinstance(doc, dict):
                continue
            key = (doc.get("evidence_id"), doc.get("headline"))
            if key in seen:
                continue
            state.evidence.append(doc)
            seen.add(key)
        discarded = int(observation.discarded_post_cutoff or 0)
        if discarded:
            state.errors.append(
                f"{observation.name} rejected {discarded} post-cutoff document(s)"
            )


def _map_stop_reason(decision: AgentDecision) -> str:
    if decision.action == "escalate":
        return "ESCALATED"
    reason = decision.reason.strip().upper().replace(" ", "_")
    if reason in get_args(StopReason):
        return reason
    text = f"{decision.reason} {decision.final_assessment or ''}".lower()
    if "contradict" in text:
        return "EVIDENCE_CONTRADICTED"
    if "quiet" in text or "no investigation" in text:
        return "NO_INVESTIGATION_NEEDED"
    return "EVIDENCE_SUFFICIENT"


def _stop(state: AgentState, reason: str) -> None:
    state.status = "stopped"
    state.stop_reason = reason


def _build_trace(state: AgentState, planner_kind: str, report: str) -> AgentRunTrace:
    return AgentRunTrace(
        run_id=state.run_id,
        as_of_date=state.as_of_date,
        assessment_cutoff=state.assessment_cutoff,
        planner_kind=planner_kind,
        decisions=[item.model_dump() for item in state.decisions],
        tool_calls=[
            call.model_dump()
            for decision in state.decisions
            for call in decision.tool_calls
        ],
        tool_results=[item.model_dump() for item in state.observations],
        errors=list(state.errors),
        stop_reason=state.stop_reason or "MAX_STEPS",
        final_assessment=sanitize_text(
            (state.last_decision.final_assessment if state.last_decision else None)
            or report.split("Current read", 1)[-1][:400]
        ),
        calibrated=calibrated_buckets(state),
    )


def _load_risk_state(
    as_of_date: str,
    *,
    risk_state: Mapping[str, Any] | None,
    mvp_result: Any | None,
) -> dict[str, Any]:
    if risk_state is not None:
        return copy.deepcopy(dict(risk_state))
    if mvp_result is not None:
        from src.mvp.hermes_monitor import compact_assessment_from_result

        return compact_assessment_from_result(mvp_result)
    from src.mvp.hermes_monitor import run_compact_assessment

    return run_compact_assessment(as_of_date=as_of_date)
