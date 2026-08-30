"""Export the three frozen heuristic investigations for the local console."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_console_case import run_case
from src.risk_state.provider import FrozenCaseProvider

TARGET = ROOT / "frontend" / "public" / "cases.json"


def export_cases(path: Path = TARGET) -> str:
    cases = [
        run_case(as_of_date, source="export").model_dump(mode="json")
        for as_of_date in sorted(FrozenCaseProvider().supported_dates)
    ]
    payload = {
        "schema_version": "investigation-console-bundle-v1",
        "cases": cases,
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(serialized, encoding="utf-8")
    return serialized


def main() -> int:
    export_cases()
    print(f"wrote {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
