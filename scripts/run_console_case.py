"""Run one supported heuristic case and emit the console JSON contract."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from src.agent.console_case import ConsoleCase, build_console_case
from src.agent.orchestrator import run_orchestrated_investigation
from src.risk_state.provider import FrozenCaseProvider, UnsupportedCaseError


def run_case(
    as_of_date: str, *, source: Literal["export", "live"]
) -> ConsoleCase:
    case = FrozenCaseProvider().load(as_of_date)
    started = time.perf_counter()
    result = run_orchestrated_investigation(case, use_llm=False)
    elapsed = 0.0 if source == "export" else time.perf_counter() - started
    return build_console_case(
        result,
        case,
        source=source,
        elapsed_seconds=elapsed,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("as_of_date", metavar="YYYY-MM-DD")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        console = run_case(args.as_of_date, source="live")
    except (UnsupportedCaseError, ValidationError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(console.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
