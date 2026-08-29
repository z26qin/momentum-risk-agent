<p align="center">
  <a href="docs/methodology.md"><img src="https://img.shields.io/badge/Docs-methodology-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="#what-it-will-not-do"><img src="https://img.shields.io/badge/Status-Investigation%20agent%20MVP-orange?style=for-the-badge" alt="Investigation agent MVP"></a>
</p>

# Momentum-Risk-Agent

An investigation agent over a **deterministic** US equity momentum tail-risk monitor.

It answers:

> Given the current deterministic momentum risk state, what should I investigate next, which tools should I use, what evidence supports or contradicts each hypothesis, and when should I stop?

It does **not** trade, de-gross, or publish a crash probability.

This is a **new project**. It inherits the quantitative engine from [`momentum-tail-risk-monitor`](https://github.com/z26qin/momentum-tail-risk-monitor) — evidence cutoff, fail-closed behavior, and PM-facing calibration. It does not keep that repo's test farm or the old pre-programmed investigation loop.

> **Model plans. Executor enforces. Orchestrator routes in code.**

---

## Architecture

```text
deterministic monitor (inherited engine)
        ↓
immutable RiskState
        ↓
Orchestrator  (CODE: which specialists, if any)
        ↓
   asyncio.wait + to_thread(run_agent)
   shared wall-clock deadline
   ┌────┴────┐
   ↓         ↓
KL crowding  DM recovery
run_agent()  run_agent()
subset tools subset tools
        ↓
one calibrated PM note (CODE synthesis; never a crash score)
```

No LangGraph / CrewAI / AutoGen. Specialists do not talk to each other; they overlap on one shared deadline. Quiet books spawn **nobody**.

`--mode single` is the same `run_agent()` loop with the full tool registry (used by specialists and demos).

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

Citations:
- [EVID-…] 2026-05-04 hedge fund technology exposure reduction

Investigation path:
1. Orchestrator spawned: crowding
2. [crowding] localized crowded unwind · tools=['get_cluster_exposure', 'search_positioning', 'search_news']
3. [crowding] forced deleveraging still unconfirmed · tools=['inspect_name']
4. [crowding] STOP: EVIDENCE_SUFFICIENT
5. Combined STOP: EVIDENCE_SUFFICIENT
```

[March 2020](outputs/march_2020_reference/pm_case_read.md) is a recovery-crash reference. [January 2024](outputs/quiet_control_2024/pm_case_read.md) should not escalate — leftover `primary_driver` labels do not spawn a search. Cross-case table: [`outputs/cross_case_comparison.md`](outputs/cross_case_comparison.md).

---

## Agent / tool contracts

Executable actions come only from a validated `AgentDecision` (`src/agent/models.py`). The orchestrator itself does not call market or evidence tools.

| Monitor | Question | Allowlist |
|---|---|---|
| Khandani–Lo crowding | Localized crowded unwind, or forced deleveraging? | `get_cluster_exposure`, `search_positioning`, `search_news`, `inspect_name`, `get_book_state` |
| Daniel–Moskowitz recovery | Recovery-driven loser rebound / lagging-leg crash setup? | `get_factor_state`, `get_book_state`, `search_news`, `compare_prior_state` |

A specialist that requests a tool outside its registry gets `unknown_tool`. Full registry: `src/tools/`.

---

## Safety invariants (enforced in Python)

1. The agent cannot modify deterministic risk metrics, thresholds, or triggers.
2. Qualitative evidence cannot become a crash score. `score_is_probability` stays false.
3. Evidence published after the assessment cutoff is rejected.
4. Missing evidence remains missing.
5. Trade language is stripped from the note.
6. Quiet books spawn zero specialists (`NO_INVESTIGATION_NEEDED`). Routing uses flags, not leftover `primary_driver` labels.
7. Each specialist loop is bounded (`MAX_STEPS = 6`). Independent specialists overlap via `asyncio.wait` + `to_thread(run_agent)` on one shared wall-clock deadline (`OVERALL_DEADLINE_SECONDS = 10`), not leftover time from the previous specialist.
8. Final output distinguishes **observed / inferred / against / not confirmed**. Mechanism notes are not averaged.

Prompts restate these rules. They are not the control plane.

---

## How to run

Requirements: Python **3.11–3.14** and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --locked --all-groups
uv run pytest -q
uv run python scripts/run_agent.py --as-of-date 2026-05-29 --planner heuristic
uv run python scripts/run_agent.py --as-of-date 2024-01-05 --planner heuristic
```

`--planner auto` uses DeepSeek when `DEEPSEEK_API_KEY` is set, otherwise the fail-closed heuristic planner. Both emit the same `AgentDecision` schema.

Inherited monitor demo (not part of the default pytest suite):

```bash
uv run python -m src.mvp.demo_smoke_test
uv run python scripts/run_monitor.py
```

```python
from src.agent import run_orchestrated_investigation

result = run_orchestrated_investigation(as_of_date="2026-05-29")
print(result.spawned, result.trace.stop_reason)
print(result.report)
```

---

## Tests

This repo tests the **investigation agent**, not the original monitor's regression farm.

| Suite | What it locks |
|---|---|
| `tests/agent/test_executor_failures.py` | malformed JSON, unknown tool, invalid args, timeout, cutoff, deadline |
| `tests/agent/test_evals.py` | quiet / semi-unwind / recovery single-loop behavior |
| `tests/agent/test_orchestrator.py` | routing, specialist isolation, one combined note |
| `tests/monitor/test_engine.py` | leftover driver is not a signal; cutoff; relative severity |

---

## Limitations

- Investigation agent, not a trading agent.
- Specialists do not debate, vote, or chat.
- Positioning and filings wrap **bundled / local** evidence.
- `search_news` is dated GDELT plus frozen packs, not a live crawl.
- Monitoring severity is a relative band, not a crash probability.
- Demo book is an equal-weight S&P 500 12-1 long-10 / short-10 proxy.

[`docs/limitations.md`](docs/limitations.md) · [`docs/methodology.md`](docs/methodology.md)

---

## Mechanisms

Investigated separately. Never merged into one opaque score.

**Daniel–Moskowitz recovery crash:** deep prior drawdown → rapid recovery → loser rebound → short-leg pain.

**Khandani–Lo crowded unwind:** concentrated / shared-theme positions → similar investors reduce exposure → one-sided selling → weak liquidity absorption. Crowding is a risk amplifier, not proof of forced deleveraging.

---

## Repository map

```text
momentum-risk-agent/
├── src/agent/           # orchestrator, planner, executor, loop, PM note
├── src/tools/           # read-only adapters + specialist subsets
├── src/mvp/             # inherited deterministic monitor
├── src/monitoring/      # inherited scorecard / unwind / crowding proxies
├── scripts/run_agent.py
├── scripts/run_monitor.py
├── tests/agent/         # this project's tests
└── tests/monitor/       # thin inherited-engine smoke
```

---

## References

1. **Daniel, K., & Moskowitz, T. J. (2016).** *Momentum Crashes.*
2. **Khandani, A. E., & Lo, A. W. (2007; 2011).** *What Happened to the Quants in August 2007?*
3. **Ken French Data Library.**
