"""Market / factor read-only tools. Never recompute or rewrite risk metrics."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.mvp.hermes_monitor import compare_assessments
from src.tools.context import ToolContext

_FACTOR_KEYS = (
    "overall_risk_state",
    "mechanism_statuses",
    "supported_mechanisms",
    "unconfirmed_mechanisms",
    "primary_driver",
    "monitoring_severity_score",
    "score_label",
    "mechanism_scores",
    "triggered_channels",
    "structural_flags",
)


def get_factor_state(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    del args
    risk = ctx.snapshot()
    payload = {key: risk.get(key) for key in _FACTOR_KEYS}
    payload["as_of_date"] = ctx.as_of_date
    payload["score_is_probability"] = False
    payload["limitation"] = (
        "UMD/regime fields are the deterministic monitor snapshot. "
        "Monitoring severity is a relative band, not a crash probability."
    )
    return payload


def compare_prior_state(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    requested = getattr(args, "prior_date", None) or risk_compare_date(ctx)
    if ctx.prior_state is None:
        return {
            "status": "unavailable",
            "requested_prior_date": requested,
            "current_compare_to_date": ctx.risk_state.get("compare_to_date"),
            "changes": [],
            "limitation": (
                "No prior compact assessment was loaded for this run. "
                "The agent does not launch a second monitor computation."
            ),
        }
    comparison = compare_assessments(dict(ctx.risk_state), dict(ctx.prior_state))
    comparison["requested_prior_date"] = requested
    comparison["prior_as_of_date"] = ctx.prior_state.get("as_of_date")
    comparison["limitation"] = (
        "Discrete-state comparison only. Numeric drift inside the same "
        "severity band is not treated as a material change."
    )
    return comparison


def risk_compare_date(ctx: ToolContext) -> str | None:
    value = ctx.risk_state.get("compare_to_date")
    return str(value) if value else None
