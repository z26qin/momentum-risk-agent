"""Bounded planner → executor investigation loop.

Model plans. Executor enforces permissions, validation, timeouts, dedup,
cutoff, and termination. The quantitative risk snapshot is never written.
"""

from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from pydantic import ValidationError

from src.agent.executor import Executor
from src.agent.models import (
    AgentDecision,
    AgentRunTrace,
    MalformedPlannerOutput,
    ToolObservation,
)
from src.agent.planner import Planner, resolve_planner
from src.agent.report import build_pm_note, calibrated_buckets, sanitize_text
from src.agent.state import AgentState, freeze_risk_state
from src.tools.context import ToolContext
from src.tools.registry import ToolRegistry, default_registry
from src.utils.io import DEFAULT_PROCESSED_DIR
from src.utils.market_time import assessment_timestamp

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


def run_agent(
    as_of_date: str = "2026-05-29",
    max_steps: int = MAX_STEPS,
    verbose: bool = False,
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
) -> AgentRunResult:
    loaded = _load_risk_state(as_of_date, risk_state=risk_state, mvp_result=mvp_result)
    frozen, fingerprint = freeze_risk_state(loaded)
    del fingerprint
    cutoff = str(frozen.get("data_cutoff") or frozen.get("evidence_cutoff") or assessment_timestamp(as_of_date))
    run_id = uuid.uuid4().hex[:12]
    selected = resolve_planner(planner=planner, use_llm=use_llm)
    tools = registry or default_registry()
    executor = Executor(tools, monotonic=monotonic)
    prior = copy.deepcopy(dict(prior_state)) if prior_state is not None else None
    state = AgentState(
        as_of_date=str(frozen.get("as_of_date") or as_of_date),
        assessment_cutoff=cutoff,
        run_id=run_id,
        max_steps=max(1, int(max_steps)),
        overall_deadline_seconds=float(overall_deadline_seconds),
        remaining_seconds=float(overall_deadline_seconds),
        _risk_state=frozen,
        _risk_fingerprint=state_fingerprint(frozen),
        prior_state=prior,
    )
    started = monotonic()
    _log(state, f"deterministic state loaded; planner={selected.kind}", verbose=verbose)
    try:
        _run_loop(
            state,
            planner=selected,
            executor=executor,
            verbose=verbose,
            monotonic=monotonic,
            started=started,
            processed_dir=processed_dir,
        )
    finally:
        state.assert_risk_unchanged()
    if state.status == "running":
        _stop(state, "MAX_STEPS", verbose=verbose)
    report = build_pm_note(state)
    if verbose:
        print(report)
    trace = _build_trace(state, selected.kind, report)
    return AgentRunResult(
        run_id=run_id,
        as_of_date=state.as_of_date,
        stop_reason=state.stop_reason or "MAX_STEPS",
        report=report,
        trace=trace,
        risk_state=state.risk_state,
        observations=tuple(state.observations),
        state=state,
        planner_kind=selected.kind,
    )


def state_fingerprint(payload: Mapping[str, Any]) -> str:
    from src.agent.state import fingerprint_risk_state

    return fingerprint_risk_state(payload)


