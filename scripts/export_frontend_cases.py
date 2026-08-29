"""Export orchestrated investigations as the frontend CaseData JSON.

    uv run python scripts/export_frontend_cases.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent.console_case import build_console_case, compact_from_snapshot
from src.agent.orchestrator import run_orchestrated_investigation
from src.utils.io import REPO_ROOT
from tests.cases import leftover_quiet_risk, recovery_risk, semi_unwind_risk

SPECS = (
    {
        "id": "semi",
        "label": "Localized unwind",
        "horizon_days": 20,
        "fallback": semi_unwind_risk,
        "snapshot": REPO_ROOT / "outputs/snapshot_2026-05-29/structured_snapshot.json",
        "overlay": {},
    },
    {
        "id": "march2020",
        "label": "Recovery crash ref",
        "horizon_days": 20,
        "fallback": recovery_risk,
        "snapshot": REPO_ROOT / "data/evaluation/march_2020_reference/structured_snapshot.json",
        "overlay": {},
    },
    {
        "id": "quiet2024",
        "label": "Quiet control",
        "horizon_days": 20,
        "fallback": leftover_quiet_risk,
        "snapshot": REPO_ROOT
        / "outputs/quiet_control_example_risk_output/pm_risk_assessment_2024-01-05.json",
        "overlay": {"primary_driver": "crowded_unwind"},
    },
)
OUTPUTS = (
    REPO_ROOT / "frontend/public/cases.json",
    REPO_ROOT / "frontend/src/data/generated/cases.json",
)


def _run(spec: dict) -> dict:
    fallback = spec["fallback"]()
    risk = compact_from_snapshot(spec["snapshot"], fallback) if spec["snapshot"] else dict(fallback)
    risk.update(spec["overlay"])
    started = time.monotonic()
    result = run_orchestrated_investigation(
        as_of_date=str(risk.get("as_of_date") or fallback["as_of_date"]),
        risk_state=risk,
        use_llm=False,
    )
    elapsed = time.monotonic() - started
    return build_console_case(
        result,
        case_id=spec["id"],
        label=spec["label"],
        horizon_days=spec["horizon_days"],
        snapshot=spec["snapshot"],
        elapsed_seconds=round(elapsed, 2),
    )


def main() -> int:
    cases = [_run(spec) for spec in SPECS]
    text = json.dumps(cases, indent=2, ensure_ascii=False) + "\n"
    for path in OUTPUTS:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
