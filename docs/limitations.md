# Limitations

- The repository supports three frozen demonstration dates, not arbitrary or
  current market dates.
- Frozen cases preserve deterministic outputs; this repository does not
  recompute the inherited quantitative methodology.
- Evidence is bundled and cutoff-dated, not a live news, filing, broker, or
  social feed.
- Theme clusters are public-data correlation proxies, not observed common
  ownership, leverage, or financing stress.
- Relative severity is not a probability and cannot be converted into one by
  the planner or synthesis layer.
- This is an investigation agent, not a trading or portfolio-action system.
- Thread timeouts bound the agent response but cannot forcibly terminate an
  already-running Python function inside its worker thread.
