"""PM-facing note. Calibration buckets are assembled in code, not from model prose."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from src.agent.models import AgentDecision, ToolObservation
from src.agent.specialists import BY_NAME, QUIET_READ
from src.agent.state import AgentState
from src.agent_prompts import heuristic_classify

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
    if not text:
        return ""
    kept: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if _TRADE.search(sentence) or _CRASH_PROB.search(sentence):
            continue
        kept.append(sentence)
    return " ".join(kept).strip()


def contains_forbidden(value: str | None) -> bool:
    text = str(value or "")
    return bool(_TRADE.search(text) or _CRASH_PROB.search(text))


ESCALATED_READ = (
    "Escalate for PM review of the deterministic state. "
    "This is not a trade instruction."
)
UNCERTAIN_READ = (
    "Investigation stopped with remaining uncertainty. The quantitative "
    "state is unchanged."
)
NO_PRIOR = "No prior-date comparison was loaded for this investigation."
DEFAULT_NEXT_CHECK = (
    "Continue ordinary monitoring of breadth, liquidity, and the concentrated names."
)
FORBIDDEN_DROPPED = "Model proposed forbidden action language; that text was dropped."
_SNAPSHOT_DELTA_PREFIX = "Deterministic snapshot already compared with"


def snapshot_observed(risk: Mapping[str, Any]) -> list[str]:
    trigger_count = int(risk.get("deterministic_trigger_count") or 0)
    cluster = [str(item) for item in (risk.get("theme_cluster") or [])]
    unwind = str(risk.get("mechanical_unwind_state") or "NORMAL")
    observed = [
        f"{trigger_count} / 4 deterministic signals triggered",
        f"mechanical unwind state: {unwind}",
    ]
    if cluster:
        observed.append("theme cluster: " + ", ".join(cluster))
    flags = [str(item) for item in (risk.get("structural_flags") or [])]
    if flags:
        observed.append("structural flags: " + ", ".join(flags))
    return observed


def calibrated_buckets(state: AgentState) -> dict[str, Any]:
    risk = state.risk_state
    observed = snapshot_observed(risk)

    for item in state.observations:
        observed.extend(_observed_from_tool(item))

    against = []
    why = str(risk.get("why_not_act_yet") or "").strip()
    if why:
        against.append(why)
    for item in state.observations:
        against.extend(_against_from_tool(item))

    classified = heuristic_classify(state.evidence, mechanism=_mechanism(state))
    inferred = [sanitize_text(item) for item in (classified.get("supported_claims") or [])]
    last = state.last_decision
    if last and last.hypothesis:
        inferred.append(f"Working hypothesis: {sanitize_text(last.hypothesis)}")
    if last and last.final_assessment:
        cleaned = sanitize_text(last.final_assessment)
        if cleaned:
            inferred.append(cleaned)
        elif contains_forbidden(last.final_assessment):
            inferred.append(FORBIDDEN_DROPPED)

    not_confirmed = [sanitize_text(item) for item in (classified.get("missing_evidence") or [])]
    for item in (classified.get("contradicting_claims") or []):
        against.append(sanitize_text(item))
    if "crowded_theme_unwind" in (risk.get("supported_mechanisms") or []) or risk.get("theme_cluster"):
        if not any("forced" in item.lower() for item in not_confirmed):
            not_confirmed.append("Broad forced deleveraging / financing stress")
    if str(risk.get("overall_risk_state") or "") != "panic_elevated":
        not_confirmed.append("Completed Daniel–Moskowitz recovery crash")

    against = [item for item in dict.fromkeys(against) if item]
    inferred = [item for item in dict.fromkeys(inferred) if item]
    not_confirmed = [item for item in dict.fromkeys(not_confirmed) if item]
    observed = [item for item in dict.fromkeys(observed) if item]
    return {
        "observed": observed,
        "inferred": inferred or ["No additional inference beyond the deterministic snapshot."],
        "contradicted": against or ["None"],
        "not_confirmed": not_confirmed or ["None"],
        "next_useful_check": _next_check(state, classified),
        "what_changed": _what_changed(state),
        "current_read": _current_read(state, classified),
    }


def build_pm_note(state: AgentState) -> str:
    return render_pm_note(calibrated_buckets(state), _path_text(state.decisions, state.stop_reason))


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


def build_combined_pm_note(
    *,
    risk_state: Mapping[str, Any],
    spawned: Sequence[str],
    specialist_results: Mapping[str, Any],
    stop_reason: str,
) -> tuple[str, dict[str, Any]]:
    """One PM note from specialist states. Never dump buckets twice or average scores."""

    mechanism_buckets = {
        name: calibrated_buckets(specialist_results[name].state)
        for name in spawned
        if name in specialist_results
    }
    prefix = len(spawned) > 1
    snapshot = snapshot_observed(risk_state)
    observed = list(dict.fromkeys(snapshot))
    inferred: list[str] = []
    against: list[str] = []
    not_confirmed: list[str] = []
    snapshot_set = set(snapshot)
    for name in spawned:
        buckets = mechanism_buckets.get(name)
        if not buckets:
            continue
        label = BY_NAME[name].label if prefix else None
        observed.extend(_label([item for item in buckets["observed"] if item not in snapshot_set], label))
        inferred.extend(_label(buckets["inferred"], label))
        against.extend(_label(buckets["contradicted"], label))
        not_confirmed.extend(_label(buckets["not_confirmed"], label))

    buckets = {
        "observed": _clean_lines(observed) or ["No additional observations beyond the snapshot."],
        "inferred": _clean_lines(inferred) or ["No additional inference beyond the deterministic snapshot."],
        "contradicted": _clean_lines(against) or ["None"],
        "not_confirmed": _clean_lines(not_confirmed) or ["None"],
        "current_read": _combined_current_read(stop_reason, spawned, mechanism_buckets),
        "what_changed": _combined_what_changed(risk_state, spawned, mechanism_buckets),
        "next_useful_check": _combined_next_check(risk_state, spawned, mechanism_buckets),
        "score_is_probability": False,
        "spawned": list(spawned),
        "mechanisms": mechanism_buckets,
    }
    path = _combined_path(spawned, specialist_results, stop_reason)
    return render_pm_note(buckets, path), buckets


def _bullets(items: Sequence[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def _path_text(
    decisions: Sequence[AgentDecision],
    stop_reason: str | None,
    *,
    label: str | None = None,
    start: int = 1,
) -> str:
    return "\n".join(_path_lines(decisions, stop_reason, label=label, start=start)) or "1. Stopped"


def _path_lines(
    decisions: Sequence[AgentDecision],
    stop_reason: str | None,
    *,
    label: str | None = None,
    start: int = 1,
) -> list[str]:
    tag = f"[{label}] " if label else ""
    lines: list[str] = []
    step = start - 1
    for decision in decisions:
        step += 1
        tools = [call.name for call in decision.tool_calls] if decision.action == "call_tools" else []
        if tools:
            lines.append(f"{step}. {tag}{decision.hypothesis} · tools={tools}")
        else:
            lines.append(f"{step}. {tag}{decision.action.upper()} ({decision.reason})")
    if stop_reason:
        step += 1
        lines.append(f"{step}. {tag}STOP: {stop_reason}")
    return lines


def _current_read(state: AgentState, classified: Mapping[str, Any]) -> str:
    if state.stop_reason == "NO_INVESTIGATION_NEEDED":
        return QUIET_READ
    if state.stop_reason == "ESCALATED":
        return ESCALATED_READ
    assessment = classified.get("assessment")
    if assessment == "contradicting":
        return "Retrieved evidence argues against the working hypothesis."
    if state.stop_reason == "EVIDENCE_SUFFICIENT":
        return (
            "Pressure is localized; available evidence does not establish a "
            "book-wide unwind or recovery crash."
        )
    return UNCERTAIN_READ


def _next_check(state: AgentState, classified: Mapping[str, Any]) -> str:
    question = None
    if state.open_questions:
        question = state.open_questions[-1]
    elif classified.get("next_question"):
        question = str(classified.get("next_question"))
    risk_checks = list(state.risk_state.get("next_checks") or [])
    if question:
        return str(question)
    if risk_checks:
        return str(risk_checks[0])
    return DEFAULT_NEXT_CHECK


def _what_changed(state: AgentState) -> str:
    for item in state.observations:
        if item.name != "compare_prior_state" or item.status != "ok":
            continue
        payload = item.payload if isinstance(item.payload, dict) else {}
        changes = payload.get("changes") or []
        if changes:
            return "\n".join(f"- {change}" for change in changes)
        if payload.get("status") == "unavailable":
            return str(payload.get("limitation") or "Prior comparison unavailable.")
    return _snapshot_delta(state.risk_state)


def _mechanism(state: AgentState) -> str | None:
    if state.focus in {"kl_crowding", "dm_recovery", "fundamentals"}:
        return state.focus
    text = " ".join(state.investigated_hypotheses).lower()
    if any(token in text for token in ("crowd", "unwind", "theme", "cluster", "position")):
        return "kl_crowding"
    if any(token in text for token in ("recover", "daniel", "loser", "short-leg")):
        return "dm_recovery"
    if any(token in text for token in ("fundamental", "earning", "filing")):
        return "fundamentals"
    return None


def _observed_from_tool(item: ToolObservation) -> list[str]:
    if item.status != "ok" or not isinstance(item.payload, dict):
        if item.status == "ok":
            return [f"{item.name} returned"]
        return []
    payload = item.payload
    lines: list[str] = []
    if item.name == "get_factor_state":
        regime = payload.get("overall_risk_state")
        lines.append(f"factor/regime: {regime}; score_is_probability=False")
    if item.name == "get_cluster_exposure":
        symbols = payload.get("cluster_symbols") or []
        if symbols:
            lines.append("cluster exposure: " + ", ".join(str(s) for s in symbols))
    if item.name == "inspect_name":
        symbol = payload.get("symbol")
        leg = (payload.get("holding") or {}).get("leg") if isinstance(payload.get("holding"), dict) else None
        lines.append(
            f"{symbol} in_cluster={payload.get('in_theme_cluster')} "
            f"in_book={payload.get('in_book')}"
            + (f" leg={leg}" if leg else "")
        )
    documents = payload.get("documents") if isinstance(payload.get("documents"), list) else []
    if documents:
        headline = str((documents[0] or {}).get("headline") or "")[:160]
        if headline:
            lines.append(f"{item.name}: {headline}")
        if payload.get("discarded_post_cutoff"):
            lines.append(
                f"{item.name} discarded {payload['discarded_post_cutoff']} post-cutoff document(s)"
            )
    return lines


def _against_from_tool(item: ToolObservation) -> list[str]:
    if item.status != "ok" or not isinstance(item.payload, dict):
        return []
    documents = item.payload.get("documents") or []
    blob = " ".join(
        f"{doc.get('headline', '')} {doc.get('snippet', '')}"
        for doc in documents
        if isinstance(doc, dict)
    ).lower()
    if any(token in blob for token in ("rebuilt", "record quarterly", "record highs")):
        return ["Public operating results do not show broad fundamental deterioration"]
    if item.name == "search_positioning" and not documents:
        return ["No bundled positioning note confirmed forced deleveraging"]
    return []


def _label(items: Sequence[str], label: str | None) -> list[str]:
    prefix = f"[{label}] " if label else ""
    return [f"{prefix}{item}" for item in items if str(item).strip()]


def _clean_lines(items: Sequence[str]) -> list[str]:
    cleaned: list[str] = []
    for item in items:
        text = sanitize_text(item)
        if not text:
            if contains_forbidden(item):
                cleaned.append(FORBIDDEN_DROPPED)
            continue
        cleaned.append(text)
    return list(dict.fromkeys(cleaned))


def _combined_current_read(
    stop_reason: str,
    spawned: Sequence[str],
    buckets: Mapping[str, Mapping[str, Any]],
) -> str:
    if stop_reason == "NO_INVESTIGATION_NEEDED" or not spawned:
        return QUIET_READ
    if len(spawned) == 1:
        text = sanitize_text(str((buckets.get(spawned[0]) or {}).get("current_read") or ""))
        return text or UNCERTAIN_READ
    names = [BY_NAME[name].label.split(" (")[0] for name in spawned]
    joined = " and ".join(names) if len(names) == 2 else ", ".join(names)
    return (
        f"{joined} were investigated separately. "
        "Findings are listed by mechanism and are not combined into one score. "
        "This is not a trade instruction."
    )


def _snapshot_delta(risk_state: Mapping[str, Any]) -> str:
    compare_to = risk_state.get("compare_to_date")
    if compare_to:
        return (
            f"{_SNAPSHOT_DELTA_PREFIX} {compare_to}; "
            "this investigation did not recompute that delta."
        )
    return NO_PRIOR


def _combined_what_changed(
    risk_state: Mapping[str, Any],
    spawned: Sequence[str],
    buckets: Mapping[str, Mapping[str, Any]],
) -> str:
    for name in spawned:
        text = str((buckets.get(name) or {}).get("what_changed") or "").strip()
        if text and text != NO_PRIOR and not text.startswith(_SNAPSHOT_DELTA_PREFIX):
            return text
    return _snapshot_delta(risk_state)


def _combined_next_check(
    risk_state: Mapping[str, Any],
    spawned: Sequence[str],
    buckets: Mapping[str, Mapping[str, Any]],
) -> str:
    for name in spawned:
        text = str((buckets.get(name) or {}).get("next_useful_check") or "").strip()
        if text:
            return text
    checks = list(risk_state.get("next_checks") or [])
    return str(checks[0]) if checks else DEFAULT_NEXT_CHECK


def _combined_path(
    spawned: Sequence[str],
    results: Mapping[str, Any],
    stop_reason: str,
) -> str:
    if not spawned:
        return f"1. Orchestrator: no specialists spawned\n2. STOP: {stop_reason}"
    lines = [f"1. Orchestrator spawned: {', '.join(spawned)}"]
    step = 1
    for name in spawned:
        result = results.get(name)
        if result is None:
            step += 1
            lines.append(f"{step}. [{name}] skipped")
            continue
        chunk = _path_lines(
            result.state.decisions,
            result.stop_reason,
            label=name,
            start=step + 1,
        )
        lines.extend(chunk)
        step += len(chunk)
    lines.append(f"{len(lines) + 1}. Combined STOP: {stop_reason}")
    return "\n".join(lines)
