<p align="center">
  <a href="docs/methodology.md"><img src="https://img.shields.io/badge/Docs-methodology-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="#what-it-will-not-do"><img src="https://img.shields.io/badge/Status-Investigation%20agent%20MVP-orange?style=for-the-badge" alt="Investigation agent MVP"></a>
</p>

# Momentum-Risk-Agent

An investigation agent over a **deterministic** US equity momentum tail-risk monitor.

It answers:

> Given the current deterministic momentum risk state, what should I investigate next, which tools should I use, what evidence supports or contradicts each hypothesis, and when should I stop?

It does **not** trade, de-gross, or publish a crash probability.

This repository is a **new project** cloned from [`momentum-tail-risk-monitor`](https://github.com/z26qin/momentum-tail-risk-monitor). The quantitative engine, evidence cutoff, fail-closed behavior, and PM-facing calibration are preserved. The architectural upgrade is the investigation loop:

> **Model plans. Executor enforces invariants.**

---

## Original system

```text
deterministic monitor
        ↓
mostly fixed investigation workflow
        ↓
PM note
```

The original loop in `src/agent/heuristic.py` still exists (compatibility tests and notebook path). It chooses among a small, pre-programmed set of mechanism searches.

## New system

```text
deterministic monitor
        ↓
immutable RiskState
        ↓
AgentState
        ↓
LLM planner  →  structured AgentDecision
        ↓
deterministic executor  (allowlist, args, timeout, dedup, cutoff)
        ↓
validated tool observations
        ↓
AgentState update
        ↓
LLM planner
        ↓
...
        ↓
FINISH / ESCALATE  →  calibrated PM note + audit trace
```

The quantitative engine remains the source of truth. The agent investigates the state; it does not change it.

---

## What a PM sees

Frozen 2026-05-29 case — not a live call:

```text
Current read
Pressure is localized; available evidence does not establish a
book-wide unwind or recovery crash.

Observed:
- 1 / 4 deterministic signals triggered
- theme cluster: CIEN, COHR, LITE
- cluster exposure: CIEN, COHR, LITE

Inferred:
- Working hypothesis: localized crowded unwind

Against:
- Liquidity is still absorbing; shorts are not being squeezed.

Not confirmed:
- Broad forced deleveraging / financing stress

Investigation path:
1. localized crowded unwind · tools=['get_cluster_exposure', 'search_positioning', 'search_news']
2. forced deleveraging still unconfirmed · tools=['inspect_name']
3. STOP: EVIDENCE_SUFFICIENT

What changed:
- Deterministic snapshot already compared with 2026-04-30; this investigation did not recompute that delta.

Next useful check:
- Watch whether selling spreads outside the cluster.
```

Same rules on two other dates: [March 2020](outputs/march_2020_reference/pm_case_read.md) is a recovery-crash reference; [January 2024](outputs/quiet_control_2024/pm_case_read.md) should not escalate. Cross-case table: [`outputs/cross_case_comparison.md`](outputs/cross_case_comparison.md).

---

## Architecture

```text
                         ┌──────────── MVPConfig ────────────┐
                         │ as_of · compare_to · horizon · LLM │
                         └────────────────┬──────────────────┘
                                          ▼
                                   run_mvp() / compact assessment
                                          │
                                          ▼
                              Immutable risk snapshot
                                          │
                                          ▼
                    run_agent()  — hand-written loop, no LangGraph
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              ▼                           ▼                           ▼
     LLM / heuristic planner      deterministic executor        calibrated PM note
     structured AgentDecision     allowlisted read-only tools   + AgentRunTrace
```

There is no multi-agent framework. One planner, one executor, one bounded loop.

---

## Agent / tool contracts

All executable actions come through validated structured output (`src/agent/models.py`). Free-form model text is never parsed to decide what runs.

```python
class ToolCall(BaseModel):
    id: str
    name: str   # allowlisted by the executor, not by the prompt alone
    args: dict[str, Any]

class AgentDecision(BaseModel):
    action: Literal["call_tools", "finish", "escalate"]
    hypothesis: str
    reason: str
    tool_calls: list[ToolCall] = []
    final_assessment: str | None = None
    open_questions: list[str] = []
```

Read-only tools (`src/tools/`):

| Tool | Role |
|---|---|
| `get_book_state` | Deterministic current PM-book risk snapshot |
| `get_factor_state` | UMD / regime / recovery state |
| `get_cluster_exposure` | Concentration / theme / long-short pressure |
| `compare_prior_state` | Compare with a previously loaded compact assessment |
| `search_news` | Point-in-time public news (GDELT + frozen packs) |
| `search_positioning` | Crowding / positioning *proxies* from bundled sources |
| `search_filings` | Bundled earnings / IR notes (not live EDGAR) |
| `inspect_name` | Drill into one ticker against holdings + cluster |

If the original repo cannot support a tool with live institutional data, the adapter says so and returns what the bundled pack actually contains. Missing evidence stays missing.

---

## Safety invariants (enforced in Python)

1. The agent cannot modify deterministic risk metrics.
2. The agent cannot modify thresholds or triggers.
3. The agent cannot convert qualitative evidence into a crash probability.
4. Evidence published after the assessment cutoff is rejected.
5. Missing evidence remains missing.
6. The agent cannot recommend or execute a trade (trade language is stripped from the note).
7. The LLM cannot override quantitative state.
8. The loop is bounded (`MAX_STEPS = 6`).
9. Tool access is allowlisted. Unknown tools become error observations.
10. Final output distinguishes **observed / inferred / against / not confirmed**.

Prompts restate these rules. They are not the control plane.

Executor also enforces: argument validation, per-tool timeout, overall investigation deadline (`OVERALL_DEADLINE_SECONDS = 10`), parallel independent reads in one planner step, canonical-arg dedup, and failure isolation (one broken read does not kill the run).

---

## One example trace

```text
Step 1
hypothesis=localized crowded unwind
tools=['get_cluster_exposure', 'search_positioning', 'search_news']

Step 1 results
  get_cluster_exposure status=ok
  search_positioning status=ok
  search_news status=ok

Step 2
hypothesis=forced deleveraging still unconfirmed
tools=['inspect_name']

Step 2 results
  inspect_name status=ok COHR

STOP: EVIDENCE_SUFFICIENT
```

`AgentRunTrace` records `run_id`, `as_of_date`, `assessment_cutoff`, decisions, tool calls, tool results, errors, `stop_reason`, and the calibrated buckets. It does not store hidden chain-of-thought or API keys.

---

## Failure handling

| Failure | Behavior |
|---|---|
| Malformed planner JSON | Stop `MALFORMED_PLANNER_OUTPUT`; no tools run from that text |
| Unknown tool | Observation `error_type=unknown_tool`; loop continues |
| Invalid arguments | Observation `error_type=invalid_args`; no crash |
| Duplicate read | Observation `status=duplicate`; not re-executed |
| Tool timeout | Observation `status=timeout`; other parallel reads may still succeed |
| One parallel tool raises | Isolated `tool_exception`; siblings still return |
| Overall deadline | Stop `DEADLINE_EXCEEDED` |
| Post-cutoff document | Dropped; `discarded_post_cutoff` counted; content never enters the note |
| Planner repeats the same search | Duplicate observation, then `UNRESOLVABLE` |
| Max steps | Stop `MAX_STEPS` |

---

## How to run

Requirements: Python **3.11–3.14** and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --locked --all-groups
uv run python -m src.mvp.demo_smoke_test
uv run pytest -q
uv run python scripts/run_agent.py \
  --as-of-date 2026-05-29 \
  --verbose
```

`--planner auto` (default) uses DeepSeek when `DEEPSEEK_API_KEY` is set, otherwise the fail-closed heuristic planner. Both emit the same `AgentDecision` schema. The executor does not care which planner produced it.

```python
from src.agent import run_agent

result = run_agent(as_of_date="2026-05-29", verbose=True)
print(result.report)
print(result.trace.stop_reason)
```

The deterministic monitor CLI is unchanged: `scripts/run_monitor.py`.

---

## Eval cases

Small behavior suite on frozen-case shaped states (`tests/agent/test_evals.py`):

| Case | Date | Expectation |
|---|---|---|
| Semi-unwind | 2026-05-29 | Crowding-related tools; terminates; no state mutation |
| Recovery-crash reference | 2020-03-24 | Factor / news tools; `score_is_probability` stays false |
| Quiet control | 2024-01-05 | No evidence search; `NO_INVESTIGATION_NEEDED` |

Plus explicit failure tests in `tests/agent/test_executor_failures.py`. Most tests inject a scripted or heuristic planner. A live LLM eval is optional.

---

## Limitations

- This is an **investigation agent**, not a trading agent.
- Positioning and filings tools wrap **bundled / local** evidence. They do not observe prime-broker leverage or pull live EDGAR.
- `search_news` is the dated GDELT panel plus frozen case packs, not a live web crawl.
- Monitoring severity is a relative band. It is **not** a crash probability.
- The demo book is an equal-weight S&P 500 12-1 long-10 / short-10 proxy, not a live institutional book.
- Without `DEEPSEEK_API_KEY`, the planner falls back to a small heuristic that still goes through the executor.

Fuller product caveats: [`docs/limitations.md`](docs/limitations.md). Methodology: [`docs/methodology.md`](docs/methodology.md).

---

## Mechanisms

The agent may investigate these lenses separately. It does not merge them into one opaque score.

**Daniel–Moskowitz recovery crash:** deep prior drawdown → rapid recovery → loser rebound → short-leg pain.

**Khandani–Lo crowded unwind:** concentrated / shared-theme positions → similar investors reduce exposure → one-sided selling → weak liquidity absorption. Crowding is a risk amplifier, not proof of forced deleveraging.

---

## Repository map

```text
momentum-risk-agent/
├── src/agent/           # planner, executor, loop, contracts, PM note
│   └── heuristic.py     # original pre-programmed loop (compatibility)
├── src/tools/           # read-only tool adapters
├── src/mvp/             # deterministic monitor, evidence card, PM response
├── src/monitoring/      # scorecard, unwind, crowding proxies
├── scripts/run_agent.py # investigation CLI
├── scripts/run_monitor.py
└── tests/agent/         # failure tests + frozen-case evals
```

---

## References

1. **Daniel, K., & Moskowitz, T. J. (2016).** *Momentum Crashes.*
2. **Khandani, A. E., & Lo, A. W. (2007; 2011).** *What Happened to the Quants in August 2007?*
3. **Ken French Data Library.**
