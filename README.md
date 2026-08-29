<p align="center">
  <a href="docs/methodology.md"><img src="https://img.shields.io/badge/Docs-methodology-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="#what-it-will-not-do"><img src="https://img.shields.io/badge/Status-Investigation%20agent%20MVP-orange?style=for-the-badge" alt="Investigation agent MVP"></a>
</p>

# Momentum-Risk-Agent

An investigation agent over a **deterministic** US equity momentum tail-risk monitor.

It answers:

> Given the current deterministic momentum risk state, what should I investigate next, which tools should I use, what evidence supports or contradicts each hypothesis, and when should I stop?

It does **not** trade, de-gross, or publish a crash probability.

This repository is a **new project** cloned from [`momentum-tail-risk-monitor`](https://github.com/z26qin/momentum-tail-risk-monitor). The quantitative engine, evidence cutoff, fail-closed behavior, and PM-facing calibration are preserved.

This is an **investigation agent**, not a trading agent, and not a multi-agent debate club. Specialists do not talk to each other. The deterministic monitor remains the source of truth.

---

## How the architecture evolved

**Original cloned project:** deterministic monitor + a mostly fixed investigation workflow (`src/agent/heuristic.py`, still present for compatibility tests).

**Previous MVP in this repo:** one LLM (or heuristic) planner + one executor over the full 8-tool registry. Evidence from crowding and recovery landed in a single `AgentState`.

**Now:** a **code orchestrator** decides which mechanism monitors to spawn. Each monitor is the existing `run_agent()` loop with its own planner prompt and a **subset** tool registry. The orchestrator then synthesizes one calibrated PM note in code. Findings are never merged into a crash score.

```text
deterministic monitor (unchanged)
        ↓
immutable RiskState
        ↓
Orchestrator  (CODE decides which specialists to spawn)
        ↓
   ┌────┴────┐
   ↓         ↓
KL crowding  DM recovery
monitor      monitor
(each is run_agent with its own planner prompt + ToolRegistry subset)
   ↓         ↓
scoped traces
        ↓
Orchestrator synthesizes one PM note in CODE
(never merge into a crash score)
```

There is no LangGraph, CrewAI, AutoGen, or other orchestration framework. Quiet books spawn **nobody** and do not search.

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
1. Orchestrator spawned: crowding
2. [crowding] localized crowded unwind · tools=['get_cluster_exposure', 'search_positioning', 'search_news']
3. [crowding] forced deleveraging still unconfirmed · tools=['inspect_name']
4. [crowding] STOP: EVIDENCE_SUFFICIENT
5. Combined STOP: EVIDENCE_SUFFICIENT

What changed:
- Deterministic snapshot already compared with 2026-04-30; this investigation did not recompute that delta.

Next useful check:
- Watch whether selling spreads outside the cluster.
```

Same rules on two other dates: [March 2020](outputs/march_2020_reference/pm_case_read.md) is a recovery-crash reference; [January 2024](outputs/quiet_control_2024/pm_case_read.md) should not escalate and **no specialists run**. Cross-case table: [`outputs/cross_case_comparison.md`](outputs/cross_case_comparison.md).

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
              run_orchestrated_investigation()  — code router, no LangGraph
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
         crowding monitor                              recovery monitor
         run_agent() + subset registry                 run_agent() + subset registry
         planner → AgentDecision                       planner → AgentDecision
         same deterministic executor                   same deterministic executor
                    │                                           │
                    └─────────────────────┬─────────────────────┘
                                          ▼
                         calibrated PM note (code synthesis)
                         + OrchestratorTrace
```

`--mode single` keeps the previous one-planner loop for demos and existing tests.

---

## Agent / tool contracts

All executable actions come through validated structured output (`src/agent/models.py`). Free-form model text is never parsed to decide what runs. The orchestrator itself does **not** call market or evidence tools.

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

### Tool subsets

| Monitor | Question | Allowlist |
|---|---|---|
| Khandani–Lo crowding | Localized crowded unwind, or forced deleveraging? | `get_cluster_exposure`, `search_positioning`, `search_news`, `inspect_name`, `get_book_state` |
| Daniel–Moskowitz recovery | Recovery-driven loser rebound / lagging-leg crash setup? | `get_factor_state`, `get_book_state`, `search_news`, `compare_prior_state` |

A specialist that requests a tool outside its registry gets `unknown_tool` from the existing executor. Full 8-tool registry (`src/tools/`):

| Tool | Role |
|---|---|
| `get_book_state` | Deterministic current PM-book risk snapshot |
| `get_factor_state` | UMD / regime / recovery state (`score_is_probability` is always false) |
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
3. The agent cannot convert qualitative evidence into a crash score. `score_is_probability` stays false.
4. Evidence published after the assessment cutoff is rejected.
5. Missing evidence remains missing.
6. The agent cannot recommend or execute a trade (trade language is stripped from the note).
7. The LLM cannot override quantitative state. The orchestrator cannot override the quiet-book skip.
8. Each specialist loop is bounded (`MAX_STEPS = 6`); specialists share one overall deadline.
9. Tool access is allowlisted per specialist. Unknown tools become error observations.
10. Final output distinguishes **observed / inferred / against / not confirmed**. Mechanism notes are not averaged into one score.

Prompts restate these rules. They are not the control plane.

Routing is code, using `no_meaningful_risk_signal`, `crowding_signal_present`, and `recovery_setup_present`. If the January 2024 quiet control has no meaningful signal, **zero** specialists spawn and **no** tools run (`NO_INVESTIGATION_NEEDED`).

Executor also enforces: argument validation, per-tool timeout, overall investigation deadline (`OVERALL_DEADLINE_SECONDS = 10`), parallel independent reads in one planner step, canonical-arg dedup, and failure isolation (one broken read does not kill the run).

---

## One example trace

```text
Orchestrator: spawned=['crowding']

=== Specialist: Crowding (Khandani–Lo) ===
question: Is pressure a localized crowded unwind, or forced deleveraging?

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

[crowding] STOP: EVIDENCE_SUFFICIENT
```

`OrchestratorTrace` records routing decisions plus each specialist's `AgentRunTrace` (`run_id`, decisions, tool calls, tool results, errors, `stop_reason`, calibrated buckets). It does not store hidden chain-of-thought or API keys.

---

## Failure handling

| Failure | Behavior |
|---|---|
| Quiet book | Orchestrator spawns nobody; `NO_INVESTIGATION_NEEDED`; no tools |
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
uv run pytest tests/agent -q
uv run python scripts/run_agent.py \
  --as-of-date 2026-05-29 \
  --verbose --planner heuristic
```

Default CLI path is the orchestrated investigation. `--planner auto` uses DeepSeek when `DEEPSEEK_API_KEY` is set, otherwise the fail-closed heuristic planner. Both emit the same `AgentDecision` schema. The executor does not care which planner produced it.

```bash
# Previous one-planner loop
uv run python scripts/run_agent.py --mode single --as-of-date 2026-05-29 --verbose

# Quiet control: no specialists, no search
uv run python scripts/run_agent.py --as-of-date 2024-01-05 --verbose --planner heuristic
```

```python
from src.agent import run_orchestrated_investigation

result = run_orchestrated_investigation(as_of_date="2026-05-29", verbose=True)
print(result.spawned)
print(result.report)
print(result.trace.stop_reason)
```

The deterministic monitor CLI is unchanged: `scripts/run_monitor.py`.

---

## Eval cases

Small behavior suite on frozen-case shaped states (`tests/agent/test_evals.py`, `tests/agent/test_orchestrator.py`):

| Case | Date | Expectation |
|---|---|---|
| Semi-unwind | 2026-05-29 | Crowding specialist; recovery skipped unless recovery flags are set |
| Recovery-crash reference | 2020-03-24 | Recovery specialist (`get_factor_state` + news); crowding skipped unless crowding flags are set |
| Quiet control | 2024-01-05 | Zero specialists; no tools; `NO_INVESTIGATION_NEEDED` |
| Both flags | synthetic | Both specialists; evidence stays mechanism-scoped |

Plus explicit failure tests in `tests/agent/test_executor_failures.py`. Most tests inject a scripted or heuristic planner. A live LLM eval is optional.

---

## Limitations

- This is an **investigation agent**, not a trading agent.
- Specialists do not debate, vote, or chat. The orchestrator is code.
- Positioning and filings tools wrap **bundled / local** evidence. They do not observe prime-broker leverage or pull live EDGAR.
- `search_news` is the dated GDELT panel plus frozen case packs, not a live web crawl.
- Monitoring severity is a relative band. It is **not** a crash probability.
- The demo book is an equal-weight S&P 500 12-1 long-10 / short-10 proxy, not a live institutional book.
- Without `DEEPSEEK_API_KEY`, planners fall back to a small heuristic that still goes through the executor.

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
├── src/agent/           # orchestrator, planner, executor, loop, contracts, PM note
│   ├── orchestrator.py  # code router + combined synthesis
│   └── heuristic.py     # original pre-programmed loop (compatibility)
├── src/tools/           # read-only tool adapters + specialist subsets
├── src/mvp/             # deterministic monitor, evidence card, PM response
├── src/monitoring/      # scorecard, unwind, crowding proxies
├── scripts/run_agent.py # investigation CLI (orchestrated default)
├── scripts/run_monitor.py
└── tests/agent/         # failure tests + frozen-case evals + orchestrator
```

---

## References

1. **Daniel, K., & Moskowitz, T. J. (2016).** *Momentum Crashes.*
2. **Khandani, A. E., & Lo, A. W. (2007; 2011).** *What Happened to the Quants in August 2007?*
3. **Ken French Data Library.**
