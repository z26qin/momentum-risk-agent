"""Calibrated PM synthesis owned by the agent layer."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from src.agent.models import AgentDecision, ToolObservation
from src.agent.specialists import BY_NAME, QUIET_READ
from src.agent.state import AgentState
from src.risk_state.models import RiskState

_TRADE = re.compile(
    r"(?i)\b(buy|sell|short|cover|de-?gross|place an order|enter a trade|"
    r"cut the longs?|cut the book|hedge now)\b"
)
_CRASH_PROB = re.compile(
    r"(?i)(crash probability|\d+\s*%\s*(chance|probability) of (a )?crash|"
    r"probability of a crash)"
)


def sanitize_text(value: str | None) -> str:
    text = str(value or "").strip()
    kept = [
        sentence
        for sentence in re.split(r"(?<=[.!?])\s+", text)
        if sentence and not _TRADE.search(sentence) and not _CRASH_PROB.search(sentence)
    ]
    return " ".join(kept).strip()


def contains_forbidden(value: str | None) -> bool:
    text = str(value or "")
    return bool(_TRADE.search(text) or _CRASH_PROB.search(text))


def snapshot_observed(risk: RiskState) -> list[str]:
    observed = [
        f"{risk.monitoring_trigger_count} / {risk.total_signal_count} deterministic signals triggered",
        f"mechanical unwind state: {risk.mechanical_unwind_state}",
    ]
    if risk.triggered_signals:
        observed.append("triggered signals: " + ", ".join(risk.triggered_signals))
    if risk.theme_cluster:
        observed.append("theme cluster: " + ", ".join(risk.theme_cluster))
    if risk.structural_flags:
        observed.append("structural flags: " + ", ".join(risk.structural_flags))
    return observed


def calibrated_buckets(state: AgentState) -> dict[str, Any]:
    observed = snapshot_observed(state.risk_state)
    for observation in state.observations:
        observed.extend(_observed_from_tool(observation))
    inferred, against, not_confirmed, next_check = _classify(state)
    last = state.last_decision
    if last and last.hypothesis:
        inferred.append(f"Working hypothesis: {sanitize_text(last.hypothesis)}")
    if last and last.final_assessment:
        cleaned = sanitize_text(last.final_assessment)
        if cleaned:
            inferred.append(cleaned)
        elif contains_forbidden(last.final_assessment):
            inferred.append("Model proposed forbidden action language; that text was dropped.")
    return {
        "observed": _unique(observed),
        "inferred": _unique(inferred) or ["No inference beyond the deterministic state."],
        "contradicted": _unique(against) or ["None"],
        "not_confirmed": _unique(not_confirmed) or ["None"],
        "next_useful_check": next_check,
        "what_changed": _what_changed(state),
        "current_read": _current_read(state),
        "score_is_probability": False,
    }


def build_pm_note(state: AgentState) -> str:
    return render_pm_note(
        calibrated_buckets(state), _path_text(state.decisions, state.stop_reason)
    )


def build_combined_pm_note(
    *,
    risk_state: RiskState,
    spawned: Sequence[str],
    specialist_results: Mapping[str, Any],
    stop_reason: str,
) -> tuple[str, dict[str, Any]]:
    mechanisms = {
        name: calibrated_buckets(specialist_results[name].state)
        for name in spawned
        if name in specialist_results
    }
    observed = snapshot_observed(risk_state)
    inferred: list[str] = []
    against: list[str] = []
    not_confirmed: list[str] = []
    for name in spawned:
        buckets = mechanisms.get(name)
        if not buckets:
            continue
        label = BY_NAME[name].label if len(spawned) > 1 else None
        inferred.extend(_label(buckets["inferred"], label))
        against.extend(_label(buckets["contradicted"], label))
        not_confirmed.extend(_label(buckets["not_confirmed"], label))
        for item in buckets["observed"]:
            if item not in observed:
                observed.extend(_label([item], label))
    calibrated = {
        "observed": _unique(observed),
        "inferred": _unique(inferred) or ["No inference beyond the deterministic state."],
        "contradicted": _unique(against) or ["None"],
        "not_confirmed": _unique(not_confirmed) or ["None"],
        "current_read": _combined_read(spawned, stop_reason),
        "what_changed": _combined_change(risk_state, mechanisms),
        "next_useful_check": _combined_next(spawned, mechanisms),
        "score_is_probability": False,
        "spawned": list(spawned),
        "mechanisms": mechanisms,
    }
    report = render_pm_note(
        calibrated, _combined_path(spawned, specialist_results, stop_reason)
    )
    return report, calibrated


def render_pm_note(buckets: Mapping[str, Any], path: str) -> str:
    return (
        f"Current read\n{buckets['current_read']}\n\n"
        f"Observed:\n{_bullets(buckets['observed'])}\n\n"
        f"Inferred:\n{_bullets(buckets['inferred'])}\n\n"
        f"Against:\n{_bullets(buckets['contradicted'])}\n\n"
        f"Not confirmed:\n{_bullets(buckets['not_confirmed'])}\n\n"
        f"Investigation path:\n{path}\n\n"
        f"What changed:\n{buckets['what_changed']}\n\n"
        f"Next useful check:\n{buckets['next_useful_check']}\n"
    )


def _classify(state: AgentState) -> tuple[list[str], list[str], list[str], str]:
    docs = [doc for doc in state.evidence if isinstance(doc, dict)]
    blob = " ".join(
        f"{doc.get('headline', '')} {doc.get('snippet', '')}" for doc in docs
    ).lower()
    inferred: list[str] = []
    against: list[str] = []
    missing: list[str] = []
    if state.focus == "kl_crowding":
        if any(token in blob for token in ("hedge fund", "technology reduction", "long sales")):
            inferred.append("Public evidence supports localized technology-position reduction.")
        if any(token in blob for token in ("rebuilt", "record revenue", "record highs")):
            against.append("Operating evidence and rebuilt exposure argue against a continuing broad unwind.")
        missing.append("Broad forced deleveraging / financing stress")
        return inferred, against, missing, "Is there evidence of broad deleveraging?"
    if state.focus == "dm_recovery":
        if state.risk_state.mechanisms.bear_market_recovery_crash == "triggered":
            inferred.append("Deterministic recovery conditions and short-leg pain are present.")
        if "recovery" in blob or "support" in blob:
            inferred.append("Cutoff-valid policy evidence supports a recovery backdrop.")
        missing.append("Direct confirmation of a broad loser-basket rebound")
        return inferred, against, missing, "Are losers rebounding broadly versus prior winners?"
    return inferred, against, ["Mechanism-specific confirmation"], "What evidence would resolve the hypothesis?"


def _current_read(state: AgentState) -> str:
    if state.stop_reason == "NO_INVESTIGATION_NEEDED":
        return QUIET_READ
    if state.stop_reason == "ESCALATED":
        return "Escalate the deterministic state for PM review; this is not a trade instruction."
    if state.focus == "dm_recovery":
        return "Recovery risk is present; the evidence remains an investigation, not a crash call."
    if state.stop_reason == "EVIDENCE_SUFFICIENT":
        return "Pressure is localized; broad forced deleveraging remains unconfirmed."
    return "Investigation stopped with uncertainty; the deterministic state is unchanged."


def _what_changed(state: AgentState) -> str:
    for item in state.observations:
        if item.name == "compare_prior_state" and item.status == "ok":
            changes = (item.payload or {}).get("changes", []) if isinstance(item.payload, dict) else []
            if changes:
                return "\n".join(f"- {change}" for change in changes)
    comparison = state.risk_state.comparison_date
    return (
        f"Frozen state is compared with {comparison.isoformat()}."
        if comparison
        else "No prior deterministic state is bundled."
    )


def _observed_from_tool(item: ToolObservation) -> list[str]:
    if item.status != "ok" or not isinstance(item.payload, dict):
        return []
    payload = item.payload
    if item.name == "get_factor_state":
        return [f"factor/regime: {payload.get('market_regime')}; score_is_probability=False"]
    if item.name == "get_cluster_exposure" and payload.get("cluster_symbols"):
        return ["cluster exposure: " + ", ".join(payload["cluster_symbols"])]
    if item.name == "inspect_name":
        holding = payload.get("holding") or {}
        return [
            f"{payload.get('symbol')} in_cluster={payload.get('in_theme_cluster')} "
            f"in_book={payload.get('in_book')}"
            + (f" leg={holding.get('leg')}" if holding.get("leg") else "")
        ]
    docs = payload.get("documents") or []
    if docs:
        return [f"{item.name}: {str(docs[0].get('headline') or '')[:160]}"]
    return []


def _combined_read(spawned: Sequence[str], stop_reason: str) -> str:
    if not spawned or stop_reason == "NO_INVESTIGATION_NEEDED":
        return QUIET_READ
    if len(spawned) == 1 and spawned[0] == "recovery":
        return "Recovery risk is present; the evidence remains an investigation, not a crash call."
    if len(spawned) == 1:
        return "Pressure is localized; broad forced deleveraging remains unconfirmed."
    return "Crowding and recovery were investigated separately and are not merged into one score."


def _combined_change(risk: RiskState, mechanisms: Mapping[str, Mapping[str, Any]]) -> str:
    for buckets in mechanisms.values():
        text = str(buckets.get("what_changed") or "")
        if text.startswith("-"):
            return text
    return (
        f"Frozen state is compared with {risk.comparison_date.isoformat()}."
        if risk.comparison_date
        else "No prior deterministic state is bundled."
    )


def _combined_next(spawned: Sequence[str], mechanisms: Mapping[str, Mapping[str, Any]]) -> str:
    for name in spawned:
        text = str((mechanisms.get(name) or {}).get("next_useful_check") or "")
        if text:
            return text
    return "Continue ordinary monitoring of breadth, liquidity, and concentrated names."


def _path_text(decisions: Sequence[AgentDecision], stop_reason: str | None) -> str:
    lines = _path_lines(decisions, stop_reason)
    return "\n".join(lines) if lines else "1. Stopped"


def _path_lines(
    decisions: Sequence[AgentDecision], stop_reason: str | None, *, label: str | None = None
) -> list[str]:
    tag = f"[{label}] " if label else ""
    lines: list[str] = []
    for index, decision in enumerate(decisions, 1):
        tools = [call.name for call in decision.tool_calls]
        if tools:
            lines.append(f"{index}. {tag}{decision.hypothesis} · tools={tools}")
        else:
            lines.append(f"{index}. {tag}{decision.action.upper()} ({decision.reason})")
    if stop_reason:
        lines.append(f"{len(lines) + 1}. {tag}STOP: {stop_reason}")
    return lines


def _combined_path(spawned: Sequence[str], results: Mapping[str, Any], stop_reason: str) -> str:
    if not spawned:
        return f"1. Orchestrator: no specialists spawned\n2. STOP: {stop_reason}"
    lines = [f"1. Orchestrator spawned: {', '.join(spawned)}"]
    for name in spawned:
        result = results.get(name)
        if result is None:
            lines.append(f"{len(lines) + 1}. [{name}] unavailable")
            continue
        for line in _path_lines(result.state.decisions, result.stop_reason, label=name):
            lines.append(f"{len(lines) + 1}. {line.split('. ', 1)[-1]}")
    lines.append(f"{len(lines) + 1}. Combined STOP: {stop_reason}")
    return "\n".join(lines)


def _label(items: Sequence[str], label: str | None) -> list[str]:
    prefix = f"[{label}] " if label else ""
    return [prefix + str(item) for item in items]


def _unique(items: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(sanitize_text(item) for item in items if sanitize_text(item)))


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"
