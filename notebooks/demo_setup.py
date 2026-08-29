"""Setup for final_mvp_demo.ipynb — one full MVP run; steps below render layers."""

from pathlib import Path
import math
import re
import sys

import pandas as pd
from IPython.display import Markdown, display

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.mvp.config import MVPConfig
from src.mvp.pipeline import run_mvp
from src.mvp.crowding_context import build_positioning_snapshot
from src.mvp.evidence_interpretation import public_positioning_proxy_items
from src.mvp.deepseek_evidence_interpreter import DeepSeekEvidenceInterpreter
from src.mvp.deepseek_pm_response_interpreter import DeepSeekPMResponseInterpreter
from src.mvp.pm_response import CATEGORY_LABELS
from src.utils.io import load_dotenv_if_present
from src.risk.dm_engine import build_primary_assessment
from src.regime.market_state import build_regime_history

# Demo default for the PPT: LIVE DeepSeek (requires DEEPSEEK_API_KEY in .env).
# Set to False for a fully offline deterministic run (no API call).
USE_LLM = True

CONFIG = MVPConfig(
    as_of_date="2026-05-29",
    compare_to_date="2026-04-30",
    threshold_profile="default",
    horizon_days=20,
    use_llm=USE_LLM,
)

CASE_PACKS = {
    "current_semi": ROOT / "outputs" / "current_semi_unwind",
    "cross_case": ROOT / "outputs" / "cross_case_comparison.md",
}

if CONFIG.use_llm:
    load_dotenv_if_present()
    evidence_interpreter = DeepSeekEvidenceInterpreter(
        cache_dir=ROOT / "outputs" / "llm_cache"
    )
    pm_interpreter = DeepSeekPMResponseInterpreter(
        cache_dir=ROOT / "outputs" / "llm_cache"
    )
else:
    evidence_interpreter = None
    pm_interpreter = None


def run_investigation_demo(mvp_result, max_steps=4, verbose=True):
    """Run the orchestrated investigation on an already-computed MVP result.

    The agent cannot change triggers, thresholds, scores, or the PM book.
    """

    from src.agent import run_orchestrated_investigation

    return run_orchestrated_investigation(
        as_of_date=CONFIG.as_of_date,
        max_steps=max_steps,
        verbose=verbose,
        mvp_result=mvp_result,
        use_llm=False,
    )


def fmt(value, signed=False):
    if value is None or value is pd.NA:
        return "unavailable"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            return "unavailable"
        return f"{value:+.4f}" if signed else f"{value:.4f}"
    return str(value)


def section(title, text):
    pattern = rf"## {re.escape(title)}\n(.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, flags=re.S)
    return match.group(0).strip() if match else f"_Section not found: {title}_"


def bullets(items):
    return "\n".join(f"- {item}" for item in items) if items else "_None_"


def run_with_retry(cfg, tries=3):
    """Run one MVP config, retrying the LLM narrative calls.

    Deterministic metrics are identical on every attempt; the retry only
    handles transient LLM schema/safety-validation failures so the live
    narrative is captured when possible. Fails closed to deterministic text.
    """

    last = None
    for _ in range(tries):
        last = run_mvp(
            cfg,
            interpreter=evidence_interpreter,
            pm_interpreter=pm_interpreter,
        )
        if last.interpretation.use_llm and last.pm_response.use_llm:
            break
    return last


# ---------------------------------------------------------------------------
# Render helpers: markdown construction lives here so the notebook cells stay
# presentation-friendly (one display call per step).
# ---------------------------------------------------------------------------


def render_market_regime(primary, row, evidence, as_of_date):
    """Build the Step 1 regime tables (rendering only; inputs are precomputed)."""

    rows = [
        ("UMD / DM state", primary.state, "comparison context only"),
        ("Bear state (504d market return < 0)", fmt(row.get("bear_state")), ""),
        ("Market return, 504d", fmt(row.get("mkt_return_504d")), ""),
        ("Market drawdown", fmt(row.get("market_drawdown")), ""),
        ("Recent min drawdown, 126d", fmt(row.get("recent_min_drawdown_126d")), ""),
        ("Recovery from trough, 126d", fmt(row.get("recovery_from_trough_126d")), ""),
        ("High volatility, 21d", fmt(row.get("high_volatility")), ""),
        ("High-vol recovery state", fmt(row.get("high_volatility_recovery_state")), ""),
        ("Rate regime", fmt(row.get("rate_regime")), ""),
    ]
    table = "| Field | Value | Note |\n| --- | --- | --- |\n"
    for label, value, note in rows:
        table += f"| {label} | `{value}` | {note} |\n"

    analog_rows = (
        "| State | Sample | Tail-loss freq | Mean fwd return | 5th pct |\n"
        "| --- | --- | --- | --- | --- |\n"
    )
    for item in evidence.historical_analogs:
        analog_rows += (
            f"| `{item['state']}` | {item['sample_size']} | "
            f"{fmt(item['tail_loss_frequency'])} | {fmt(item['mean_forward_return'])} | "
            f"{fmt(item['fifth_percentile_forward_return'])} |\n"
        )
    return (
        Markdown(f"### Market regime — {as_of_date}\n\n{table}"),
        Markdown(
            "**UMD comparison context** (descriptive history, not PM-book "
            f"probability):\n\n{analog_rows}"
        ),
    )


