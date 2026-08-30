# PIA Agent Resilience and Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Forward-port citations, one transient tool retry, and one DeepSeek-to-heuristic fallback onto the immutable-case agent runtime.

**Architecture:** Extend the existing synthesis, executor, and planner loop at their current ownership boundaries. Preserve immutable `InvestigationCase` input, specialist allowlists, shared deadlines, and validated `AgentDecision` output.

**Tech Stack:** Python 3.11–3.14, Pydantic 2, pytest, uv.

**Spec:** `docs/superpowers/specs/2026-08-30-pr2-forward-port-design.md`

## Global Constraints

- Use BDD-style Given/When/Then scenarios; add only tests needed to protect observable behavior.
- Do not restore `src/agent/report.py`, legacy monitor packages, mutable risk dictionaries, or processed-data adapters.
- Keep `MAX_STEPS = 6`, the shared overall deadline, specialist isolation, and `score_is_probability=False`.
- Python runtime dependencies remain Pydantic only.

---

### Task 1: Citation synthesis

**Files:**
- Modify: `src/agent/synthesis.py`
- Modify: `tests/agent/test_executor_failures.py`
- Modify: `tests/agent/test_orchestrator.py`

**Interfaces:**
- Consumes: `AgentState.evidence: list[dict[str, Any]]` after cutoff filtering.
- Produces: `calibrated_buckets(...)["citations"]: list[str]` and one `Citations:` PM-note section.

- [ ] **Step 1: Add the minimal BDD scenarios**

Add one cutoff scenario and one combined-synthesis scenario:

```python
def test_given_cutoff_valid_and_future_docs_when_synthesized_then_only_valid_doc_is_cited():
    # Given one valid and one post-cutoff evidence document
    # When the agent finishes
    # Then Observed and Citations contain [OK], never FUTURE
    assert "Citations:" in result.report
    assert "[OK]" in result.report
    assert "FUTURE" not in result.report


def test_given_dual_specialists_when_combined_then_citations_are_deduplicated_once():
    assert result.report.count("Citations:") == 1
    assert result.trace.calibrated["citations"].count(expected) == 1
```

- [ ] **Step 2: Implement citation construction and rendering**

Add focused helpers in `synthesis.py`:

```python
def _cite_document(document: Mapping[str, Any]) -> str:
    evidence_id = str(document.get("evidence_id") or "").strip()
    published = str(document.get("published_at") or "").strip()[:10]
    headline = str(document.get("headline") or "").strip()[:160]
    return " ".join(
        part for part in (f"[{evidence_id}]" if evidence_id else "", published, headline)
        if part
    )


def _citations(state: AgentState) -> list[str]:
    return _unique(_cite_document(doc) for doc in state.evidence if isinstance(doc, dict))
```

Include `citations` in specialist and combined buckets and render it between
`Not confirmed` and `Investigation path`. Prefix the first evidence headline in
Observed with the same citation label.

- [ ] **Step 3: Verify the citation scenarios and regression suite**

Run:

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q \
  tests/agent/test_executor_failures.py \
  tests/agent/test_orchestrator.py
UV_CACHE_DIR=.uv-cache uv run pytest -q
```

- [ ] **Step 4: Commit the vertical slice**

```bash
git add src/agent/synthesis.py tests/agent/test_executor_failures.py tests/agent/test_orchestrator.py
git commit -m "feat: add cutoff-safe PM citations"
```

---

### Task 2: Bounded transient tool retry

**Files:**
- Modify: `src/agent/models.py`
- Modify: `src/agent/executor.py`
- Modify: `src/tools/registry.py`
- Modify: `tests/agent/test_executor_failures.py`

**Interfaces:**
- Produces: `ToolObservation.attempts: int = 1`.
- Produces: `TOOL_RETRIES = 1` and executor behavior bounded by the existing deadline.

- [ ] **Step 1: Add three table-driven BDD scenarios**

```python
@pytest.mark.parametrize("failure", [RuntimeError("transient"), TimeoutError("slow")])
def test_given_transient_first_failure_when_budget_remains_then_tool_retries_once(failure):
    assert calls["count"] == 2
    assert result.observations[0].status == "ok"
    assert result.observations[0].attempts == 2


def test_given_invalid_or_duplicate_call_when_executed_then_it_is_not_retried():
    assert calls["count"] <= 1


def test_given_two_handler_failures_when_executed_then_final_error_is_isolated():
    assert calls["count"] == 2
    assert result.observations[0].status == "error"
    assert result.observations[0].attempts == 2