def _run_loop(
    state: AgentState,
    *,
    planner: Planner,
    executor: Executor,
    verbose: bool,
    monotonic: Monotonic,
    started: float,
    processed_dir,
) -> None:
    while state.status == "running":
        state.remaining_seconds = state.overall_deadline_seconds - (monotonic() - started)
        if state.remaining_seconds <= 0:
            _stop(state, "DEADLINE_EXCEEDED", verbose=verbose)
            return
        if state.step >= state.max_steps:
            _stop(state, "MAX_STEPS", verbose=verbose)
            return
        try:
            raw = planner.decide(state)
            decision = parse_decision(raw)
        except TimeoutError as exc:
            state.errors.append(str(exc))
            _stop(state, "PLANNER_TIMEOUT", verbose=verbose)
            return
        except MalformedPlannerOutput as exc:
            state.errors.append(f"malformed planner output: {exc}")
            _stop(state, "MALFORMED_PLANNER_OUTPUT", verbose=verbose)
            return
        state.step += 1
        state.decisions.append(decision)
        state.last_decision = decision
        if decision.hypothesis and decision.hypothesis not in state.investigated_hypotheses:
            state.investigated_hypotheses.append(decision.hypothesis)
        for question in decision.open_questions:
            if question not in state.open_questions:
                state.open_questions.append(question)
        _log(state, f"hypothesis={decision.hypothesis}", verbose=verbose)
        if verbose and decision.action == "call_tools":
            names = [call.name for call in decision.tool_calls]
            print(f"Step {state.step}")
            print(f"hypothesis={decision.hypothesis}")
            print(f"tools={names}")
            print()
        if decision.action in {"finish", "escalate"}:
            reason = _map_stop_reason(decision)
            _stop(state, reason, verbose=verbose)
            return
        ctx = ToolContext(
            as_of_date=state.as_of_date,
            assessment_cutoff=state.assessment_cutoff,
            risk_state=state.risk_state,
            prior_state=state.prior_state,
            processed_dir=processed_dir,
        )
        remaining = state.overall_deadline_seconds - (monotonic() - started)
        batch = executor.execute_decision(decision, state, ctx, remaining_seconds=remaining)
        state.observations.extend(batch)
        _ingest_evidence(state, batch)
        if verbose:
            print(f"Step {state.step} results")
            for item in batch:
                detail = item.error_type or (
                    f"docs={len((item.payload or {}).get('documents', []))}"
                    if isinstance(item.payload, dict)
                    else item.status
                )
                print(f"  {item.name} status={item.status} {detail}")
            print()
        if remaining <= 0 or (state.overall_deadline_seconds - (monotonic() - started)) <= 0:
            _stop(state, "DEADLINE_EXCEEDED", verbose=verbose)
            return
        if batch and all(item.status == "duplicate" for item in batch):
            state.consecutive_duplicate_steps += 1
            if state.consecutive_duplicate_steps >= 1:
                _stop(state, "UNRESOLVABLE", verbose=verbose)
                return
        else:
            state.consecutive_duplicate_steps = 0


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
    allowed = {
        "EVIDENCE_SUFFICIENT",
        "EVIDENCE_CONTRADICTED",
        "NO_INVESTIGATION_NEEDED",
        "UNRESOLVABLE",
        "MAX_STEPS",
        "DEADLINE_EXCEEDED",
        "ESCALATED",
    }
    reason = decision.reason.strip().upper().replace(" ", "_")
    if reason in allowed:
        return reason
    text = f"{decision.reason} {decision.final_assessment or ''}".lower()
    if "contradict" in text:
        return "EVIDENCE_CONTRADICTED"
    if "quiet" in text or "no investigation" in text:
        return "NO_INVESTIGATION_NEEDED"
    return "EVIDENCE_SUFFICIENT"


def _stop(state: AgentState, reason: str, *, verbose: bool) -> None:
    state.status = "stopped"
    state.stop_reason = reason
    state.logs.append(f"[Agent {state.step}] STOP: {reason}")
    if verbose:
        print(f"STOP: {reason}")
        print()


def _log(state: AgentState, message: str, *, verbose: bool) -> None:
    line = f"[Agent {state.step}] {message}"
    state.logs.append(line)
    if verbose:
        print(line)


def _build_trace(state: AgentState, planner_kind: str, report: str) -> AgentRunTrace:
    decisions = [item.model_dump() for item in state.decisions]
    tool_calls = [
        call.model_dump()
        for decision in state.decisions
        for call in decision.tool_calls
    ]
    results = [item.model_dump() for item in state.observations]
    return AgentRunTrace(
        run_id=state.run_id,
        as_of_date=state.as_of_date,
        assessment_cutoff=state.assessment_cutoff,
        planner_kind=planner_kind,
        decisions=decisions,
        tool_calls=tool_calls,
        tool_results=results,
        errors=list(state.errors),
        stop_reason=state.stop_reason or "MAX_STEPS",
        final_assessment=sanitize_text(
            (state.last_decision.final_assessment if state.last_decision else None) or report.split("Current read", 1)[-1][:400]
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
