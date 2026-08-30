# Investigation console

This local React console displays agent-owned facts from the frozen console
contract. It never computes risk or receives a `DEEPSEEK_API_KEY`.

From the repository root:

```bash
uv sync --locked
uv run python scripts/export_frontend_cases.py
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173` and select one of the three supported dates:
`2020-03-24`, `2024-01-05`, or `2026-05-29`.

- `npm run sync-cases` regenerates the single deterministic fixture at
  `public/cases.json`.
- Playback consumes `trace.loop` in Python-defined order and displays route,
  plan, observation, retry/fallback, stop, and combine state.
- `RE-RUN AGENT` uses the Vite development server's local POST endpoint. It
  validates the date, runs `.venv/bin/python scripts/run_console_case.py`, and
  applies a 45-second subprocess timeout.
- The local endpoint is heuristic-only and is not a production service.

Validation commands:

```bash
npm run lint
npm run build
```
