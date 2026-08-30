# Demo walkthrough

Start with the quiet case. It proves code-owned routing ignores a high relative
score and leftover crowding driver when no mechanism is triggered:

```bash
uv run python scripts/run_agent.py --as-of-date 2024-01-05 --planner heuristic --verbose
```

Then run May 2026. The crowding mechanism routes one isolated specialist, which
reads the cluster, cutoff-dated positioning/news evidence, and one concentrated
name before stopping:

```bash
uv run python scripts/run_agent.py --as-of-date 2026-05-29 --planner heuristic --verbose
```

Finally run March 2020. The recovery specialist reads factor state, dated policy
evidence, and the bundled February prior state. Portfolio concentration alone
does not incorrectly spawn the crowding specialist:

```bash
uv run python scripts/run_agent.py --as-of-date 2020-03-24 --planner heuristic --verbose
```

Use `--save-trace agent_traces/<name>.json` to inspect routing, structured
decisions, tool observations, errors, stop reasons, and calibrated output.

## DeepSeek planner

Set `DEEPSEEK_API_KEY` in the repository's ignored `.env`, then replace
`--planner heuristic` with `--planner llm`. The default model is
`deepseek-v4-flash`; `DEEPSEEK_MODEL` can select another compatible DeepSeek
chat model. Use `--planner auto` to select DeepSeek only when the key is
non-empty and otherwise retain deterministic heuristic planning.
