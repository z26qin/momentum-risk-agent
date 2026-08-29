"""Default retrieval adapters and LLM/heuristic classification helpers."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Mapping, Sequence

from src.utils.io import REPO_ROOT, read_json
from src.utils.market_time import NEW_YORK

LOCAL_EVIDENCE_PATH = (
    REPO_ROOT / "data/evaluation/current_semi_unwind/candidate_evidence.json"
)

CLASSIFY_INSTRUCTIONS = """\
You assist a PM investigating an already-computed momentum tail-risk state.
The deterministic quantitative engine owns the risk state. You only classify
supplied evidence. Do not recalculate metrics, change thresholds or triggers,
predict crash probability, or recommend trades.

Return a single JSON object with exactly these keys:
assessment: supporting | contradicting | mixed | insufficient
supported_claims: array of short strings
contradicting_claims: array of short strings
missing_evidence: array of short strings
next_question: string or null (one narrower follow-up, or null)
confidence: low | medium | high  (evidence quality, NOT a crash probability)

Rules:
- Localized theme or technology exposure reduction does not establish broad
  forced deleveraging.
- Missing evidence remains missing. Do not invent sources or facts.
- If evidence is thin, mixed, or only anecdotal, assessment must be
  insufficient or mixed and next_question should narrow the gap.
