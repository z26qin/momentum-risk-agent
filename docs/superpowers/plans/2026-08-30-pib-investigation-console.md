# PIB Investigation Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Forward-port PR #2's React investigation console, deterministic exports, loop playback, and local rerun onto the immutable-case runtime after PIA merges.

**Architecture:** A frozen Pydantic console contract serializes public agent results. One deterministic JSON file feeds the React app, while a Vite-only local API runs the same heuristic orchestration for supported dates.

**Tech Stack:** Python 3.11–3.14, Pydantic 2, pytest, React 19, TypeScript, Vite, Tailwind CSS, oxlint.

**Spec:** `docs/superpowers/specs/2026-08-30-pr2-forward-port-design.md`

## Global Constraints

- Start from `main` only after PIA merges.
- Use BDD-style observable scenarios and only necessary tests.
- The frontend displays agent-owned facts; it never computes risk or probability.
- Browser code never receives `DEEPSEEK_API_KEY`.
- Keep one generated fixture file: `frontend/public/cases.json`.

---

### Task 1: Frozen console contract and serializer

**Files:**
- Create: `src/agent/console_case.py`
- Create: `tests/agent/test_console_case.py`

**Interfaces:**
- Produces: `build_console_case(result: OrchestratedRunResult, case: InvestigationCase, *, source: Literal["export", "live"], elapsed_seconds: float) -> ConsoleCase`.
- Produces: frozen, extra-forbidden `ConsoleCase`, `ConsoleRiskState`, `ConsoleTrace`, `ConsolePMNote`, and loop-event models.

- [ ] **Step 1: Add three BDD contract scenarios**

```python
@pytest.mark.parametrize("date", ["2026-05-29", "2024-01-05", "2020-03-24"])
def test_given_supported_case_when_serialized_then_console_preserves_agent_contract(date):
    assert console.date == date
    assert console.risk_state.score_is_probability is False
    assert console.trace.combined_stop == result.stop_reason
    assert console.note.citations == tuple(result.trace.calibrated["citations"])


def test_given_quiet_case_when_serialized_then_route_and_combine_events_exist_without_specialist():
    assert [event.kind for event in console.trace.loop] == ["route", "combine"]


def test_given_unknown_console_field_when_validated_then_contract_rejects_it():
    with pytest.raises(ValidationError):
        ConsoleCase.model_validate({**payload, "legacy_snapshot": {}})
```

- [ ] **Step 2: Implement the console schema and public-result mapping**

Map directly from `RiskState.model_dump(mode="json")`, orchestrator routing,
specialist decisions/observations, and calibrated buckets. Represent retry count
and planner fallback in observation/plan events. Do not import private synthesis
helpers or archived modules.

- [ ] **Step 3: Verify and commit**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q tests/agent/test_console_case.py
UV_CACHE_DIR=.uv-cache uv run pytest -q
git add src/agent/console_case.py tests/agent/test_console_case.py
git commit -m "feat: add frozen investigation console contract"
```

---

### Task 2: Deterministic export and local rerun scripts

**Files:**
- Create: `scripts/export_frontend_cases.py`
- Create: `scripts/run_console_case.py`
- Modify: `tests/agent/test_console_case.py`

**Interfaces:**
- `run_case(as_of_date: str, *, source: Literal["export", "live"]) -> ConsoleCase`.
- Export target: `frontend/public/cases.json`.

- [ ] **Step 1: Add export/rerun BDD scenarios**

```python
def test_given_three_frozen_cases_when_exported_twice_then_json_is_identical(tmp_path):
    first = export_cases(tmp_path / "cases.json")
    second = export_cases(tmp_path / "cases.json")
    assert first == second


def test_given_unsupported_date_when_console_run_requested_then_it_fails_explicitly():
    with pytest.raises(UnsupportedCaseError):
        run_case("2026-06-30", source="live")
```

- [ ] **Step 2: Implement scripts using `FrozenCaseProvider` and heuristic orchestration**

The export sorts cases by provider-supported date, sets volatile elapsed time to
zero for deterministic output, and writes via UTF-8 JSON. The rerun script prints
one model JSON and returns exit 2 for unsupported cases.

- [ ] **Step 3: Verify and commit**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q tests/agent/test_console_case.py
UV_CACHE_DIR=.uv-cache uv run python scripts/export_frontend_cases.py
UV_CACHE_DIR=.uv-cache uv run python scripts/run_console_case.py 2026-05-29
git add scripts/export_frontend_cases.py scripts/run_console_case.py tests/agent/test_console_case.py frontend/public/cases.json
git commit -m "feat: export and rerun console cases"
```

