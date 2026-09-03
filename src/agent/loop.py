"""Bounded planner → executor investigation loop."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, get_args

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
from src.agent.state import AgentState
from src.agent.synthesis import build_pm_note, calibrated_buckets, sanitize_text
from src.agent.tracing import (
    record_event,
    specialist_inputs,
    specialist_outputs,
    traceable,
)
from src.risk_state.models import InvestigationCase, RiskState
from src.tools.context import ToolContext
from src.tools.registry import ToolRegistry, default_registry

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
    risk_state: RiskState
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


@traceable(
    name="specialist_loop",
    run_type="chain",
    process_inputs=specialist_inputs,
    process_outputs=specialist_outputs,
)
def run_agent(
    case: InvestigationCase,
    max_steps: int = MAX_STEPS,
    *,
    overall_deadline_seconds: float = OVERALL_DEADLINE_SECONDS,
    planner: Planner | None = None,
    registry: ToolRegistry | None = None,
    use_llm: bool | None = None,
    monotonic: Monotonic = time.monotonic,
    focus: str | None = None,
    run_id: str | None = None,
) -> AgentRunResult:
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
        case=case,
        run_id=run_id,
        max_steps=max(1, int(max_steps)),
        overall_deadline_seconds=deadline,
        remaining_seconds=deadline,
        focus=focus,
    )
    fallback = (
        HeuristicPlanner(focus=focus) if str(selected.kind).startswith("llm") else None
    )
    planner_kind = _run_loop(
        state,
        planner=selected,
        fallback=fallback,
        executor=Executor(tools, monotonic=monotonic),
        ctx=ToolContext.from_case(case),
        monotonic=monotonic,
        started=monotonic(),
    )
    report = build_pm_note(state)
    return AgentRunResult(
        run_id=run_id,
        as_of_date=state.as_of_date,
        stop_reason=state.stop_reason or "MAX_STEPS",
        report=report,
        trace=_build_trace(state, planner_kind, report),
        risk_state=case.risk_state,
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
    transitioned = False

    def planner_path() -> str:
        return f"{planner.kind}->{active.kind}" if transitioned else active.kind

    while state.status == "running":
        remaining = state.overall_deadline_seconds - (monotonic() - started)
        state.remaining_seconds = remaining
        if remaining <= 0:
            _stop(state, "DEADLINE_EXCEEDED")
            return planner_path()
        if state.step >= state.max_steps:
            _stop(state, "MAX_STEPS")
            return planner_path()
        try:
            decision = parse_decision(active.decide(state))
        except (TimeoutError, MalformedPlannerOutput) as exc:
            if fallback is not None and active is planner:
                label = "timeout" if isinstance(exc, TimeoutError) else "malformed output"
                state.errors.append(
                    f"LLM planner {label}; falling back to heuristic: {exc}"
                )
                record_event(
                    "planner_fallback",
                    {
                        "from": planner.kind,
                        "to": fallback.kind,
                        "reason": label,
                        "error": str(exc),
                    },
                )
                active = fallback
                transitioned = True
                continue
            if isinstance(exc, TimeoutError):
                state.errors.append(str(exc))
                _stop(state, "PLANNER_TIMEOUT")
            else:
                state.errors.append(f"malformed planner output: {exc}")
                _stop(state, "MALFORMED_PLANNER_OUTPUT")
            return planner_path()
        state.step += 1
        state.decisions.append(decision)
        state.last_decision = decision
        if decision.hypothesis not in state.investigated_hypotheses:
            state.investigated_hypotheses.append(decision.hypothesis)
        for question in decision.open_questions:
            if question not in state.open_questions:
                state.open_questions.append(question)
        if decision.action in {"finish", "escalate"}:
            _stop(state, _map_stop_reason(decision))
            return planner_path()
        batch = executor.execute_decision(decision, state, ctx, remaining_seconds=remaining)
        state.observations.extend(batch)
        _ingest_evidence(state, batch)
        if monotonic() - started >= state.overall_deadline_seconds:
            _stop(state, "DEADLINE_EXCEEDED")
            return planner_path()
        if batch and all(item.status == "duplicate" for item in batch):
            _stop(state, "UNRESOLVABLE")
            return planner_path()
    return planner_path()


def _ingest_evidence(state: AgentState, batch: list[ToolObservation]) -> None:
    seen = {(item.get("evidence_id"), item.get("headline")) for item in state.evidence}
    for observation in batch:
        if observation.status != "ok" or not isinstance(observation.payload, dict):
            continue
        for document in observation.payload.get("documents") or []:
            if not isinstance(document, dict):
                continue
            key = (document.get("evidence_id"), document.get("headline"))
            if key not in seen:
                state.evidence.append(document)
                seen.add(key)
        if observation.discarded_post_cutoff:
            state.errors.append(
                f"{observation.name} rejected {observation.discarded_post_cutoff} post-cutoff document(s)"
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
            call.model_dump() for decision in state.decisions for call in decision.tool_calls
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
