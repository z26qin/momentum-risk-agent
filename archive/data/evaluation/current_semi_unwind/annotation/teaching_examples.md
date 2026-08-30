# Calibration examples

> **NOT GOLD — FOR HUMAN CALIBRATION ONLY**

These examples illustrate plausible readings. Reviewers must make independent decisions and record no semantic label merely because it appears here.

## 1. Plausible Khandani–Lo evidence

**Title:** Tech stocks see largest hedge fund selloff in decade: Goldman Sachs  
**Source:** Investing.com reporting Goldman Sachs Prime Book data  
**Timestamp:** 2026-05-04 (date precision)  
**Evidence ID:** `CSU-2026-013`

**Passage:** The report said hedge funds made their largest decade-scale technology reduction, led by long sales; semiconductors and equipment were among the heaviest-sold groups.

**Why it is instructive:** It contains positioning-based risk reduction and broad technology subsector selling, which is closer to Khandani–Lo than an earnings-only story.

**Provisional relevance:** 2  
**Provisional mechanism:** `kl_synchronized_deleveraging`, possibly `kl_factor_propagation`  
**Alternative interpretation:** A normal discretionary rotation could produce long sales without forced deleveraging or liquidity stress.  
**What the human must decide:** Whether second-hand Prime Book reporting is strong enough to support synchronized deleveraging and whether the breadth extends beyond technology.

## 2. Plausible Daniel–Moskowitz evidence

**Title:** MacroMemo — May 5–25, 2026  
**Source:** RBC Global Asset Management  
**Timestamp:** 2026-05-25 (date precision)  
**Evidence ID:** `CSU-2026-015`

**Passage:** RBC described a broad recovery from the March selloff and explosive semiconductor gains, while warning that SOX valuations and technical measures were historically stretched.

**Why it is instructive:** It documents the recovery portion of a DM-style sequence and a stretched momentum winner complex.

**Provisional relevance:** 2  
**Provisional mechanism:** `dm_market_recovery`; not enough for a full DM crash  
**Alternative interpretation:** Semiconductor strength could reflect improving fundamentals rather than a loser-leg rebound.  
**What the human must decide:** Whether the prior decline qualifies as panic and whether actual prior losers—not semiconductor winners—were rebounding.

## 3. Plausible fundamental repricing evidence

**Title:** Will Rising Capex Test Hyperscalers’ Credit Strength?  
**Source:** S&P Global Ratings  
**Timestamp:** 2026-05-14T13:02:00-04:00  
**Evidence ID:** `CSU-2026-005`

**Passage:** S&P estimated five large cloud providers would spend about $750 billion in 2026, pressuring free cash flow even as first-quarter revenue and earnings accelerated.

**Why it is instructive:** It states both the capex/FCF concern and the contemporaneous earnings counterweight.

**Provisional relevance:** 2  
**Provisional mechanism:** `fundamental_capex_repricing`  
**Alternative interpretation:** Strong demand and earnings may justify capex, making this uncertainty rather than negative repricing.  
**What the human must decide:** Whether the passage indicates a changed cash-flow outlook or merely a known financing consequence of growth.

## 4. Ambiguous or contextual evidence

**Title:** Amazon.com Announces First Quarter Results  
**Source:** Amazon Investor Relations  
**Timestamp:** 2026-04-29 (date precision)  
**Evidence ID:** `CSU-2026-004`

**Passage:** Amazon said trailing free cash flow fell to $1.2 billion as AI property-and-equipment investment rose; AWS revenue nevertheless grew 28%.

**Why it is instructive:** The same record supports capex pressure and strong monetization, so direction depends on the mechanism claim.

**Provisional relevance:** 2  
**Provisional mechanism:** `fundamental_capex_repricing`, `fundamental_earnings_revision`  
**Alternative interpretation:** It could contradict a negative fundamental thesis because AWS growth remained strong.  
**What the human must decide:** Which fact is mechanism-discriminating and whether the item should be contextual rather than supporting.

## 5. Contradicting evidence

**Title:** Coherent Reports Third Quarter Fiscal 2026 Results  
**Source:** Coherent Investor Relations  
**Timestamp:** 2026-05-06 (date precision)  
**Evidence ID:** `CSU-2026-008`

**Passage:** Coherent reported 21% year-over-year revenue growth and said exceptionally strong datacenter and communications demand was driving capacity expansion.

**Why it is instructive:** Coherent is in the repository’s triggered correlated cluster, yet its contemporaneous operating evidence was strong.

**Provisional relevance:** 2  
**Provisional mechanism:** `fundamental_earnings_revision`, `contradicting_evidence`  
**Alternative interpretation:** Strong trailing results do not preclude valuation compression or future estimate cuts.  
**What the human must decide:** Whether this genuinely contradicts a fundamental repricing claim or merely shows that price/positioning stress preceded fundamental deterioration.
