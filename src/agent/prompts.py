"""Planner prompts. These constrain the model; invariants are still enforced in code."""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from src.agent.models import TOOL_NAMES, ToolObservation
from src.agent.state import AgentState

PLANNER_SYSTEM = """\
You are the investigation planner for Momentum-Risk-Agent.

The deterministic monitor has already computed the risk state. You investigate
that state. You do not change it.

Return a single JSON object with exactly these keys:
  action: call_tools | finish | escalate
  hypothesis: string
  reason: string
  tool_calls: array of {id, name, args}
  final_assessment: string or null
  open_questions: array of strings

Allowed tool names:
  get_book_state, get_factor_state, get_cluster_exposure, compare_prior_state,
  search_news, search_positioning, search_filings, inspect_name

Rules (the executor will enforce these even if you ignore them):
- Do not recalculate metrics, thresholds, triggers, or crash probabilities.
- Do not recommend or execute a trade, hedge, or de-gross.
- Do not treat missing evidence as present.
- Do not use information published after the assessment cutoff.
- Prefer a small parallel batch of independent reads.
- Dependent lookups wait for the next step.
- Stop when evidence is sufficient, clearly contradicted, the book is quiet,
  remaining uncertainty cannot be resolved with these tools, or the budget is gone.

Hypotheses to consider, without forcing all of them:
  crowded unwind, recovery-driven reversal, fundamental deterioration,
  localized theme unwind, ordinary noise.

When action is finish or escalate, tool_calls must be [].
When action is call_tools, include one to four tool calls with explicit args.
search_* tools require {"query": "..."}.
inspect_name requires {"symbol": "TICKER"}.
"""


COMPACT_RISK_KEYS = (
    "as_of_date",
    "overall_risk_state",
    "deterministic_trigger_count",
    "triggered_channels",
    "structural_flags",
    "supported_mechanisms",
    "unconfirmed_mechanisms",
    "mechanical_unwind_state",
    "primary_driver",
    "theme_cluster",
    "pm_posture",
    "book_read",
    "score_label",
    "monitoring_severity_score",
    "score_is_probability",
    "why_not_act_yet",
    "next_checks",
)


def compact_planner_view(state: AgentState) -> dict[str, Any]:
    risk = state.risk_state
    compact_risk = {key: risk.get(key) for key in COMPACT_RISK_KEYS}
    compact_risk["score_is_probability"] = False
    return {
        "risk_state": compact_risk,
        "prior_observations": [_compact_observation(item) for item in state.observations[-12:]],
        "investigated_hypotheses": list(state.investigated_hypotheses),
        "tool_history": list(sorted(state.executed_keys)),
        "open_questions": list(state.open_questions),
        "remaining_steps": max(0, state.max_steps - state.step),
        "remaining_deadline_seconds": round(max(0.0, state.remaining_seconds), 2),
        "allowed_tools": list(TOOL_NAMES),
    }


def format_planner_user(state: AgentState) -> str:
    return json.dumps(compact_planner_view(state), default=str, sort_keys=True)


def _compact_observation(item: ToolObservation) -> dict[str, Any]:
    payload = item.payload
    if isinstance(payload, dict) and "documents" in payload:
        documents = []
        for doc in list(payload.get("documents") or [])[:4]:
            if not isinstance(doc, dict):
                continue
            documents.append(
                {
                    "evidence_id": doc.get("evidence_id"),
                    "published_at": doc.get("published_at"),
                    "headline": str(doc.get("headline") or "")[:240],
                    "source": doc.get("source"),
                }
            )
        payload = {
            "documents": documents,
            "limitation": payload.get("limitation"),
            "source": payload.get("source"),
        }
    elif isinstance(payload, dict):
        payload = {key: payload[key] for key in list(payload)[:12]}
    return {
        "tool_call_id": item.tool_call_id,
        "name": item.name,
        "status": item.status,
        "error_type": item.error_type,
        "discarded_post_cutoff": item.discarded_post_cutoff,
        "payload": payload,
    }


def truncate_snippet(value: Any, limit: int = 240) -> str:
    text = str(value or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"
