"""Print one live console case as JSON. Used by the Vite /api/run proxy."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_EXPORT = Path(__file__).with_name("export_frontend_cases.py")
_SPEC = importlib.util.spec_from_file_location("export_frontend_cases", _EXPORT)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"cannot load {_EXPORT}")
_EXPORT_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_EXPORT_MOD)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: run_console_case.py <case_id>", file=sys.stderr)
        return 2
    payload = _EXPORT_MOD.run_case(args[0], source="live")
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
