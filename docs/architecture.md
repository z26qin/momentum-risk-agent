# Architecture

## Trust boundaries

`FrozenCaseProvider` validates JSON into a frozen, extra-forbidden
`InvestigationCase`. Its `RiskState` and nested values are immutable. Cutoffs
must be 16:00 America/New_York on the assessment date, signal counts must be
consistent, and `score_is_probability` is literally `False`.

The orchestrator reads triggered mechanism statuses and selects no specialist,
the crowding specialist, the recovery specialist, or both. A high relative
severity score or leftover primary-driver label cannot route work by itself.

Each specialist reuses the same bounded `run_agent` loop with a different tool
allowlist. Specialists run concurrently against one wall-clock budget and do
not share mutable investigation memory.

## Planner and executor

The planner can return only a validated `AgentDecision`: call tools, finish, or
escalate. It cannot execute code directly. The executor rejects unknown tools
and invalid arguments, deduplicates equivalent reads, caps parallel calls,
isolates exceptions and timeouts, enforces the overall deadline, and removes
post-cutoff evidence.

Only handler exceptions and per-tool timeouts are transient: the executor may
retry either once if the same overall deadline has budget. Pre-execution
rejections and cutoff filtering are never retried. `ToolObservation.attempts`
keeps that behavior visible without changing the tool payload.

An LLM planner may transition once to its focus-matched heuristic planner after
a transport timeout or malformed structured decision. The failed LLM call uses
wall-clock budget but not a loop step. Scripted and heuristic planner failures
remain fail-closed, and an empty explicit LLM configuration is rejected by the
CLI before the agent starts.

Tools project the frozen case or search its bundled evidence. Missing evidence,
holdings, and prior states remain explicitly missing.

## Synthesis

Synthesis renders observed, inferred, against, not-confirmed, and citation
buckets. Citations are derived only from cutoff-valid evidence already ingested
into the agent state, formatted as `[evidence_id] YYYY-MM-DD headline`, and
deduplicated across specialists. It
does not average specialist findings or turn relative severity into a crash
probability. Trade language and probability claims are removed in code before
the PM note or trace is returned.

## Production extension

A future production implementation should satisfy
`CaseProvider.load(as_of_date) -> InvestigationCase`. Quantitative computation,
data acquisition, and freshness monitoring stay behind that boundary; the
orchestrator, tools, executor, and synthesis do not change.
