"""Read-only context handed to every registered tool."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.utils.io import DEFAULT_PROCESSED_DIR


@dataclass(frozen=True)
class ToolContext:
    as_of_date: str
    assessment_cutoff: str
    risk_state: Mapping[str, Any]
    prior_state: Mapping[str, Any] | None = None
    processed_dir: Path = DEFAULT_PROCESSED_DIR

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(dict(self.risk_state))
