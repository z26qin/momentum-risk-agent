# Teaching examples

**NOT GOLD — FOR TRAINING DISCUSSION ONLY.** These provisional suggestions must not be copied into the annotation queue without human review.

## Example 01: Federal Reserve announces extensive new measures to support the economy

- Example ID: `teach-01`
- Assessment timestamp: `2020-03-24T16:00:00-04:00`
- Document metadata: Federal Reserve Board; published `2020-03-23T08:00:00-04:00`; [source](https://www.federalreserve.gov/newsevents/pressreleases/monetary20200323b.htm)

> The Federal Reserve is committed to using its full range of tools to support households, businesses, and the U.S. economy overall in this challenging time. The coronavirus pandemic is causing tremendous hardship across the United States and around the world. Our nation's first priority is to care for those afflicted and to limit the further spread of the virus. While great uncertainty remains, it has become clear that our economy will face severe disruptions. Aggressive efforts must be taken across the public and private sectors to limit the losses to jobs and incomes and to promote a swift recovery once the disruptions abate.

Why this is useful: A high-ranked official policy release directly documents credit and liquidity support during the stressed state, yet it does not state that momentum positions unwound.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `2`; mechanism `policy_or_liquidity_support`; direction `supporting`.
- Alternative plausible label: Relevance 1 / contextual if the reviewer requires an explicit cross-sectional or momentum connection.
- What the human must decide: Does direct evidence about market-wide credit support save enough investigation time to be directly useful for this environment?

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: The official archive metadata is cutoff-valid.
- Evidence direction: `supporting` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.

## Example 02: Treasury and Federal Reserve Board Expand Measures to Enhance Liquidity and Flow of Credit to American Workers, Households, and Businesses

- Example ID: `teach-02`
- Assessment timestamp: `2020-03-24T16:00:00-04:00`
- Document metadata: U.S. Department of the Treasury; published `2020-03-23T11:51:12+00:00`; [source](https://home.treasury.gov/news/press-releases/sm951)

> WASHINGTON – The spread of coronavirus has disrupted economic activity and put significant liquidity pressure on U.S. businesses. To immediately enhance liquidity and support American workers, households, and businesses through this challenging period, U.S. Treasury Secretary Steven T. Mnuchin today authorized the expansion of two recently launched facilities and the establishment of three new facilities to provide liquidity to the financial system pursuant to section 13(3) of the Federal Reserve Act.

Why this is useful: This is a near-duplicate policy account from a second official archive. It tests whether duplicate information should be discounted even when its grounding is excellent.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `2`; mechanism `policy_or_liquidity_support`; direction `supporting`.
- Alternative plausible label: Relevance 0 as a near-duplicate of the Federal Reserve release, or relevance 1 because it adds Treasury authorization context.
- What the human must decide: Does the Treasury-specific passage add useful information beyond the higher-ranked Federal Reserve release?

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: The official archive metadata is cutoff-valid.
- Evidence direction: `supporting` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.

## Example 03: SEC Enables Immediate Effectiveness of Proposed Rule Change to Facilitate NYSE Electronic Auctions in Light of Temporary Closure of Physical Trading Floor

- Example ID: `teach-03`
- Assessment timestamp: `2020-03-24T16:00:00-04:00`
- Document metadata: U.S. Securities and Exchange Commission; published `2020-03-21T18:00:00+00:00`; [source](https://www.sec.gov/newsroom/press-releases/2020-67)

> The U.S. Securities and Exchange Commission noticed for immediate effectiveness a proposed rule filing submitted by New York Stock Exchange LLC (NYSE) to facilitate electronic auctions in light of its decision to temporarily close its New York trading floor.

Why this is useful: Electronic-auction continuity is evidence of extraordinary market operating conditions, but its mechanism link to momentum reversal is indirect.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `1`; mechanism `market_stress_or_panic`; direction `contextual`.
- Alternative plausible label: Relevance 0 if trading-floor operations would not help the PM investigate the reversal environment.
- What the human must decide: Is market-functioning context useful background, or merely a pandemic-era operational detail?

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: The official archive metadata is cutoff-valid.
- Evidence direction: `contextual` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.

## Example 04: Consumer Price Index for February 2020

- Example ID: `teach-04`
- Assessment timestamp: `2020-03-24T16:00:00-04:00`
- Document metadata: U.S. Bureau of Labor Statistics; published `2020-03-11T08:30:00-04:00`; [source](https://www.bls.gov/news.release/archives/cpi_03112020.htm)

> The Consumer Price Index for All Urban Consumers (CPI-U) rose 0.1 percent in February on a seasonally adjusted basis, the same increase as in January, the U.S. Bureau of Labor Statistics reported today. Over the last 12 months, the all items index increased 2.3 percent before seasonal adjustment.

Why this is useful: The release is timestamp-clean and macroeconomic, but describes February inflation rather than a reversal mechanism.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `1`; mechanism `generic_macro_context`; direction `contextual`.
- Alternative plausible label: Relevance 0 because the passage predates the shock and does not help explain the contemporaneous reversal.
- What the human must decide: Would this macro background actually reduce investigation time?

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: The official archive metadata is cutoff-valid.
- Evidence direction: `contextual` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.

## Example 05: SEC Emergency Action Stops Digital Asset Scam

- Example ID: `teach-05`
- Assessment timestamp: `2020-03-24T16:00:00-04:00`
- Document metadata: U.S. Securities and Exchange Commission; published `2020-03-20T14:55:00+00:00`; [source](https://www.sec.gov/newsroom/press-releases/2020-66)

> The Securities and Exchange Commission today announced that it has obtained an asset freeze and other emergency relief to halt an ongoing securities fraud perpetrated by a former state senator and two others who bilked investors in and outside the U.S.

Why this is useful: An official release can be fully timestamp-valid yet completely irrelevant to the economic mechanism under review.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `0`; mechanism `other`; direction `irrelevant`.
- Alternative plausible label: No plausible higher label unless the archived passage contains market-mechanism content not visible in the selected passage.
- What the human must decide: Can the reviewer avoid rewarding official provenance when the passage itself is unrelated?

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: The official archive metadata is cutoff-valid.
- Evidence direction: `irrelevant` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.

## Example 06: Treasury Targets Companies Facilitating Iran’s Petroleum Sales

- Example ID: `teach-06`
- Assessment timestamp: `2020-03-24T16:00:00-04:00`
- Document metadata: U.S. Department of the Treasury; published `2020-03-19T13:56:31+00:00`; [source](https://home.treasury.gov/news/press-releases/sm949)

> WASHINGTON – The U.S. Department of the Treasury’s Office of Foreign Assets Control (OFAC) today took action against five United Arab Emirates (UAE)-based companies that facilitate the Iranian regime’s petroleum and petrochemical sales. In 2019, these five companies collectively purchased hundreds of thousands of metric tons of petroleum products from the National Iranian Oil Company (NIOC). Iran’s petroleum and petrochemical industries are major sources of revenue for the Iranian regime, which has used these funds to support the Islamic Revolutionary Guard Corps-Qods Force’s (IRGC-QF) malign activities throughout the Middle East, including the support of terrorist groups.

Why this is useful: Sanctions and petroleum-market wording can create keyword overlap without explaining the US equity momentum-reversal environment.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `0`; mechanism `other`; direction `irrelevant`.
- Alternative plausible label: Relevance 1 only if the exact passage contains a defensible market-stress connection; headline association is insufficient.
- What the human must decide: Is any mechanism connection present in the passage rather than in outside knowledge?

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: The official archive metadata is cutoff-valid.
- Evidence direction: `irrelevant` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.

## Example 07: Federal Reserve announces extensive new measures to support the economy

- Example ID: `teach-07`
- Assessment timestamp: `2020-03-18T16:00:00-04:00`
- Document metadata: Federal Reserve Board; published `2020-03-23T08:00:00-04:00`; [source](https://www.federalreserve.gov/newsevents/pressreleases/monetary20200323b.htm)

> The Federal Reserve is committed to using its full range of tools to support households, businesses, and the U.S. economy overall in this challenging time. The coronavirus pandemic is causing tremendous hardship across the United States and around the world. Our nation's first priority is to care for those afflicted and to limit the further spread of the virus. While great uncertainty remains, it has become clear that our economy will face severe disruptions. Aggressive efforts must be taken across the public and private sectors to limit the losses to jobs and incomes and to promote a swift recovery once the disruptions abate.

Why this is useful: The same strong policy document becomes an objective future negative at the March 18 cutoff.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `0`; mechanism `policy_or_liquidity_support`; direction `irrelevant`.
- Alternative plausible label: None for strict evaluation: invalid_future forces relevance 0 regardless of later economic usefulness.
- What the human must decide: Can the reviewer keep economic relevance separate from timestamp validity?

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: The publication is after this assessment cutoff.
- Evidence direction: `irrelevant` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.

## Example 08: Statement from Secretary Steven T. Mnuchin on the Establishment of the Money Market Mutual Fund Liquidity Facility

- Example ID: `teach-08`
- Assessment timestamp: `2020-03-24T16:00:00-04:00`
- Document metadata: U.S. Department of the Treasury; published `2020-03-19T01:53:13+00:00`; [source](https://home.treasury.gov/news/press-releases/sm950)

> WASHINGTON – U.S. Treasury Secretary Steven T. Mnuchin issued the following statement on the establishment of the Money Market Mutual Fund Liquidity Facility (MMLF) by the Federal Reserve Board:

Why this is useful: This release overlaps the Federal Reserve MMLF announcement but adds Treasury credit-protection details, making deduplication a substantive rather than purely textual judgment.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `2`; mechanism `policy_or_liquidity_support`; direction `supporting`.
- Alternative plausible label: Relevance 1 or 0 if the higher-ranked facility announcement already supplies everything the PM needs.
- What the human must decide: Does the Treasury-specific detail justify retaining this near-duplicate?

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: The official archive metadata is cutoff-valid.
- Evidence direction: `supporting` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.

## Example 09: Stop blaming short sellers for causing the market drops

- Example ID: `teach-09`
- Assessment timestamp: `2020-03-24T16:00:00-04:00`
- Document metadata: CNBC; published `2020-03-19T00:00:00-04:00`; [source](https://www.cnbc.com/2020/03/19/stop-blaming-short-sellers-for-causing-the-market-drops.html)

> Blaming short sellers is misguided. European countries have banned short selling but their markets continue to fall.

Why this is useful: GDELT proves discovery, and the current snippet challenges a short-selling explanation, but the exact March 2020 page version cannot be proven.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `1 (conditional on timestamp validity)`; mechanism `short_covering_or_position_unwind`; direction `contradicting`.
- Alternative plausible label: Timestamp uncertain and excluded from strict metrics; semantic relevance 0 is also plausible because short selling is not the same as momentum-position unwind.
- What the human must decide: Separate the potentially useful contradiction from the failed historical content-version proof.

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: Discovery is historical, but the exact historical page version is unproven.
- Evidence direction: `contradicting` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.

## Example 10: Stock rally continues at midday

- Example ID: `teach-10`
- Assessment timestamp: `2020-03-24T16:00:00-04:00`
- Document metadata: CNN; published `2020-03-24T12:08:13-04:00`; [source](https://www.cnn.com/business/live-news/stock-market-news-today-032420/)

> Today’s rally in US stocks isn’t letting up at midday. All three major indexes are sharply higher.

Why this is useful: The passage directly documents an extraordinary market rebound, but GDELT only proves discovery of the evolving live page; the retrieved content version is not historically verified.

**NOT GOLD — FOR TRAINING DISCUSSION ONLY**

- Provisional label suggestion: relevance `2 (conditional on timestamp validity)`; mechanism `market_rebound`; direction `supporting`.
- Alternative plausible label: Timestamp uncertain and excluded from strict metrics; semantic relevance 1 is plausible if a broad-index rebound alone is only context for the momentum reversal.
- What the human must decide: Separate strong semantic usefulness from the unresolved historical content-version proof.

Dimension check:

- Economic relevance: judge whether the passage helps explain the environment, not whether the source is famous.
- Timestamp validity: Discovery is historical, but the exact historical page version is unproven.
- Evidence direction: `supporting` is provisional and must follow the passage, not the headline.
- Strength of grounding: any supporting passage must be copied exactly from the block quote above.
