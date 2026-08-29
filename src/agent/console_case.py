"""Map an orchestrated investigation onto the frontend CaseData contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.agent.orchestrator import OrchestratedRunResult
from src.agent.specialists import BY_NAME
from src.tools.registry import CROWDING_TOOL_NAMES, RECOVERY_TOOL_NAMES
from src.utils.io import read_json

_TOOL_NAMES = {"crowding": CROWDING_TOOL_NAMES, "recovery": RECOVERY_TOOL_NAMES}
# Same four channels `src.agent.report.snapshot_observed` counts as "n / 4".
PM_SIGNALS = (
    "high_volatility_recovery",
    "short_minus_long_beta_gap",
    "portfolio_drawdown",
    "short_loss_in_recovery",
)


def build_console_case(
    result: OrchestratedRunResult,
    *,
    case_id: str,
    label: str,
    horizon_days: int = 20,
    snapshot: Mapping[str, Any] | Path | None = None,
    elapsed_seconds: float = 0.0,
) -> dict[str, Any]:
    payload = _load_snapshot(snapshot)
    return {
        "id": case_id,
        "label": label,
        "date": result.as_of_date,
        "cutoff": _cutoff_label(result),
        "horizon_days": horizon_days,
        "risk_state": _risk_panel(result.risk_state, payload),
        "trace": _trace_panel(result, elapsed_seconds=elapsed_seconds),
        "note": _note_panel(result),
    }


def compact_from_snapshot(snapshot: Mapping[str, Any] | Path, fallback: Mapping[str, Any]) -> dict[str, Any]:
    """Best-effort compact assessment from a frozen monitor dump."""

    payload = _load_snapshot(snapshot) or {}
    extra: dict[str, Any] = {}
    if "deterministic_input" in payload:
        extra = _compact_from_mvp(payload)
    elif "structural_unwind" in payload:
        extra = _compact_from_structured(payload)
    merged = dict(fallback)
    merged.update({key: value for key, value in extra.items() if value is not None})
    return merged


def _load_snapshot(snapshot: Mapping[str, Any] | Path | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    if isinstance(snapshot, Path):
        return read_json(snapshot) if snapshot.is_file() else None
    return dict(snapshot)


def _cutoff_label(result: OrchestratedRunResult) -> str:
    raw = str(result.trace.assessment_cutoff or result.risk_state.get("data_cutoff") or "")
    if "T" in raw:
        return raw.replace("T", " ")[:22]
    return raw or result.as_of_date


def _risk_panel(risk: Mapping[str, Any], snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    snapshot = snapshot or {}
    scorecard = _pm_scorecard(snapshot, risk)
    mechanisms = _mechanism_statuses(snapshot) or dict(risk.get("mechanism_statuses") or {})
    theme = _theme_proxy(snapshot, risk)
    unwind = (
        (snapshot.get("mechanical_unwind") or {}).get("unwind_state")
        or risk.get("mechanical_unwind_state")
        or "NORMAL"
    )
    fired = int(risk.get("deterministic_trigger_count") or 0)
    return {
        "scorecard": scorecard,
        "trigger_count": f"{fired} / {len(PM_SIGNALS)}",
        "mechanisms": mechanisms,
        "theme_proxy": theme,
        "unwind_state": unwind,
        "primary_driver": risk.get("primary_driver"),
        "score_is_probability": False,
    }


def _pm_signal_lookup(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    out: dict[str, Mapping[str, Any]] = {}
    backdrop = snapshot.get("market_backdrop") or {}
    high_vol = backdrop.get("high_volatility_recovery")
    if isinstance(high_vol, dict):
        out["high_volatility_recovery"] = high_vol
    stress = snapshot.get("pm_book_stress") or {}
    raw = stress.get("signals")
    if isinstance(raw, dict):
        for name, row in raw.items():
            if isinstance(row, dict):
                out[str(name)] = row
    card = snapshot.get("deterministic_input") or {}
    for item in list(card.get("triggered_quant_signals") or []) + list(
        card.get("non_triggered_relevant_signals") or []
    ):
        if isinstance(item, dict) and item.get("name"):
            out[str(item["name"])] = item
        elif isinstance(item, str):
            out[item] = {"status": "triggered", "name": item}
    return out


def _signal_triggered(row: Mapping[str, Any], *, fallback: bool) -> bool:
    if row.get("triggered") is True:
        return True
    status = str(row.get("status") or "").lower()
    if status in {"triggered", "trig"}:
        return True
    if status in {"not_triggered", "not triggered"}:
        return False
    return fallback


def _pm_scorecard(snapshot: Mapping[str, Any], risk: Mapping[str, Any]) -> list[dict[str, Any]]:
    lookup = _pm_signal_lookup(snapshot)
    triggered = {str(name) for name in (risk.get("triggered_channels") or [])}
    rows: list[dict[str, Any]] = []
    for name in PM_SIGNALS:
        src = lookup.get(name) or {}
        fired = _signal_triggered(src, fallback=name in triggered)
        threshold = src.get("threshold")
        if threshold is None:
            threshold = "triggered" if fired else "not triggered"
        rows.append(
            {
                "metric": name,
                "current_value": src.get("current_value"),
                "threshold": threshold,
                "triggered": fired,
                "status": "available",
            }
        )
    return rows


def _mechanism_statuses(snapshot: Mapping[str, Any]) -> dict[str, str]:
    structural = snapshot.get("structural_unwind") or {}
    if structural.get("mechanism_statuses"):
        return dict(structural["mechanism_statuses"])
    scenarios = (snapshot.get("unwind") or {}).get("mechanism_scenarios") or []
    return {
        item["scenario"]: item.get("status") or "not_confirmed"
        for item in scenarios
        if isinstance(item, dict) and item.get("scenario")
    }


def _theme_proxy(snapshot: Mapping[str, Any], risk: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = (snapshot.get("structural_unwind") or {}).get("theme_proxy") or (
        snapshot.get("unwind") or {}
    ).get("theme_concentration")
    if isinstance(raw, dict) and raw.get("cluster_symbols"):
        return {
            "cluster_symbols": list(raw.get("cluster_symbols") or []),
            "cluster_average_residual_correlation": float(
                raw.get("cluster_average_residual_correlation") or 0
            ),
            "cluster_residual_loss_5d": float(raw.get("cluster_residual_loss_5d") or 0),
            "cluster_exposure_share": float(raw.get("cluster_exposure_share") or 0),
            "trigger": bool(raw.get("trigger")),
        }
    cluster = [str(item) for item in (risk.get("theme_cluster") or [])]
    if not cluster:
        return None
    return {
        "cluster_symbols": cluster,
        "cluster_average_residual_correlation": 0.0,
        "cluster_residual_loss_5d": 0.0,
        "cluster_exposure_share": 0.0,
        "trigger": True,
    }


def _trace_panel(result: OrchestratedRunResult, *, elapsed_seconds: float) -> dict[str, Any]:
    routing = result.routing or {}
    specialists = []
    for name in result.spawned:
        spec = BY_NAME[name]
        run = result.specialist_results.get(name)
        decisions = []
        if run is not None:
            for decision in run.state.decisions:
                if decision.action != "call_tools":
                    continue
                decisions.append(
                    {
                        "hypothesis": decision.hypothesis,
                        "tool_calls": [
                            {"name": call.name, "args": dict(call.args or {})}
                            for call in decision.tool_calls
                        ],
                    }
                )
        specialists.append(
            {
                "name": spec.name,
                "label": spec.label,
                "question": spec.question,
                "focus": spec.focus,
                "allowed_tools": list(_TOOL_NAMES.get(name, ())),
                "planner_kind": run.planner_kind if run is not None else "",
                "decisions": decisions,
                "stop_reason": run.stop_reason if run is not None else "UNRESOLVABLE",
                "errors": list(run.state.errors) if run is not None else [],
                "elapsed_seconds": elapsed_seconds,
            }
        )
    return {
        "run_id": result.run_id,
        "quiet": bool(routing.get("quiet")),
        "spawned": list(result.spawned),
        "schedule": routing.get("schedule") or "parallel_shared_deadline",
        "deadline_seconds": float(routing.get("deadline_seconds") or 10),
        "elapsed_seconds": float(elapsed_seconds),
        "errors": list(result.trace.errors),
        "specialists": specialists,
        "combined_stop": result.stop_reason,
    }


def _note_panel(result: OrchestratedRunResult) -> dict[str, Any]:
    buckets = result.trace.calibrated or {}
    citations = [item for item in (buckets.get("citations") or []) if item and item != "None"]
    return {
        "current_read": buckets.get("current_read") or result.report.split("\n", 1)[0],
        "observed": list(buckets.get("observed") or []),
        "inferred": list(buckets.get("inferred") or []),
        "against": list(buckets.get("contradicted") or []),
        "not_confirmed": list(buckets.get("not_confirmed") or []),
        "citations": citations,
        "what_changed": str(buckets.get("what_changed") or ""),
        "next_useful_check": str(buckets.get("next_useful_check") or ""),
        "score_is_probability": False,
    }


def _compact_from_structured(payload: Mapping[str, Any]) -> dict[str, Any]:
    structural = payload.get("structural_unwind") or {}
    mechanical = payload.get("mechanical_unwind") or {}
    stress = payload.get("pm_book_stress") or {}
    temporal = payload.get("temporal_scope") or {}
    statuses = dict(structural.get("mechanism_statuses") or {})
    triggered = stress.get("triggered_quant_signals") or []
    names = [item if isinstance(item, str) else str(item.get("name") or "") for item in triggered]
    names = [name for name in names if name]
    theme = structural.get("theme_proxy") or {}
    pm = payload.get("pm_response") or {}
    return {
        "as_of_date": temporal.get("analysis_as_of_date"),
        "data_cutoff": temporal.get("evidence_cutoff_timestamp") or temporal.get("analysis_cutoff_timestamp"),
        "overall_risk_state": (payload.get("market_backdrop") or {}).get("dm_inspired_market_state"),
        "deterministic_trigger_count": len(names),
        "triggered_channels": names,
        "structural_flags": list(structural.get("active_scenarios") or []),
        "supported_mechanisms": [key for key, status in statuses.items() if status == "triggered"],
        "mechanism_statuses": statuses,
        "mechanical_unwind_state": mechanical.get("unwind_state") or "NORMAL",
        "theme_cluster": list(theme.get("cluster_symbols") or []),
        "score_is_probability": False,
        "why_not_act_yet": pm.get("why_not_act_yet"),
    }


def _compact_from_mvp(payload: Mapping[str, Any]) -> dict[str, Any]:
    card = payload.get("deterministic_input") or {}
    unwind = payload.get("unwind") or {}
    mechanical = payload.get("mechanical_unwind") or {}
    pm = payload.get("pm_response") or {}
    statuses = {
        item["scenario"]: item.get("status") or "not_confirmed"
        for item in (unwind.get("mechanism_scenarios") or [])
        if isinstance(item, dict) and item.get("scenario")
    }
    triggered = card.get("triggered_quant_signals") or []
    names = [item if isinstance(item, str) else str(item.get("name") or "") for item in triggered]
    names = [name for name in names if name]
    theme = unwind.get("theme_concentration") or {}
    return {
        "as_of_date": card.get("as_of_date"),
        "data_cutoff": card.get("data_cutoff"),
        "overall_risk_state": card.get("overall_risk_state"),
        "deterministic_trigger_count": len(names),
        "triggered_channels": names,
        "structural_flags": list(unwind.get("active_scenarios") or []),
        "supported_mechanisms": [key for key, status in statuses.items() if status == "triggered"],
        "mechanism_statuses": statuses,
        "mechanical_unwind_state": mechanical.get("unwind_state") or "NORMAL",
        "theme_cluster": list(theme.get("cluster_symbols") or []),
        "score_is_probability": False,
        "why_not_act_yet": pm.get("why_not_act_yet"),
    }
