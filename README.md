# Momentum Risk Agent

A focused agent-architecture MVP over immutable deterministic momentum-risk
cases. The repository demonstrates how model planning is bounded by typed
decisions, code-owned routing, allowlisted read-only tools, deadlines, and
calibrated synthesis.

It does not recompute production market data, trade, de-gross, or emit a crash
probability.

## Execution path

```text
FrozenCaseProvider
  → immutable RiskState
  → code orchestrator
  → isolated crowding / recovery specialists
  → structured AgentDecision
  → validated read-only tools
  → executor safety controls
  → one calibrated PM note
```

The deterministic layer owns facts. The orchestrator owns routing. The planner
chooses reads. The executor owns permissions and budgets. Synthesis owns the
PM-facing note.

## Run it

Requirements: Python 3.11–3.14 and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --locked
uv run pytest -q

uv run python scripts/run_agent.py --as-of-date 2026-05-29 --planner heuristic
uv run python scripts/run_agent.py --as-of-date 2024-01-05 --planner heuristic
uv run python scripts/run_agent.py --as-of-date 2020-03-24 --planner heuristic
```

Expected routing:

| Case | Result |
|---|---|
| `2026-05-29` | crowding specialist |
| `2024-01-05` | no specialist and no tool calls |
| `2020-03-24` | recovery specialist |

`--planner auto` uses DeepSeek when `DEEPSEEK_API_KEY` is present and otherwise
uses the fail-closed heuristic planner.

### DeepSeek planner

The CLI loads DeepSeek settings from the ignored local `.env` file without
overriding values already exported by the shell:

```dotenv
DEEPSEEK_API_KEY="your-key"
# Optional defaults:
# DEEPSEEK_MODEL="deepseek-v4-flash"
# DEEPSEEK_BASE_URL="https://api.deepseek.com"
```

Then run an explicit LLM investigation:

```bash
uv run python scripts/run_agent.py --as-of-date 2026-05-29 --planner llm --verbose
```

The planner calls DeepSeek's `/chat/completions` endpoint in non-thinking JSON
mode with an 800-token output cap. Every response must be one complete JSON
object that validates as an `AgentDecision`; empty, truncated, wrapped, or
malformed responses never execute unvalidated calls. With a valid API key, a
runtime DeepSeek timeout or malformed response switches that specialist once to
its bounded heuristic planner; the transition is recorded in the trace. An
explicit `--planner llm` still exits before orchestration when the key is empty.
`DEEPSEEK_MODEL` and `DEEPSEEK_BASE_URL` remain optional overrides.

### Evidence resilience

Cutoff-valid evidence is rendered in Observed and in one deduplicated
`Citations:` section using `[evidence_id] YYYY-MM-DD headline`. Rejected
post-cutoff documents cannot enter either section.

An executed read that raises a handler exception or reaches its per-tool timeout
gets at most one additional attempt when the shared investigation deadline still
has budget. Unknown tools, invalid arguments, semantic duplicates, cutoff
rejections, and exhausted deadlines are not retried. Each observation exposes
its attempt count in the trace.

## Public API

```python
from src.agent import run_orchestrated_investigation
from src.risk_state import FrozenCaseProvider

case = FrozenCaseProvider().load("2026-05-29")
result = run_orchestrated_investigation(case, use_llm=False)

print(result.spawned)
print(result.report)
```

`CaseProvider.load(as_of_date) -> InvestigationCase` is the extension seam for
future production data. Agent code never imports the retained data archive.

## Repository map

```text
src/agent/       planner, executor, loop, orchestration, synthesis
src/tools/       typed registry and case-local read-only observations
src/risk_state/  immutable contracts and provider interface
data/demo_cases/ three active deterministic cases
archive/data/    inherited non-runtime data retained for provenance
scripts/         one orchestrated CLI
tests/           focused boundary, runtime, tool, and failure tests
```

See [architecture](docs/architecture.md), [demo walkthrough](docs/demo.md), and
[limitations](docs/limitations.md).
