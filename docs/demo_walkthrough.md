# PM Evidence Card — 15–20 minute walkthrough

## Pre-demo check

```bash
uv sync --locked --all-groups
uv run python -m src.mvp.demo_smoke_test
uv run python -m pytest -q
```

Expected:

- smoke output contains `"status": "ready"`;
- default pytest is the investigation-agent suite plus a thin engine smoke
  (the original monitor regression farm is not in this repo).

Open:

```bash
uv run --with jupyterlab jupyter lab notebooks/final_mvp_demo.ipynb
```

Use:

```python
CONFIG = MVPConfig(
    as_of_date="2024-01-05",
    compare_to_date="2023-12-01",
    threshold_profile="default",
    horizon_days=20,
    use_llm=False,
)
```

## Minute 0–3 — Problem

Ask: is **this momentum book** becoming fragile, how does that compare with the
published UMD backdrop, and what evidence would confirm or invalidate the view?

Emphasize:

1. crashes are rare and state-dependent;
2. one aggregate score is insufficient;
3. the S&P 10/10 book is the default **customizable PM portfolio**; UMD is the
   **comparison benchmark**;
4. this tool monitors fragility; it does not prescribe a trade.

## Minute 3–7 — Architecture and data

Show the notebook architecture cell and the metadata table. Stress:

- one `MVPConfig` / one `run_mvp()` result;
- PM portfolio scorecard is primary; UMD layer is comparison-only;
- threshold profile scopes Phase 4 only.

## Minute 7–12 — Macro comparison, portfolio, scorecard

Walk through:

1. UMD / market comparison components (high-volatility recovery context);
2. active long-10 / short-10 holdings in the PM book;
3. trailing drawdown / beta-gap chart for that book;
4. four-row scorecard statuses on the book.

## Minute 12–16 — Mechanisms and evidence

Show the three independent mechanism scenarios and the six-row unwind inputs on
the PM book. Then show timestamped evidence and the constrained interpretation.
Note that evidence cannot rewrite deterministic facts.

## Minute 16–20 — Card, limitations, future work

Render the final PM card. Close with limitations and deferred work from the
README: true PM holdings plug-in, PIT membership, observed positioning,
predictive validation, fuller retrieval layer.