def render_quant_signals(signals, as_of_date):
    """Build the Step 2 quant-signal table (rendering only)."""

    rows = []
    for s in signals:
        delta = (
            fmt(s.change_vs_comparison, signed=True)
            if s.change_vs_comparison is not None
            else "—"
        )
        rows.append(
            f"| `{s.name}` | `{fmt(s.current_value)}` | `{fmt(s.threshold)}` | "
            f"`{s.status}` | `{delta}` | {s.interpretation} |"
        )
    table = (
        "| Metric | Value | Threshold | Status | Δ vs comparison | Read |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        + "\n".join(rows)
    )
    return Markdown(f"### Quant signals — {as_of_date}\n\n{table}")


def render_structural_mechanical(unwind, mechanical):
    """Return the Step 3 mechanism/theme/footprint/scorecard tables."""

    mech_rows = []
    for m in unwind.mechanism_scenarios:
        mech_rows.append(f"| `{m.scenario}` | `{m.status}` | {m.summary} |")
    mech_table = (
        "| Mechanism scenario | Status | Read |\n"
        "| --- | --- | --- |\n"
        + "\n".join(mech_rows)
    )

    tc = unwind.theme_concentration
    theme_rows = [
        ("Cluster", ", ".join(tc.cluster_symbols) or "—"),
        ("Active long symbols", ", ".join(tc.active_long_symbols) or "—"),
        ("Cluster exposure share", fmt(tc.cluster_exposure_share)),
        ("Avg residual correlation", fmt(tc.cluster_average_residual_correlation)),
        ("5d residual loss", fmt(tc.cluster_residual_loss_5d)),
        ("5d abnormal volume share", fmt(tc.cluster_abnormal_volume_share_5d)),
        ("Concentration trigger", fmt(tc.trigger)),
    ]
    theme_table = "| Field | Value |\n| --- | --- |\n"
    for label, value in theme_rows:
        theme_table += f"| {label} | `{value}` |\n"

    mech_state_rows = [
        ("Unwind state", fmt(mechanical.unwind_state)),
        ("Control spec", fmt(mechanical.control_spec)),
        ("Factor footprint R²", fmt(mechanical.factor_footprint_r2)),
        ("Factor footprint percentile", fmt(mechanical.factor_footprint_percentile)),
        ("Extreme turnover ratio", fmt(mechanical.extreme_turnover_ratio)),
        ("Extreme turnover percentile", fmt(mechanical.extreme_turnover_percentile)),
        ("Liquidity absorption failure", fmt(mechanical.liquidity_absorption_failure)),
        ("Absorption percentile", fmt(mechanical.absorption_percentile)),
    ]
    mech_state_table = "| Field | Value |\n| --- | --- |\n"
    for label, value in mech_state_rows:
        mech_state_table += f"| {label} | `{value}` |\n"

    sc_rows = []
    for r in unwind.scorecard:
        sc_rows.append(
            f"| `{r.metric}` | `{fmt(r.current_value)}` | `{fmt(r.threshold)}` | "
            f"`{r.triggered}` | `{r.severity}` | {r.explanation} |"
        )
    sc_table = (
        "| Metric | Value | Threshold | Triggered | Severity | Explanation |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        + "\n".join(sc_rows)
    )
    return (
        Markdown(f"### Mechanism scenarios — {unwind.as_of_date}\n\n{mech_table}"),
        Markdown(f"### Theme concentration\n\n{theme_table}"),
        Markdown(f"### Mechanical footprint\n\n{mech_state_table}"),
        Markdown(f"### Unwind scorecard (6 rows)\n\n{sc_table}"),
    )


