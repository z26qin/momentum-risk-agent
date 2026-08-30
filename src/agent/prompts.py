"""Planner prompts. These constrain the model; invariants are still enforced in code."""

from __future__ import annotations

import json
from typing import Any, Sequence

from src.agent.models import TOOL_NAMES, ToolObservation
from src.agent.specialists import BY_FOCUS
from src.agent.state import AgentState

PLANNER_SYSTEM = f"""\
You are the investigation planner for Momentum-Risk-Agent.

The deterministic monitor has already computed the risk state. You investigate
that state. You do not change it.

Return a single JSON object with exactly these keys:
  action: call_tools | finish | escalate
  hypothesis: string
  reason: string
  tool_calls: array of {{id, name, args}}
  final_assessment: string or null
  open_questions: array of strings

The user JSON field allowed_tools is the allowlist. The executor is
authoritative; unknown names become unknown_tool.
Registered names: {", ".join(TOOL_NAMES)}.

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
search_* tools require {{"query": "..."}}.
inspect_name requires {{"symbol": "TICKER"}}.
compare_prior_state accepts {{"prior_date": "YYYY-MM-DD"}} or {{}}.
"""

def planner_system_prompt(focus: str | None = None) -> str:
    spec = BY_FOCUS.get(focus or "")
    return PLANNER_SYSTEM if spec is None else PLANNER_SYSTEM + "\n" + spec.addendum


def compact_planner_view(
    state: AgentState,
    *,
    allowed_tools: Sequence[str] | None = None,
    focus: str | None = None,
) -> dict[str, Any]:
    risk = state.risk_state
    compact_risk = {
        "as_of_date": risk.as_of_date.isoformat(),
        "assessment_cutoff": risk.assessment_cutoff.isoformat(),
        "market_regime": risk.market_regime,
        "mechanical_unwind_state": risk.mechanical_unwind_state,
        "monitoring_trigger_count": risk.monitoring_trigger_count,
        "total_signal_count": risk.total_signal_count,
        "triggered_signals": list(risk.triggered_signals),
        "structural_flags": list(risk.structural_flags),
        "mechanisms": risk.mechanisms.model_dump(),
        "theme_cluster": list(risk.theme_cluster),
        "book": risk.book.model_dump(mode="json"),
        "severity": risk.severity.model_dump(mode="json"),
        "score_is_probability": False,
    }
    tools = list(allowed_tools) if allowed_tools is not None else list(TOOL_NAMES)
    return {
        "risk_state": compact_risk,
        "focus": focus or state.focus,
        "prior_observations": [_compact_observation(item) for item in state.observations[-12:]],
        "investigated_hypotheses": list(state.investigated_hypotheses),
        "tool_history": list(sorted(state.executed_keys)),
        "open_questions": list(state.open_questions),
        "remaining_steps": max(0, state.max_steps - state.step),
        "remaining_deadline_seconds": round(max(0.0, state.remaining_seconds), 2),
        "allowed_tools": tools,
    }


def format_planner_user(
    state: AgentState,
    *,
    allowed_tools: Sequence[str] | None = None,
    focus: str | None = None,
) -> str:
    return json.dumps(
        compact_planner_view(state, allowed_tools=allowed_tools, focus=focus),
        default=str,
        sort_keys=True,
    )


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
