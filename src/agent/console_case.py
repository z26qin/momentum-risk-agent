"""Frozen, public serialization contract for the investigation console."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.agent.orchestrator import OrchestratedRunResult
from src.risk_state.models import (
    BookState,
    InvestigationCase,
    MechanismStates,
    SeverityState,
)


class ConsoleModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConsoleRiskState(ConsoleModel):
    schema_version: Literal["risk-state-v1"]
    as_of_date: str
    assessment_cutoff: str
    comparison_date: str | None = None
    market_regime: str
    mechanical_unwind_state: str
    total_signal_count: int
    monitoring_trigger_count: int
    triggered_signals: tuple[str, ...]
    structural_flags: tuple[str, ...]
    mechanisms: MechanismStates
    triggered_mechanisms: tuple[str, ...]
    unconfirmed_mechanisms: tuple[str, ...]
    book: BookState
    theme_cluster: tuple[str, ...]
    severity: SeverityState


class ConsoleLoopEvent(ConsoleModel):
    sequence: int = Field(ge=1)
    kind: Literal["route", "plan", "observe", "stop", "combine"]
    specialist: str | None = None
    action: str | None = None
    hypothesis: str | None = None
    reason: str | None = None
    planner_kind: str | None = None
    planner_fallback: bool = False
    tool_call_id: str | None = None
    tool_name: str | None = None
    status: str | None = None
    attempts: int | None = Field(default=None, ge=1)
    discarded_post_cutoff: int = Field(default=0, ge=0)
    error_type: str | None = None
    error_message: str | None = None
    stop_reason: str | None = None
    specialists: tuple[str, ...] = ()


class ConsoleSpecialistTrace(ConsoleModel):
    name: str
    planner_kind: str
    planner_fallback: bool
    stop_reason: str
    steps: int = Field(ge=0)


class ConsoleTrace(ConsoleModel):
    combined_stop: str
    quiet: bool
    schedule: str
    routed_specialists: tuple[str, ...]
    specialists: tuple[ConsoleSpecialistTrace, ...]
    loop: tuple[ConsoleLoopEvent, ...]
    errors: tuple[str, ...]


class ConsolePMNote(ConsoleModel):
    current_read: str
    observed: tuple[str, ...]
    inferred: tuple[str, ...]
    contradicted: tuple[str, ...]
    not_confirmed: tuple[str, ...]
    citations: tuple[str, ...]
    what_changed: str
    next_useful_check: str
    score_is_probability: Literal[False] = False


class ConsoleCase(ConsoleModel):
    schema_version: Literal["investigation-console-v1"] = "investigation-console-v1"
    date: str
    source: Literal["export", "live"]
    elapsed_seconds: float = Field(ge=0)
    risk_state: ConsoleRiskState
    trace: ConsoleTrace
    note: ConsolePMNote


def build_console_case(
    result: OrchestratedRunResult,
    case: InvestigationCase,
    *,
    source: Literal["export", "live"],
    elapsed_seconds: float,
) -> ConsoleCase:
    """Map public runtime results into the browser-safe console contract."""

    risk = result.risk_state
    if risk != case.risk_state:
        raise ValueError("orchestrated result does not match the supplied case")

    risk_payload = risk.model_dump(mode="json")
    risk_payload.update(
        monitoring_trigger_count=risk.monitoring_trigger_count,
        triggered_mechanisms=risk.triggered_mechanisms,
        unconfirmed_mechanisms=risk.unconfirmed_mechanisms,
    )
    calibrated = result.trace.calibrated
    note = ConsolePMNote(
        current_read=str(calibrated.get("current_read") or ""),
        observed=_strings(calibrated.get("observed")),
        inferred=_strings(calibrated.get("inferred")),
        contradicted=_strings(calibrated.get("contradicted")),
        not_confirmed=_strings(calibrated.get("not_confirmed")),
        citations=_strings(calibrated.get("citations")),
        what_changed=str(calibrated.get("what_changed") or ""),
        next_useful_check=str(calibrated.get("next_useful_check") or ""),
        score_is_probability=False,
    )
    return ConsoleCase(
        date=result.as_of_date,
        source=source,
        elapsed_seconds=max(0.0, float(elapsed_seconds)),
        risk_state=ConsoleRiskState.model_validate(risk_payload),
        trace=_build_trace(result),
        note=note,
    )


def _build_trace(result: OrchestratedRunResult) -> ConsoleTrace:
    events: list[ConsoleLoopEvent] = []

    def append(kind: str, **kwargs: Any) -> None:
        events.append(ConsoleLoopEvent(sequence=len(events) + 1, kind=kind, **kwargs))

    append(
        "route",
        action="skip" if not result.spawned else "spawn",
        reason="NO_INVESTIGATION_NEEDED"
        if result.routing.get("quiet")
        else "deterministic_mechanisms",
        specialists=result.spawned,
    )
    specialists: list[ConsoleSpecialistTrace] = []
    for name in result.spawned:
        specialist = result.specialist_results.get(name)
        if specialist is None:
            failure = next(
                (
                    item
                    for item in result.trace.decisions
                    if item.get("actor") == name
                    and item.get("action") in {"failed", "skipped"}
                ),
                {},
            )
            append(
                "stop",
                specialist=name,
                action=str(failure.get("action") or "failed"),
                reason=str(failure.get("error") or failure.get("reason") or "UNRESOLVABLE"),
                stop_reason=str(failure.get("reason") or "UNRESOLVABLE"),
            )
            continue

        trace = specialist.trace
        fallback = "->" in trace.planner_kind
        specialists.append(
            ConsoleSpecialistTrace(
                name=name,
                planner_kind=trace.planner_kind,
                planner_fallback=fallback,
                stop_reason=trace.stop_reason,
                steps=len(trace.decisions),
            )
        )
        observations = {
            str(item.get("tool_call_id") or ""): item for item in trace.tool_results
        }
        for decision in trace.decisions:
            append(
                "plan",
                specialist=name,
                action=str(decision.get("action") or ""),
                hypothesis=str(decision.get("hypothesis") or ""),
                reason=str(decision.get("reason") or ""),
                planner_kind=trace.planner_kind,
                planner_fallback=fallback,
            )
            for call in decision.get("tool_calls") or []:
                call_id = str(call.get("id") or "")
                observation = observations.get(call_id, {})
                append(
                    "observe",
                    specialist=name,
                    tool_call_id=call_id,
                    tool_name=str(call.get("name") or observation.get("name") or ""),
                    status=str(observation.get("status") or "unavailable"),
                    attempts=max(1, int(observation.get("attempts") or 1)),
                    discarded_post_cutoff=max(
                        0, int(observation.get("discarded_post_cutoff") or 0)
                    ),
                    error_type=observation.get("error_type"),
                    error_message=observation.get("error_message"),
                )
        append(
            "stop",
            specialist=name,
            planner_kind=trace.planner_kind,
            planner_fallback=fallback,
            stop_reason=trace.stop_reason,
        )
    append("combine", stop_reason=result.stop_reason, specialists=result.spawned)
    return ConsoleTrace(
        combined_stop=result.stop_reason,
        quiet=bool(result.routing.get("quiet")),
        schedule=str(result.routing.get("schedule") or ""),
        routed_specialists=result.spawned,
        specialists=tuple(specialists),
        loop=tuple(events),
        errors=tuple(result.trace.errors),
    )


def _strings(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(str(item) for item in value)
