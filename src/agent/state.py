"""Mutable investigation memory around an immutable deterministic case."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.agent.models import AgentDecision, ToolObservation
from src.risk_state.models import InvestigationCase, RiskState


@dataclass
class AgentState:
    case: InvestigationCase
    run_id: str
    max_steps: int
    overall_deadline_seconds: float
    remaining_seconds: float
    observations: list[ToolObservation] = field(default_factory=list)
    decisions: list[AgentDecision] = field(default_factory=list)
    executed_keys: set[str] = field(default_factory=set)
    investigated_hypotheses: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    step: int = 0
    status: str = "running"
    stop_reason: str | None = None
    last_decision: AgentDecision | None = None
    focus: str | None = None

    @property
    def risk_state(self) -> RiskState:
        return self.case.risk_state

    @property
    def as_of_date(self) -> str:
        return self.risk_state.as_of_date.isoformat()

    @property
    def assessment_cutoff(self) -> str:
        return self.risk_state.assessment_cutoff.isoformat()
