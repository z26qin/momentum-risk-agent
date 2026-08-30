"""Providers for deterministic investigation cases."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from src.risk_state.models import InvestigationCase

DEFAULT_CASES_DIR = Path(__file__).resolve().parents[2] / "data" / "demo_cases"


class UnsupportedCaseError(LookupError):
    pass


class CaseProvider(Protocol):
    def load(self, as_of_date: str) -> InvestigationCase:
        ...


class FrozenCaseProvider:
    def __init__(self, root: Path = DEFAULT_CASES_DIR) -> None:
        self.root = Path(root)

    @property
    def supported_dates(self) -> tuple[str, ...]:
        if not self.root.is_dir():
            return ()
        return tuple(
            path.parent.name
            for path in sorted(self.root.glob("*/case.json"))
            if path.is_file()
        )

    def load(self, as_of_date: str) -> InvestigationCase:
        requested = str(as_of_date).strip()
        if requested not in self.supported_dates:
            supported = ", ".join(self.supported_dates) or "none"
            raise UnsupportedCaseError(
                f"unsupported demo date {requested!r}; supported dates: {supported}"
            )
        path = self.root / requested / "case.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        return InvestigationCase.model_validate(payload)
