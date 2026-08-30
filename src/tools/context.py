"""Read-only context handed to every registered tool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.risk_state.models import InvestigationCase


@dataclass(frozen=True)
class ToolContext:
    case: InvestigationCase

    @classmethod
    def from_case(cls, case: InvestigationCase) -> ToolContext:
        return cls(case=case)

    @property
    def as_of_date(self) -> str:
        return self.case.risk_state.as_of_date.isoformat()

    @property
    def assessment_cutoff(self) -> str:
        return self.case.risk_state.assessment_cutoff.isoformat()

    @property
    def risk_state(self):
        return self.case.risk_state

    @property
    def prior_state(self):
        return self.case.prior_state

    def snapshot(self) -> dict[str, Any]:
        return self.case.risk_state.model_dump(mode="json")
