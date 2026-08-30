# March 2020 retrieval annotation guidelines

Evaluation: `march-2020-momentum-retrieval-gold-v1`

## Purpose

Judge whether each candidate passage was available by the assessment cutoff
and whether it would help a PM investigate the contemporaneous
momentum-reversal environment. Do not judge whether the passage later proved
correct, predicted returns, or caused the reversal.

The candidate corpus and human gold labels are separate. Official archives,
GDELT metadata, retrieval scores, classifier output, and the provisional
teaching suggestions are never gold labels.

## Timestamp validity

- `valid`: the exact content version is demonstrably available at or before the
  assessment cutoff.
- `invalid_future`: publication, discovery, availability, or content-version
  time is after the cutoff. Relevance must be `0`.
- `uncertain`: the historical content version cannot be proven. Retain the row
  for audit, but it is excluded from strict metrics.

Do not substitute crawl/acquisition time for publication time. A current live
page is not historical evidence unless the archive or version claim is explicit.

## Relevance

- `2`: directly useful for explaining the momentum-reversal environment.
- `1`: useful background, but the mechanism connection is indirect.
- `0`: irrelevant, keyword-only, duplicate, or not useful.

When evidence is weak, choose the lower score. A market-wide rally is not by
itself proof of a momentum-position unwind.

## Mechanisms

Use one or more semicolon-separated values from:

- `market_stress_or_panic`
- `market_rebound`
- `policy_or_liquidity_support`
- `short_covering_or_position_unwind`
- `loser_leg_recovery`
- `crowded_positioning`
- `generic_macro_context`
- `other`

These mechanisms are an annotation vocabulary, not claims that GDELT observes
them directly. Use `other` only when no listed mechanism is appropriate.

## Evidence direction

- `supporting`: directly supports the mechanism interpretation.
- `contradicting`: directly challenges it.
- `contextual`: relevant context without a direct directional connection.
- `irrelevant`: required when relevance is `0`.

## Passage and rationale

For relevance `2`, copy one exact supporting substring from
`retrieved_passage`. For relevance `1`, a grounded passage is strongly
recommended. Do not paraphrase inside `supporting_passage`. Explain the
document-level judgment in `reviewer_rationale`, and record confidence as
`high`, `medium`, or `low`.

## Independence rules

Do not use future momentum returns, matured tail-loss labels, later accounts of
March 24, retrieval rank as a label, or a model classification as authority.
Label the passage available at the cutoff, not the later market outcome.
