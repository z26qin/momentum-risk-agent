"""CLI for the planner/executor investigation agent.

Example:

    uv run python scripts/run_agent.py \\
      --as-of-date 2026-05-29 \\
      --verbose
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent.loop import MAX_STEPS, OVERALL_DEADLINE_SECONDS, run_agent
from src.mvp.config import HISTORICAL_EXAMPLE_DATE
from src.mvp.hermes_monitor import (
    MissingCachedDataError,
    default_compare_to_date,
    require_cached_inputs,
    run_compact_assessment,
)
from src.utils.io import REPO_ROOT, load_dotenv_if_present, write_json


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Investigate an already-computed momentum risk state with an LLM "
            "planner and a deterministic tool executor. Not a trading agent."
        )
    )
    parser.add_argument("--as-of-date", default=HISTORICAL_EXAMPLE_DATE, metavar="YYYY-MM-DD")
    parser.add_argument("--compare-to-date", default=None, metavar="YYYY-MM-DD")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    parser.add_argument(
        "--deadline-seconds",
        type=float,
        default=OVERALL_DEADLINE_SECONDS,
    )
    parser.add_argument(
        "--planner",
        choices=("auto", "llm", "heuristic"),
        default="auto",
        help="auto uses DeepSeek when DEEPSEEK_API_KEY is set, else heuristic",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--save-trace",
        default=None,
        help="Optional JSON path for the audit trace",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    load_dotenv_if_present()
    try:
        require_cached_inputs()
        compare_to = args.compare_to_date
        assessment = run_compact_assessment(
            as_of_date=args.as_of_date,
            compare_to_date=compare_to or default_compare_to_date(args.as_of_date),
        )
        prior = None
        if args.compare_to_date:
            prior = run_compact_assessment(as_of_date=args.compare_to_date)
    except MissingCachedDataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    use_llm = None
    if args.planner == "llm":
        use_llm = True
    elif args.planner == "heuristic":
        use_llm = False

    result = run_agent(
        as_of_date=args.as_of_date,
        max_steps=args.max_steps,
        verbose=args.verbose,
        overall_deadline_seconds=args.deadline_seconds,
        risk_state=assessment,
        prior_state=prior,
        use_llm=use_llm,
    )
    if not args.verbose:
        print(result.report)
    if args.save_trace:
        path = Path(args.save_trace)
        if not path.is_absolute():
            path = REPO_ROOT / path
        write_json(path, json.loads(result.trace.model_dump_json()))
        print(f"# wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
