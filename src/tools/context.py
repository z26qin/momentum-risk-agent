"""Read-only context handed to every registered tool."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.risk_state.models import InvestigationCase
from src.utils.io import DEFAULT_PROCESSED_DIR


@dataclass(frozen=True)
class ToolContext:
    as_of_date: str
    assessment_cutoff: str
    risk_state: Mapping[str, Any]
    prior_state: Mapping[str, Any] | None = None
    processed_dir: Path = DEFAULT_PROCESSED_DIR
    case: InvestigationCase | None = None

    @classmethod
    def from_case(cls, case: InvestigationCase) -> ToolContext:
        risk = case.risk_state.model_dump(mode="json")
        prior = case.prior_state.model_dump(mode="json") if case.prior_state else None
        return cls(
            as_of_date=case.risk_state.as_of_date.isoformat(),
            assessment_cutoff=case.risk_state.assessment_cutoff.isoformat(),
            risk_state=risk,
            prior_state=prior,
            case=case,
        )

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.risk_state))
