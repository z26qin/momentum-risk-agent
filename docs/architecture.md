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

Tools project the frozen case or search its bundled evidence. Missing evidence,
holdings, and prior states remain explicitly missing.

## Synthesis

Synthesis renders observed, inferred, against, and not-confirmed buckets. It
does not average specialist findings or turn relative severity into a crash
probability. Trade language and probability claims are removed in code before
the PM note or trace is returned.

## Production extension

A future production implementation should satisfy
`CaseProvider.load(as_of_date) -> InvestigationCase`. Quantitative computation,
data acquisition, and freshness monitoring stay behind that boundary; the
orchestrator, tools, executor, and synthesis do not change.
