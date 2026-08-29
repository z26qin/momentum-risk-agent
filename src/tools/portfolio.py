"""Portfolio / book / name read-only tools over the frozen monitor snapshot."""

from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import BaseModel

from src.tools.context import ToolContext
from src.tools.evidence import local_mentions

_BOOK_KEYS = (
    "as_of_date",
    "book_read",
    "deterministic_trigger_count",
    "triggered_channels",
    "pm_posture",
    "mechanical_unwind_state",
    "main_vulnerability",
    "why_not_act_yet",
    "theme_cluster",
    "structural_flags",
    "pm_current_state",
)


def get_book_state(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    del args
    risk = ctx.snapshot()
    payload = {key: risk.get(key) for key in _BOOK_KEYS}
    payload["as_of_date"] = ctx.as_of_date
    payload["assessment_cutoff"] = ctx.assessment_cutoff
    payload["limitation"] = (
        "Book metrics are copied from the immutable monitor snapshot. "
        "This tool cannot change thresholds, triggers, or holdings."
    )
    return payload


def get_cluster_exposure(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    del args
    risk = ctx.snapshot()
    cluster = list(risk.get("theme_cluster") or [])
    flags = list(risk.get("structural_flags") or [])
    return {
        "as_of_date": ctx.as_of_date,
        "cluster_symbols": cluster,
        "cluster_size": len(cluster),
        "structural_flags": flags,
        "mechanical_unwind_state": risk.get("mechanical_unwind_state"),
        "primary_driver": risk.get("primary_driver"),
        "supported_mechanisms": list(risk.get("supported_mechanisms") or []),
        "limitation": (
            "Cluster membership is a correlated-theme proxy from public prices "
            "and holdings. It is not observed common ownership or leverage."
        ),
    }


def inspect_name(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    symbol = str(getattr(args, "symbol", "")).strip().upper()
    risk = ctx.snapshot()
    cluster = [str(item).upper() for item in (risk.get("theme_cluster") or [])]
    holding = _lookup_holding(ctx, symbol)
    mentions = local_mentions(ctx.as_of_date, symbol)[:3]
    return {
        "symbol": symbol,
        "in_theme_cluster": symbol in cluster,
        "cluster_symbols": cluster,
        "in_book": holding is not None,
        "holding": holding,
        "local_evidence": mentions,
        "limitation": (
            "Name drill-down uses bundled holdings and local evidence only. "
            "Missing mentions remain missing."
        ),
    }


def _lookup_holding(ctx: ToolContext, symbol: str) -> dict[str, Any] | None:
    path = ctx.processed_dir / "momentum_portfolio_holdings.parquet"
    if not path.is_file():
        return None
    try:
        frame = pd.read_parquet(
            path,
            columns=["effective_month", "symbol", "leg", "weight", "formation_date"],
        )
    except (OSError, ValueError, KeyError):
        return None
    if frame.empty or "symbol" not in frame.columns:
        return None
    frame = frame.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    month = frame["effective_month"]
    if isinstance(month.dtype, pd.PeriodDtype):
        frame["effective_month"] = month.dt.to_timestamp()
    else:
        frame["effective_month"] = pd.to_datetime(month, errors="coerce")
    as_of = pd.Timestamp(ctx.as_of_date)
    matched = frame.loc[frame["symbol"].eq(symbol) & frame["effective_month"].le(as_of)]
    if matched.empty:
        return None
    latest = matched["effective_month"].max()
    row = matched.loc[matched["effective_month"].eq(latest)].iloc[-1]
    weight = row["weight"] if "weight" in row else None
    try:
        weight_value = None if pd.isna(weight) else float(weight)
    except (TypeError, ValueError):
        weight_value = None
    formation = row["formation_date"] if "formation_date" in row else None
    return {
        "symbol": symbol,
        "leg": str(row.get("leg") or ""),
        "weight": weight_value,
        "effective_month": pd.Timestamp(latest).date().isoformat(),
        "formation_date": (
            pd.Timestamp(formation).date().isoformat() if formation is not None and not pd.isna(formation) else None
        ),
    }