```

- [ ] **Step 2: Implement one shared-budget retry**

Add `attempts` to `ToolObservation`, `TOOL_RETRIES = 1` to the registry, and
replace each parallel submission with `_run_with_retry`. Return
`(payload, discarded, elapsed_ms, attempts)` and subtract elapsed time from the
remaining budget before a second attempt. Do not retry precheck observations.

```python
for attempt in range(1, TOOL_RETRIES + 2):
    timeout = min(spec.timeout_seconds, max(0.0, leftover))
    if timeout <= 0:
        break
    try:
        payload, discarded, elapsed_ms = self._run_one(spec, ctx, parsed, timeout)
        return payload, discarded, elapsed_ms, attempt
    except (TimeoutError, Exception):
        leftover -= self.monotonic() - started
        if attempt > TOOL_RETRIES or leftover <= 0:
            raise
```

Use a dedicated internal exception carrying `attempts` when the final attempt
fails so the error observation retains the count.

- [ ] **Step 3: Verify retry behavior and deadlines**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q tests/agent/test_executor_failures.py
UV_CACHE_DIR=.uv-cache uv run pytest -q
```

- [ ] **Step 4: Commit the vertical slice**

```bash
git add src/agent/models.py src/agent/executor.py src/tools/registry.py tests/agent/test_executor_failures.py
git commit -m "feat: retry transient tool failures once"
```

---

### Task 3: LLM-to-heuristic runtime fallback

**Files:**
- Modify: `src/agent/loop.py`
- Modify: `tests/agent/test_executor_failures.py`
- Modify: `tests/agent/test_case_runtime.py`

**Interfaces:**
- Consumes: planner `kind`, specialist `focus`, and existing exceptions.
- Produces: final `planner_kind` transition string and fallback audit error.

- [ ] **Step 1: Add minimal fallback scenarios**

```python
@pytest.mark.parametrize("failure", [TimeoutError("down"), "not-json"])
def test_given_active_llm_failure_when_specialist_has_budget_then_it_falls_back_once(failure):
    assert result.stop_reason != "MALFORMED_PLANNER_OUTPUT"
    assert result.planner_kind == "llm-kl_crowding->heuristic-kl_crowding"
    assert any("falling back to heuristic" in error for error in result.state.errors)


def test_given_scripted_planner_failure_when_run_then_it_still_fails_closed():
    assert result.stop_reason == "MALFORMED_PLANNER_OUTPUT"
```

Keep the existing CLI scenario asserting that explicit LLM mode with an empty
key exits 2.

- [ ] **Step 2: Implement a one-way planner transition**

Make `_run_loop` return the final planner path. Create a fallback only when
`selected.kind.startswith("llm")`:

```python
fallback = HeuristicPlanner(focus=focus) if selected.kind.startswith("llm") else None
planner_path = _run_loop(..., planner=selected, fallback=fallback)
```

Inside `_run_loop`, catch `TimeoutError` and `MalformedPlannerOutput`; switch
once, append an audit error, and continue without incrementing `state.step`.
Return `f"{selected.kind}->{active.kind}"` after a transition and pass it into
the result and trace.

- [ ] **Step 3: Verify fallback and full agent behavior**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q \
  tests/agent/test_executor_failures.py \
  tests/agent/test_case_runtime.py
UV_CACHE_DIR=.uv-cache uv run pytest -q
```

- [ ] **Step 4: Commit the vertical slice**

```bash
git add src/agent/loop.py tests/agent/test_executor_failures.py tests/agent/test_case_runtime.py
git commit -m "feat: fall back after runtime LLM failure"
```

---

### Task 4: PIA acceptance and pull request

**Files:**
- Modify: `README.md`
- Modify: `docs/architecture.md`

**Interfaces:** Documents the delivered runtime behavior for PIB and users.

- [ ] **Step 1: Document citations, retry, and fallback semantics**

Update the trust-boundary and DeepSeek sections with the exact retry/fallback
limits and citation source rule.

- [ ] **Step 2: Run acceptance commands**

```bash
UV_CACHE_DIR=.uv-cache uv run pytest -q
UV_CACHE_DIR=.uv-cache uv run python scripts/run_agent.py --as-of-date 2026-05-29 --planner heuristic
UV_CACHE_DIR=.uv-cache uv run python scripts/run_agent.py --as-of-date 2024-01-05 --planner heuristic
UV_CACHE_DIR=.uv-cache uv run python scripts/run_agent.py --as-of-date 2020-03-24 --planner heuristic
git diff --check origin/main...HEAD
```

Confirm May routes crowding, January routes nobody, March routes recovery,
citations contain only bundled cutoff-valid evidence, and the worktree is clean.

- [ ] **Step 3: Commit documentation**

```bash
git add README.md docs/architecture.md
git commit -m "docs: describe resilient evidence investigation"
```

- [ ] **Step 4: Push and open PIA**

```bash
git push -u origin feat/pia-agent-resilience-citations
gh pr create --base main --head feat/pia-agent-resilience-citations \
  --title "PIA: Add agent resilience and citations"
```

PIA must merge before executing PIB.
