"""Mutable investigation memory around an immutable risk snapshot."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from src.agent.models import AgentDecision, ToolObservation


def fingerprint_risk_state(payload: Mapping[str, Any]) -> str:
    return json.dumps(dict(payload), sort_keys=True, default=str)


def freeze_risk_state(payload: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    copied = copy.deepcopy(dict(payload))
    return copied, fingerprint_risk_state(copied)


@dataclass
class AgentState:
    """Planner-visible investigation state. Risk metrics are stored privately."""

    as_of_date: str
    assessment_cutoff: str
    run_id: str
    max_steps: int
    overall_deadline_seconds: float
    remaining_seconds: float
    _risk_state: dict[str, Any]
    _risk_fingerprint: str
    prior_state: dict[str, Any] | None = None
    observations: list[ToolObservation] = field(default_factory=list)
    decisions: list[AgentDecision] = field(default_factory=list)
    executed_keys: set[str] = field(default_factory=set)
    investigated_hypotheses: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    step: int = 0
    status: str = "running"
    stop_reason: str | None = None
    consecutive_duplicate_steps: int = 0
    last_decision: AgentDecision | None = None
    focus: str | None = None

    @property
    def risk_state(self) -> dict[str, Any]:
        """Defensive copy. Callers cannot mutate the stored snapshot."""

        return copy.deepcopy(self._risk_state)

    def risk_fingerprint(self) -> str:
        return self._risk_fingerprint

    def assert_risk_unchanged(self) -> None:
        current = fingerprint_risk_state(self._risk_state)
        if current != self._risk_fingerprint:
            raise RuntimeError("invariant violated: deterministic risk state changed")
