# PR #2 Forward-Port Design

## Goal

Forward-port all user-facing behavior from PR #2 onto the focused immutable-case
agent architecture already merged by PR #3, without restoring legacy monitor
APIs, mutable risk dictionaries, processed-data adapters, or generated reports.

## Delivery shape

Delivery is split into two sequential pull requests:

1. **PIA — Agent resilience and citations.** Add PM citations, one bounded retry
   for transient tool failures, and one LLM-to-heuristic runtime fallback.
2. **PIB — Investigation console.** Add the React console, deterministic case
   export, loop playback, and local live rerun on top of PIA's trace contract.

PIB starts from `main` only after PIA is merged. PR #2 remains a historical
reference and is closed as superseded after both forward-port PRs merge.

## PIA behavior

### Citations

`src/agent/synthesis.py` owns citation construction. A citation is emitted only
for cutoff-valid evidence ingested into `AgentState.evidence` and is rendered as
`[evidence_id] YYYY-MM-DD headline`. Citations are stable, deduplicated, and
present once in single-specialist and combined PM notes. Missing citations render
as `None`; post-cutoff documents never appear in Observed or Citations.

### Tool retry

The executor makes at most one additional attempt after a handler exception or
per-tool timeout. Unknown tools, invalid arguments, semantic duplicates, cutoff
rejection, and overall-deadline exhaustion are never retried. Both attempts share
the original tool timeout and investigation wall-clock budget. The final
`ToolObservation` records `attempts`; success after retry remains `ok`, while a
second failure preserves the existing isolated error/timeout status.

### Planner fallback

When the active planner kind starts with `llm`, a `TimeoutError` or
`MalformedPlannerOutput` switches that specialist once to its matching
`HeuristicPlanner`. The failed LLM call consumes wall-clock time but not an agent
step. The transition is recorded in errors and in `planner_kind` as
`llm-<focus>->heuristic-<focus>`. Scripted and heuristic planners continue to
fail closed. `--planner llm` still rejects an empty API key before orchestration.

## PIB behavior

### Console contract

`src/agent/console_case.py` maps only `InvestigationCase`, immutable `RiskState`,
`OrchestratedRunResult`, and public trace/calibrated fields into frozen,
extra-forbidden Pydantic console models. It does not read archived data or legacy
snapshots and does not recompute risk.

### Export and rerun

`scripts/export_frontend_cases.py` loads the three supported dates through
`FrozenCaseProvider`, runs heuristic orchestration, and deterministically writes
one canonical file: `frontend/public/cases.json`. `scripts/run_console_case.py`
accepts one supported date and prints one console case as JSON. The Vite-only
`POST /api/run/:as_of_date` proxy invokes that script with a 45-second timeout.
The browser never receives `DEEPSEEK_API_KEY`; console reruns are heuristic.

### React console

The console provides three panels: immutable RiskState, investigation trace
playback, and calibrated PM note with citations. It visualizes route, plan,
observe, retry/fallback, stop, and combine events. TypeScript mirrors the Python
console schema and never derives triggers, mechanism statuses, severity, or
probabilities.

## Constraints

- Exactly three runtime cases remain supported: `2026-05-29`, `2024-01-05`,
  and `2020-03-24`.
- Python runtime dependencies remain Pydantic only.
- The maximum loop length remains six steps and the overall deadline remains
  shared across planners, retries, tools, and specialists.
- Risk scores are relative severity and `score_is_probability` is always false.
- Tests follow BDD-style observable scenarios and are limited to behaviors that
  protect trust boundaries or user-visible flows.
- Active Python imports must not load archived modules, pandas, NumPy, PyArrow,
  or scikit-learn.

## Acceptance

PIA must preserve all three demo routes and pass the Python suite. PIB must pass
the Python suite, `npm run lint`, and `npm run build`; exporting twice must yield
identical JSON; each supported date must replay and rerun successfully. After
both PRs merge, PR #2 is closed with links to PIA and PIB.