"""

MECHANISM_QUERIES = {
    "kl_crowding": "crowded hedge-fund positioning unwind deleveraging",
    "dm_recovery": "market recovery loser rebound short-leg pain volatility",
    "fundamentals": "earnings capex growth outlook deterioration",
}
FOLLOWUP_QUERY = (
    "hedge fund gross exposure deleveraging technology prime brokerage"
)
MECHANISM_LABELS = {
    "kl_crowding": "Crowded-positioning unwind",
    "dm_recovery": "DM recovery / loser rebound",
    "fundamentals": "Fundamental repricing",
}
CROWDING_FLAGS = {"crowded_theme_unwind", "portfolio_concentration"}
RECOVERY_FLAGS = {
    "bear_market_recovery_crash",
    "short_book_reversal_crash",
    "high_volatility_recovery",
    "short_loss_in_recovery",
}


def published_by_cutoff(published_at: str, cutoff: str, as_of_date: str) -> bool:
    """Invariant 2: published_at <= assessment_cutoff."""

    pub = str(published_at or "").strip()
    if not pub or pub[:10] > as_of_date:
        return False
    parsed, cut = _parse_dt(pub), _parse_dt(cutoff)
    if parsed is None or cut is None:
        return pub[:10] <= as_of_date
    if parsed.tzinfo is None and cut.tzinfo is not None:
        parsed = parsed.replace(tzinfo=cut.tzinfo)
    elif parsed.tzinfo is not None and cut.tzinfo is None:
        cut = cut.replace(tzinfo=parsed.tzinfo)
    return parsed <= cut


def _parse_dt(value: str) -> datetime | None:
    text = value.strip()
    eastern = text.endswith(" ET")
    if eastern:
        text = text[: -len(" ET")].strip()
    text = text.replace("Z", "+00:00")
    if " " in text and "T" not in text[:19]:
        text = text.replace(" ", "T", 1)
    for candidate in (text, text[:10]):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if eastern or parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=NEW_YORK)
        return parsed
    return None


def active_flags(risk: Mapping[str, Any]) -> set[str]:
    flags = set(risk.get("structural_flags") or ())
    flags.update(risk.get("supported_mechanisms") or ())
    flags.update(risk.get("triggered_channels") or ())
    flags.update(
        name
        for name, status in (risk.get("mechanism_statuses") or {}).items()
        if status == "triggered"
    )
    return flags


def crowding_signal_present(state: Any) -> bool:
    """True only when crowding flags fired.

    ``primary_driver`` is a relative-score label, not a routing input. Quiet
    compact assessments can still say ``crowded_unwind`` while triggers are 0.
    """

    risk = getattr(state, "risk_state", state)
    return bool(active_flags(risk) & CROWDING_FLAGS)


def recovery_setup_present(state: Any) -> bool:
    return bool(active_flags(getattr(state, "risk_state", state)) & RECOVERY_FLAGS)


def no_meaningful_risk_signal(state: Any) -> bool:
    risk = getattr(state, "risk_state", state)
    if int(risk.get("deterministic_trigger_count") or 0) > 0:
        return False
    if crowding_signal_present(risk) or recovery_setup_present(risk):
        return False
    return str(risk.get("mechanical_unwind_state") or "NORMAL") in {"NORMAL", "", "None"}


def want_fundamentals(state: Any) -> bool:
    risk = getattr(state, "risk_state", state)
    investigated = getattr(state, "investigated_mechanisms", set())
    if "fundamentals" in investigated:
        return False
    if "fundamental_repricing" in active_flags(risk):
        return True
    if str(risk.get("scenario_classification") or "") == "fundamental_repricing":
        return True
    missing = " ".join((getattr(state, "last_assessment", None) or {}).get("missing_evidence") or [])
    return "fundamental" in missing.lower() and bool(investigated)
_FORCED = ("forced deleveraging", "forced selling", "margin call", "gross exposure")
_LOCAL = ("technology reduction", "tech stocks", "hedge fund selloff", "semiconductor")
_CONTRA = ("rebuilt", "pile back", "record highs", "buying focused", "record quarterly")
_RECOVERY = ("loser rebound", "short squeeze", "junk rally", "rapid recovery")


def as_document(item: Mapping[str, Any], *, query: str, channel: str) -> dict[str, Any]:
    return {
        "evidence_id": str(item.get("evidence_id") or item.get("id") or ""),
        "published_at": str(
            item.get("published_at")
            or item.get("publication_timestamp")
            or item.get("timestamp")
            or item.get("date")
            or ""
        ),
        "source": str(item.get("source") or ""),
        "headline": str(
            item.get("headline")
            or item.get("title")
            or item.get("headline_or_summary")
            or ""
        ),
        "snippet": str(
            item.get("snippet")
            or item.get("passage")
            or item.get("headline_or_summary")
            or item.get("title")
            or ""
        ),
        "channel": channel,
        "query": query,
        "stance": item.get("stance") or item.get("provisional_direction"),
    }


def _hits(query: str, text: str) -> bool:
    tokens = [token for token in query.lower().split() if len(token) > 3]
    blob = text.lower()
    return any(token in blob for token in tokens) if tokens else True


def retrieve_local_evidence(
    query: str, cutoff: str, *, as_of_date: str
) -> list[dict[str, Any]]:
    del cutoff  # cutoff is enforced by the agent loop, not the adapter
    if not LOCAL_EVIDENCE_PATH.is_file():
        return []
    payload = read_json(LOCAL_EVIDENCE_PATH)
    items = payload.get("items") if isinstance(payload, dict) else payload
    found: list[dict[str, Any]] = []
    for raw in items or []:
        doc = as_document(raw, query=query, channel="local")
        haystack = f"{doc['headline']} {doc['snippet']} {raw.get('mechanism_candidates')}"
        if _hits(query, haystack):
            found.append(doc)
    return found


def search_news(query: str, cutoff: str, *, as_of_date: str) -> list[dict[str, Any]]:
    del cutoff
    from src.evidence.gdelt_evidence import load_gdelt_titles, retrieve_gdelt_evidence

    lowered = query.lower()
    if any(token in lowered for token in ("crowd", "delever", "position", "hedge")):
        triggers, themes = ["crowded_theme_unwind"], ["crowding"]
    elif any(token in lowered for token in ("recover", "loser", "squeeze", "volatil")):
        triggers = [
            "high_volatility_recovery",
            "short_loss_in_recovery",
            "bear_market_recovery_crash",
        ]
        themes = ["panic", "riskoff"]
    else:
        triggers, themes = ["portfolio_drawdown"], ["policy", "rotation"]
    try:
        frame = retrieve_gdelt_evidence(
            load_gdelt_titles(),
            as_of_date=as_of_date,
            active_triggers=triggers,
            lookback_days=30,
            max_records=8,
            themes=themes,
            clamp_max_records=False,
        )
    except (OSError, TypeError, ValueError):
        return []
    if frame is None or getattr(frame, "empty", True):
        return []
    return [
        as_document(row, query=query, channel="news")
        for row in frame.to_dict(orient="records")
    ]


def search_positioning_evidence(query: str, cutoff: str, *, as_of_date: str) -> list[dict[str, Any]]:
    """Local positioning notes plus GDELT/news-style public evidence.

    This is not a Reddit/X/social-media search. An empty result is valid;
    never fabricate.
    """

    local = [
        item
        for item in retrieve_local_evidence(query, cutoff, as_of_date=as_of_date)
        if any(
            token in f"{item['headline']} {item['snippet']}".lower()
            for token in ("hedge fund", "prime", "position")
        )
    ]
    merged = {
        item["evidence_id"] or item["headline"]: item
        for item in local + search_news(query, cutoff, as_of_date=as_of_date)
    }
    return list(merged.values())[:8]


def query_from_question(question: str | None) -> str:
    text = (question or "").strip()
    if not text:
        return FOLLOWUP_QUERY
    if "?" not in text:
        return text
    if "delever" in text.lower() or "gross exposure" in text.lower():
        return FOLLOWUP_QUERY
    cleaned = re.sub(
        r"\b(?:is|there|any|evidence|of|the|a|an|to|for|in)\b", " ", text.lower()
    )
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip() or FOLLOWUP_QUERY


def format_classify_prompt(
    *,
    risk_state: Mapping[str, Any],
    hypothesis: str,
    evidence: Sequence[Mapping[str, Any]],
    query_history: Sequence[str],
    action_history: Sequence[Mapping[str, Any]],
) -> str:
    compact = {
        key: risk_state.get(key)
        for key in (
            "as_of_date",
            "overall_risk_state",
            "deterministic_trigger_count",
            "triggered_channels",
            "structural_flags",
            "supported_mechanisms",
            "mechanical_unwind_state",
            "theme_cluster",
        )
    }
    items = [
        {key: item.get(key) for key in ("evidence_id", "published_at", "source", "headline", "snippet")}
        for item in evidence
    ]
    return (
        f"DETERMINISTIC STATE\n{compact}\n\nCURRENT HYPOTHESIS\n{hypothesis}\n\n"
        f"EVIDENCE\n{items}\n\nPREVIOUS INVESTIGATION\n"
        f"queries={list(query_history)}\n"
        f"actions={[item.get('name') for item in action_history]}\n"
    )


def heuristic_classify(
    evidence: Sequence[Mapping[str, Any]], *, mechanism: str | None
) -> dict[str, Any]:
    followup = {
        "kl_crowding": "Is there evidence of broad deleveraging?",
        "dm_recovery": "Are losers rebounding vs winners?",
        "fundamentals": "Did earnings or outlook deteriorate in the book names?",
    }.get(mechanism, "What narrower public evidence would confirm the mechanism?")
    if not evidence:
        return {
            "assessment": "insufficient",
            "supported_claims": [],
            "contradicting_claims": [],
            "missing_evidence": ["No cutoff-valid documents were retrieved for this question."],
            "next_question": followup,
            "confidence": "low",
        }
    blob = " ".join(f"{item.get('headline', '')} {item.get('snippet', '')}" for item in evidence).lower()
    local, forced, contra, recovery = (
        any(token in blob for token in group)
        for group in (_LOCAL, _FORCED, _CONTRA, _RECOVERY)
    )
    if mechanism == "kl_crowding":
        supported = ["Localized crowding or technology exposure reduction"] if local else []
        contradicting = (
            ["Later rebuilding of technology exposure argues against an ongoing unwind"]
            if contra
            else []
        )
        missing = [] if forced else ["Broad forced deleveraging"]
        if forced and local and not contra:
            assessment, nxt, conf = "supporting", None, "medium"
        elif supported and contradicting:
            assessment, nxt, conf = "mixed", followup, "low"
        else:
            assessment, nxt, conf = "insufficient", followup, "low"
        return {
            "assessment": assessment,
            "supported_claims": supported,
            "contradicting_claims": contradicting,
            "missing_evidence": missing,
            "next_question": nxt,
            "confidence": conf,
        }
    if mechanism == "dm_recovery":
        supported = ["Recovery / short-covering language in public headlines"] if recovery else []
        return {
            "assessment": "mixed" if supported else "insufficient",
            "supported_claims": supported,
            "contradicting_claims": [],
            "missing_evidence": [] if supported else ["DM-style loser rebound"],
            "next_question": None if supported else followup,
            "confidence": "low",
        }
    if mechanism == "fundamentals" and contra:
        return {
            "assessment": "contradicting",
            "supported_claims": [],
            "contradicting_claims": [
                "Operating results do not show broad fundamental deterioration"
            ],
            "missing_evidence": ["Completed earnings revision in the actual book names"],
            "next_question": None,
            "confidence": "medium",
        }
    return {
        "assessment": "insufficient",
        "supported_claims": [],
        "contradicting_claims": [],
        "missing_evidence": ["Mechanism-specific confirmation"],
        "next_question": followup,
        "confidence": "low",
    }


def llm_classify(
    state: Any, mechanism: str | None, evidence: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return None
    from src.evidence.deepseek_explainer import (
        DEFAULT_DEEPSEEK_BASE_URL,
        DEFAULT_DEEPSEEK_MODEL,
        _extract_json_object,
        _post_chat_completion,
    )

    content = _post_chat_completion(
        api_key=api_key,
        model=os.environ.get("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL,
        messages=[
            {"role": "system", "content": CLASSIFY_INSTRUCTIONS},
            {
                "role": "user",
                "content": format_classify_prompt(
                    risk_state=state.risk_state,
                    hypothesis=MECHANISM_LABELS.get(mechanism or "", mechanism or "unspecified"),
                    evidence=evidence,
                    query_history=state.query_history,
                    action_history=state.action_history,
                ),
            },
        ],
        base_url=os.environ.get("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL,
        temperature=0.2,
    )
    parsed = _extract_json_object(content)
    assessment = str(parsed.get("assessment") or "").lower()
    if assessment not in {"supporting", "contradicting", "mixed", "insufficient"}:
        return None
    parsed["assessment"] = assessment
    if parsed.get("confidence") not in {"low", "medium", "high"}:
        parsed["confidence"] = "low"
    return parsed


def format_pm_report(
    *,
    trigger_count: int,
    total_triggers: int,
    primary_mechanism: str,
    assessment: Mapping[str, Any] | None,
    path: Sequence[str],
    stop_reason: str,
) -> str:
    payload = assessment or {}

    def bullets(items: Sequence[str]) -> str:
        return "\n".join(f"- {item}" for item in items) if items else "- None"

    if stop_reason == "NO_INVESTIGATION_NEEDED":
        interpretation = (
            "The deterministic state does not justify additional evidence "
            "search. Continue ordinary monitoring."
        )
    elif stop_reason == "TOOL_FAILURE":
        interpretation = (
            "A retrieval tool failed. No fabricated evidence was added. "
            "The deterministic risk state is unchanged."
        )
    elif payload.get("assessment") == "supporting" and not payload.get("missing_evidence"):
        interpretation = (
            "Retrieved evidence is consistent with the investigated mechanism. "
            "This remains an interpretation, not a change to the risk state."
        )
    else:
        interpretation = (
            "Localized crowding pressure is supported, but evidence does not "
            "establish a broad quantitative unwind. Continue monitoring rather "
            "than escalating the deterministic risk state."
        )
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(path, start=1)) or "1. Stopped"
    return (
        f"Risk state\n---------\n{trigger_count} / {total_triggers} deterministic signals triggered.\n\n"
        f"Primary mechanism investigated\n---------\n{primary_mechanism}\n\n"
        f"Evidence read\n---------\nSupporting:\n{bullets(payload.get('supported_claims') or [])}\n\n"
        f"Contradicting:\n{bullets(payload.get('contradicting_claims') or [])}\n\n"
        f"Not established:\n{bullets(payload.get('missing_evidence') or [])}\n\n"
        f"Agent path\n---------\n{steps}\n\n"
        f"PM interpretation\n---------\n{interpretation}\n"
    )