---

### Task 3: React console shell and immutable state/note panels

**Files:**
- Create: `frontend/package.json`, `frontend/package-lock.json`, TypeScript/Vite/Tailwind configs, and `frontend/index.html`
- Create: `frontend/src/data/types.ts`, `frontend/src/data/cases.ts`
- Create: `frontend/src/components/RiskStatePanel.tsx`
- Create: `frontend/src/components/PMNote.tsx`
- Create: `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/index.css`

**Interfaces:** TypeScript `CaseData` mirrors the serialized Pydantic aliases exactly.

- [ ] **Step 1: Port the PR #2 visual shell while replacing legacy field types**

Use `risk_state.market_regime`, `mechanical_unwind_state`, triggered signals,
mechanisms, book metrics, theme cluster, and severity directly. PMNote renders
all calibrated sections plus citations. Fetch `/cases.json` once; do not keep a
second generated source copy.

- [ ] **Step 2: Install, lint, and build**

```bash
cd frontend
npm ci
npm run lint
npm run build
```

- [ ] **Step 3: Commit the UI shell**

```bash
git add frontend
git commit -m "feat: add immutable risk investigation console"
```

---

### Task 4: Loop playback and Vite live rerun

**Files:**
- Create: `frontend/src/components/InvestigationTrace.tsx`
- Create: `frontend/src/data/playback.ts`
- Create: `frontend/src/hooks/useLoopPlayback.ts`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/src/data/types.ts`

**Interfaces:** `POST /api/run/:as_of_date -> ConsoleCase`; playback consumes `trace.loop` in order.

- [ ] **Step 1: Implement route/plan/observe/stop/combine playback**

Port PR #2's controls and animation state. Render observation status, attempts,
discarded post-cutoff count, planner fallback, and stop reason without deriving
new state.

- [ ] **Step 2: Implement the local Vite API with strict date validation**

Match only `YYYY-MM-DD`, spawn `.venv/bin/python scripts/run_console_case.py
<date>` with `execFile`, `cwd` set to the repo root, a 45-second timeout, and an
8 MiB output cap. Return JSON errors with HTTP 400 for invalid dates and 500 for
subprocess failures. Never pass environment values to browser JavaScript.

- [ ] **Step 3: Verify frontend behavior**

```bash
cd frontend
npm run lint
npm run build
npm run dev
```

Smoke-check each case selection, playback controls, and one rerun per supported
date. Confirm the quiet case has no specialist tool events.

- [ ] **Step 4: Commit live playback**

```bash
git add frontend
git commit -m "feat: replay and rerun investigation loops"
```

---

### Task 5: PIB acceptance and supersede PR #2

**Files:**
- Modify: `README.md`
- Create: `frontend/README.md`
- Modify: `docs/demo.md`

- [ ] **Step 1: Document console setup, export, playback, and rerun**

Document `npm ci`, `npm run sync-cases`, `npm run dev`, supported cases, and the
heuristic-only local API security boundary.

- [ ] **Step 2: Run full acceptance**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q
UV_CACHE_DIR=.uv-cache uv run python scripts/export_frontend_cases.py
cp frontend/public/cases.json /tmp/cases-first.json
UV_CACHE_DIR=.uv-cache uv run python scripts/export_frontend_cases.py
cmp /tmp/cases-first.json frontend/public/cases.json
cd frontend && npm ci && npm run lint && npm run build
git diff --check origin/main...HEAD
```

- [ ] **Step 3: Commit docs and open PIB**

```bash
git add README.md frontend/README.md docs/demo.md
git commit -m "docs: add investigation console workflow"
git push -u origin feat/pib-investigation-console
gh pr create --base main --head feat/pib-investigation-console \
  --title "PIB: Add investigation console"
```

- [ ] **Step 4: Close PR #2 after PIB merges**

Comment on PR #2 with links to merged PIA and PIB, then close it without merging.
