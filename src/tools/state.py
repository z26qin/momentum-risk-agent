"""Read-only projections over a validated investigation case."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.risk_state.models import RiskState
from src.tools.context import ToolContext


def _case(ctx: ToolContext):
    if ctx.case is None:
        raise ValueError("case-local tool requires a validated InvestigationCase")
    return ctx.case


def get_book_state(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    del args
    risk = _case(ctx).risk_state
    return {
        "as_of_date": risk.as_of_date.isoformat(),
        "assessment_cutoff": risk.assessment_cutoff.isoformat(),
        "monitoring_trigger_count": risk.monitoring_trigger_count,
        "triggered_signals": list(risk.triggered_signals),
        "mechanical_unwind_state": risk.mechanical_unwind_state,
        "book": risk.book.model_dump(mode="json"),
        "theme_cluster": list(risk.theme_cluster),
        "structural_flags": list(risk.structural_flags),
        "limitation": "Facts are copied from the immutable deterministic case.",
    }


def get_factor_state(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    del args
    risk = _case(ctx).risk_state
    return {
        "as_of_date": risk.as_of_date.isoformat(),
        "market_regime": risk.market_regime,
        "mechanisms": risk.mechanisms.model_dump(),
        "triggered_mechanisms": list(risk.triggered_mechanisms),
        "unconfirmed_mechanisms": list(risk.unconfirmed_mechanisms),
        "severity": risk.severity.model_dump(mode="json"),
        "score_is_probability": False,
        "limitation": "Severity is a relative monitoring score, not a crash probability.",
    }


def get_cluster_exposure(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    del args
    risk = _case(ctx).risk_state
    return {
        "as_of_date": risk.as_of_date.isoformat(),
        "cluster_symbols": list(risk.theme_cluster),
        "cluster_size": len(risk.theme_cluster),
        "structural_flags": list(risk.structural_flags),
        "mechanical_unwind_state": risk.mechanical_unwind_state,
        "crowding_status": risk.mechanisms.crowded_theme_unwind,
        "limitation": (
            "Cluster membership is a frozen correlated-theme proxy, not observed "
            "common ownership or leverage."
        ),
    }


def inspect_name(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    case = _case(ctx)
    symbol = str(getattr(args, "symbol", "")).strip().upper()
    holding = next((item for item in case.holdings if item.symbol == symbol), None)
    evidence = [item for item in case.evidence if symbol in item.symbols]
    return {
        "symbol": symbol,
        "in_theme_cluster": symbol in case.risk_state.theme_cluster,
        "cluster_symbols": list(case.risk_state.theme_cluster),
        "in_book": holding is not None,
        "holding": holding.model_dump(mode="json") if holding else None,
        "local_evidence": [item.model_dump(mode="json") for item in evidence[:3]],
        "limitation": "Name inspection uses frozen case holdings and evidence only.",
    }


def compare_prior_state(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    case = _case(ctx)
    requested = getattr(args, "prior_date", None)
    prior = case.prior_state
    if prior is None:
        return {
            "status": "unavailable",
            "requested_prior_date": requested,
            "prior_as_of_date": None,
            "changes": [],
            "limitation": "No prior deterministic state is bundled; missing remains missing.",
        }
    if requested and str(requested) != prior.as_of_date.isoformat():
        return {
            "status": "unavailable",
            "requested_prior_date": str(requested),
            "prior_as_of_date": prior.as_of_date.isoformat(),
            "changes": [],
            "limitation": "The requested prior date is not bundled in this case.",
        }
    return {
        "status": "available",
        "requested_prior_date": str(requested) if requested else prior.as_of_date.isoformat(),
        "prior_as_of_date": prior.as_of_date.isoformat(),
        "changes": _discrete_changes(prior, case.risk_state),
        "limitation": "Discrete deterministic state changes only; numeric drift is not promoted.",
    }


def _discrete_changes(prior: RiskState, current: RiskState) -> list[str]:
    changes: list[str] = []
    if prior.market_regime != current.market_regime:
        changes.append(f"market_regime: {prior.market_regime} → {current.market_regime}")
    if prior.mechanical_unwind_state != current.mechanical_unwind_state:
        changes.append(
            "mechanical_unwind_state: "
            f"{prior.mechanical_unwind_state} → {current.mechanical_unwind_state}"
        )
    prior_mechanisms = prior.mechanisms.model_dump()
    current_mechanisms = current.mechanisms.model_dump()
    for name in current_mechanisms:
        if prior_mechanisms[name] != current_mechanisms[name]:
            changes.append(f"{name}: {prior_mechanisms[name]} → {current_mechanisms[name]}")
    if prior.triggered_signals != current.triggered_signals:
        changes.append(
            "triggered_signals: "
            f"{list(prior.triggered_signals)} → {list(current.triggered_signals)}"
        )
    if prior.theme_cluster != current.theme_cluster:
        changes.append(
            f"theme_cluster: {list(prior.theme_cluster)} → {list(current.theme_cluster)}"
        )
    return changes
