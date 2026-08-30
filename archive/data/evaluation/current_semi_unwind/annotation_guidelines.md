# Current semi-unwind annotation guidelines

Assessment date: **2026-05-29**  
Evidence cutoff: **2026-05-29 16:00 America/New_York**

This is a human-review protocol, not a gold dataset. The May 29 structured snapshot is 66 calendar days behind the current market date and has no economic semiconductor-theme classifier. Reviewers must not treat the statistical `CIEN`–`COHR`–`LITE` cluster as observed common ownership or as a validated semiconductor basket.

## Timestamp validity

- `valid`: the source was publicly available by the cutoff.
- `invalid`: publication occurred after the cutoff.
- `uncertain`: the publication time cannot be placed confidently before the cutoff.
- When only a date is published, retain date-level precision and never invent a time.
- A post-cutoff article describing May performance is still invalid for this assessment.

## Relevance

- `2`: directly helps distinguish DM recovery crash, Khandani–Lo unwind, or fundamental repricing.
- `1`: useful market or company context without discriminating among mechanisms.
- `0`: generic, duplicate, unsupported, or outside the cutoff.

## Mechanism labels

Use one or more labels from `evidence_protocol.json`. Keep the lenses separate:

- DM requires prior broad-market stress, recovery, and loser-leg rebound evidence.
- Khandani–Lo requires positioning/crowding, synchronized risk reduction, absorption stress, or factor propagation evidence.
- Fundamental repricing requires cash-flow, capex, valuation, competition, supply, or earnings-revision evidence.
- Strong operating results can contradict a negative fundamental-repricing thesis without disproving crowding risk.

## Direction

- `supporting`: strengthens the selected mechanism.
- `contradicting`: directly weakens it or supports an alternative explanation.
- `contextual`: relevant background without a directional mechanism conclusion.
- `irrelevant`: not usable for the research question.

## Status

- `verified`: timestamp, source, locator, and stored passage were checked.
- `source_metadata_only`: useful metadata, but passage-level verification is incomplete.
- `timestamp_uncertain`: timing cannot be placed reliably before the cutoff.
- `duplicate`: substantively duplicates a stronger item.
- `excluded`: future-dated, unsupported, or outside scope.

## Reviewer procedure

1. Open the locator and confirm title, publisher, and publication timing.
2. Confirm the stored passage is a faithful minimal excerpt or close paraphrase.
3. Decide timestamp validity before assigning semantic labels.
4. Assign relevance and mechanism without using the candidate hypothesis as a gold label.
5. Consider at least one alternative interpretation.
6. Record whether the item is company-specific, sector-wide, factor-wide, or generic market context.
7. Do not infer forced liquidation from public selling, correlation, turnover, or price action alone.
8. Do not infer fundamental deterioration merely from a price decline.
9. Flag contradictions and missing evidence explicitly.
10. Reject trade instructions, causal certainty, or composite probabilities.

## Known calibration trap

The structured snapshot detects a concentrated correlated cluster and elevated turnover, but it simultaneously shows healthy momentum breadth, no synchronous winner liquidation, no short-leg reversal, and no liquidity-absorption failure. Public evidence through the cutoff also shows strong AI-infrastructure demand. A valid review may therefore conclude “mixed” or “insufficient,” and should not force a single mechanism.
