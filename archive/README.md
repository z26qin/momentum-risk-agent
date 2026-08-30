# Archived deterministic inputs

`archive/data/` contains inherited raw, processed, corpus, evaluation, and
fixture data from `momentum-tail-risk-monitor`. It is retained for provenance
and future production-data work, but it is not imported, opened, or required
by the agent MVP.

The active runtime reads only the validated bundles in `data/demo_cases/`.
Production recomputation should be introduced later through the `CaseProvider`
interface rather than by reconnecting agent code directly to this archive.
