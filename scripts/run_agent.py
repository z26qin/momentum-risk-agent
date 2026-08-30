"""CLI for the focused orchestrated investigation agent."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import ValidationError

from src.agent.loop import MAX_STEPS, OVERALL_DEADLINE_SECONDS
from src.agent.orchestrator import run_orchestrated_investigation
from src.risk_state.provider import FrozenCaseProvider, UnsupportedCaseError

DEFAULT_CASE_DATE = "2026-05-29"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Investigate an immutable deterministic momentum-risk demo case."
    )
    parser.add_argument("--as-of-date", default=DEFAULT_CASE_DATE, metavar="YYYY-MM-DD")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    parser.add_argument(
        "--deadline-seconds", type=float, default=OVERALL_DEADLINE_SECONDS
    )
    parser.add_argument(
        "--planner",
        choices=("auto", "llm", "heuristic"),
        default="auto",
        help="auto uses DeepSeek when DEEPSEEK_API_KEY is set, else heuristic",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--save-trace", default=None, help="Optional JSON trace path")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        case = FrozenCaseProvider().load(args.as_of_date)
    except (UnsupportedCaseError, ValidationError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    use_llm = True if args.planner == "llm" else False if args.planner == "heuristic" else None
    result = run_orchestrated_investigation(
        case,
        max_steps=args.max_steps,
        overall_deadline_seconds=args.deadline_seconds,
        use_llm=use_llm,
    )
    print(result.report)
    if args.verbose:
        print(
            f"# stop={result.stop_reason} spawned={list(result.spawned)}",
            file=sys.stderr,
        )
    if args.save_trace:
        path = Path(args.save_trace)
        if not path.is_absolute():
            path = ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.trace.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(f"# wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