def render_ai_evidence(evidence, interpretation, case_packs, config):
    """Return a condensed Step 4 AI evidence layer (key fields + details)."""

    mode = "live DeepSeek" if interpretation.use_llm else "offline deterministic"
    evidence_quality = evidence.audit_metadata.get("evidence_quality", "unavailable")
    by_id = {
        item.evidence_id: f"{item.headline_or_summary} — {item.source}"
        for item in evidence.retrieved_evidence
        if item.evidence_id
    }

    def id_line(evidence_id: str) -> str:
        summary = by_id.get(evidence_id)
        return f"- `{evidence_id}` — {summary}" if summary else f"- `{evidence_id}`"

    contra = list(interpretation.contradicting_evidence_ids)
    support = list(interpretation.supporting_evidence_ids)
    missing = list(interpretation.missing_or_uncertain_evidence)[:2]
    monitor = list(interpretation.monitoring_questions)
    invalid = list(interpretation.invalidation_conditions)
    contra_block = "\n".join(id_line(item) for item in contra) or "_None_"
    support_block = "\n".join(id_line(item) for item in support) or "_None_"
    missing_block = "\n".join(f"- {item}" for item in missing) or "_None_"
    monitor_block = "\n".join(f"- {item}" for item in monitor) or "_None_"
    invalid_block = "\n".join(f"- {item}" for item in invalid) or "_None_"

    warn_block = ""
    if evidence.data_warnings:
        warn_block = (
            "<details><summary>Deterministic adapter warnings (technical)</summary>\n\n"
            + bullets(evidence.data_warnings)
            + "\n\n</details>"
        )

    body = (
        f"### AI evidence layer — {mode} (condensed)\n\n"
        f"**Read:** {interpretation.narrative_state}\n\n"
        f"**Key counter-evidence ({len(contra)}):**\n\n{contra_block}\n\n"
        f"**Key missing:**\n\n{missing_block}\n\n"
        "<details><summary>Supporting · Monitoring · Invalidation · Quality</summary>\n\n"
        f"**PM interpretation:** “{interpretation.pm_interpretation}”\n\n"
        f"**Supporting:**\n\n{support_block}\n\n"
        f"**Monitoring questions:**\n\n{monitor_block}\n\n"
        f"**Invalidation conditions:**\n\n{invalid_block}\n\n"
        f"**Evidence quality:** `{evidence_quality}` · "
        f"`{interpretation.model_or_prompt_version}`\n\n"
        "</details>\n\n"
        f"{warn_block}"
    )

    case_read = (case_packs["current_semi"] / "pm_case_read.md").read_text()
    if config.as_of_date == "2026-05-29":
        frozen_sections = "\n\n".join(
            section(title, case_read)
            for title in [
                "What is supported",
                "What remains unconfirmed",
                "Why broad action may still be premature",
            ]
        )
        body += (
            "\n\n<details><summary><strong>Frozen evidence challenge "
            "(2026-05-29 pack)</strong> — supporting / unconfirmed / "
            f"premature</summary>\n\n{frozen_sections}\n\n</details>"
        )
    else:
        body += (
            "\n\n_The frozen evidence challenge is bound to 2026-05-29 and "
            "is not shown for other CONFIG dates._"
        )
    return Markdown(body)


def render_final_pm_read(evidence, unwind, mechanical, pm, as_of_date):
    """Return the Step 5 final PM read as one Markdown object."""

    scenarios = {m.scenario: m.status for m in unwind.mechanism_scenarios}
    tail_risk_state = {
        "FRAGILITY_BUILDING": "potential momentum tail risk",
    }.get(str(mechanical.unwind_state), str(mechanical.unwind_state).replace("_", " ").lower())

    table = (
        "| Layer | Read |\n"
        "| --- | --- |\n"
        f"| UMD / market context | `{evidence.overall_risk_state}` (comparison only) |\n"
        f"| Scorecard triggers | {len(evidence.triggered_quant_signals)} |\n"
        f"| Recovery crash | `{scenarios.get('bear_market_recovery_crash')}` |\n"
        f"| Short-book reversal | `{scenarios.get('short_book_reversal_crash')}` |\n"
        f"| Crowded theme unwind | `{scenarios.get('crowded_theme_unwind')}` |\n"
        f"| Momentum tail-risk state | `{tail_risk_state}` |\n"
        f"| Classification | `{unwind.scenario_classification}` |\n"
    )

    cats = [CATEGORY_LABELS.get(c, c) for c in pm.response_categories]
    cats_block = (
        "<details><summary>Response categories (bounded menu)</summary>\n\n"
        + bullets(cats)
        + "\n\n</details>"
    )
    pm_mode = "live DeepSeek" if pm.use_llm else "offline deterministic"

    return Markdown(
        f"### Final PM read — {as_of_date}\n\n"
        f"{table}\n"
        f"**Current read:** “{pm.current_state}”\n\n"
        f"**Main vulnerability:** “{pm.main_vulnerability}”\n\n"
        f"**Why not act yet:** “{pm.why_not_act_yet}”\n\n"
        f"**What would change the reading:**\n\n{bullets(pm.what_would_change_the_reading)}\n\n"
        f"**Conditional response:**\n\n{bullets(pm.conditional_response)}\n\n"
        f"{cats_block}\n\n"
        f"*Mode: {pm_mode} (`{pm.model_or_prompt_version}`)*"
    )


def render_comparison(
    evidence,
    unwind,
    mechanical,
    interpretation,
    ev6,
    un6,
    mech6,
    interp6,
):
    """Build the Step 6 5/29 vs 6/30 comparison table (rendering only)."""

    def posture_for(unw):
        return (
            "escalate_for_pm_review"
            if "crowded_theme_unwind" in unw.active_scenarios
            else "focused_review_and_monitor"
        )

    rows = [
        ("Overall state", evidence.overall_risk_state, ev6.overall_risk_state),
        ("Quant triggers", len(evidence.triggered_quant_signals), len(ev6.triggered_quant_signals)),
        ("Scenario classification", unwind.scenario_classification, un6.scenario_classification),
        ("Active mechanisms", ", ".join(unwind.active_scenarios) or "none", ", ".join(un6.active_scenarios) or "none"),
        ("Theme cluster", ", ".join(unwind.theme_concentration.cluster_symbols) or "—", ", ".join(un6.theme_concentration.cluster_symbols) or "—"),
        ("Theme trigger", fmt(unwind.theme_concentration.trigger), fmt(un6.theme_concentration.trigger)),
        ("Mechanical state", mechanical.unwind_state, mech6.unwind_state),
        ("Factor footprint pct", fmt(mechanical.factor_footprint_percentile), fmt(mech6.factor_footprint_percentile)),
        ("Extreme turnover pct", fmt(mechanical.extreme_turnover_percentile), fmt(mech6.extreme_turnover_percentile)),
        ("Liquidity absorption failure", fmt(mechanical.liquidity_absorption_failure), fmt(mech6.liquidity_absorption_failure)),
        ("Evidence items", evidence.audit_metadata["retrieved_evidence_count"], ev6.audit_metadata["retrieved_evidence_count"]),
        ("Evidence mode", "live DeepSeek" if interpretation.use_llm else "deterministic", "live DeepSeek" if interp6.use_llm else "deterministic"),
        ("LLM narrative", interpretation.narrative_state, interp6.narrative_state),
        ("PM posture", posture_for(unwind), posture_for(un6)),
    ]
    table = (
        "| Dimension | 2026-05-29 | 2026-06-30 |\n"
        "| --- | --- | --- |\n"
        + "\n".join(f"| {k} | {v5} | {v6} |" for k, v5, v6 in rows)
    )
    return Markdown(f"### What changed from 2026-05-29 to 2026-06-30\n\n{table}")


def render_gdelt_read(label, payload, message):
    """Build the Step 7 GDELT news-read Markdown (rendering only).

    ``payload`` is ``(triggers, evidence, explainer_result)`` or ``None`` when
    the layer was not activated or failed closed; ``message`` carries the
    reason in that case.
    """

    if payload is None:
        return Markdown(f"**GDELT — {label}:** {message}")
    triggers, evidence, explain = payload
    if explain.get("status") != "ok":
        return Markdown(
            f"**GDELT news read — {label}:** {explain.get('message', 'unavailable')}"
        )
    rows = list(evidence.itertuples())
    all_evidence = "\n".join(
        f"- `{row.evidence_id}` ({row.date}) **{row.title}** — "
        f"{row.source} · matched: `{row.matched_trigger}`"
        for row in rows
    ) or "_None_"
    top_evidence = "\n".join(
        f"- `{row.evidence_id}` ({row.date}) **{row.title}** — "
        f"{row.source} · matched: `{row.matched_trigger}`"
        for row in rows[:4]
    ) or "_None_"
    trigger_label = ", ".join(
        f"{t['trigger']} ({t['status']})" for t in triggers
    )
    body = (
        f"**GDELT — {label}** (condensed)\n\n"
        f"**Triggers:** {trigger_label}\n\n"
        f"**Read:** {explain.get('trigger_summary')}\n\n"
        f"**PM takeaway:** {explain.get('pm_takeaway')}\n\n"
        f"**Top evidence:**\n\n{top_evidence}\n\n"
        "<details><summary>Recent narrative · Mechanism · Limitations · All evidence</summary>\n\n"
        f"**Recent narrative:** {explain.get('recent_narrative')}\n\n"
        f"**Momentum mechanism:** {explain.get('momentum_mechanism')}\n\n"
        f"**Limitations:** {explain.get('limitations')}\n\n"
        f"**All evidence:**\n\n{all_evidence}\n\n</details>"
    )
    return Markdown(body)
