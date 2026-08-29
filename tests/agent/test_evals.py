"""Behavior evals on frozen-case shaped states. Planner is heuristic or scripted."""

from __future__ import annotations

from src.agent.loop import run_agent
from src.agent.planner import HeuristicPlanner
from src.agent.report import contains_forbidden


def _quiet_risk(**overrides):
    payload = {
        "as_of_date": "2024-01-05",
        "data_cutoff": "2024-01-05T16:00:00-05:00",
        "overall_risk_state": "bear_low_volatility",
        "deterministic_trigger_count": 0,
        "triggered_channels": [],
        "structural_flags": [],
        "supported_mechanisms": [],
        "mechanism_statuses": {
            "bear_market_recovery_crash": "not_confirmed",
            "short_book_reversal_crash": "not_confirmed",
            "crowded_theme_unwind": "not_confirmed",
        },
        "mechanical_unwind_state": "NORMAL",
        "primary_driver": None,
        "theme_cluster": [],
        "score_is_probability": False,
        "next_checks": ["Continue ordinary monitoring."],
    }
    payload.update(overrides)
    return payload


def _semi_unwind_risk(**overrides):
    return _quiet_risk(
        as_of_date="2026-05-29",
        data_cutoff="2026-05-29T16:00:00-04:00",
        overall_risk_state="normal",
        deterministic_trigger_count=1,
        triggered_channels=["portfolio_drawdown"],
        structural_flags=["crowded_theme_unwind", "portfolio_concentration"],
        supported_mechanisms=["crowded_theme_unwind"],
        mechanism_statuses={"crowded_theme_unwind": "triggered"},
        mechanical_unwind_state="FRAGILITY_BUILDING",
        primary_driver="crowded_unwind",
        theme_cluster=["CIEN", "COHR", "LITE"],
        why_not_act_yet="Liquidity is still absorbing; shorts are not being squeezed.",
        **overrides,
    )


def _recovery_risk(**overrides):
    return _quiet_risk(
        as_of_date="2020-03-24",
        data_cutoff="2020-03-24T16:00:00-04:00",
        overall_risk_state="panic_elevated",
        deterministic_trigger_count=2,
        triggered_channels=["short_loss_in_recovery", "high_volatility_recovery"],
        structural_flags=["bear_market_recovery_crash"],
        supported_mechanisms=["bear_market_recovery_crash"],
        mechanism_statuses={"bear_market_recovery_crash": "triggered"},
        mechanical_unwind_state="ACTIVE_UNWIND",
        primary_driver="dm_recovery",
        theme_cluster=[],
        **overrides,
    )


def _tool_names(result) -> list[str]:
    return [item.name for item in result.observations if item.status == "ok"]


def test_eval_quiet_january_2024_does_not_search() -> None:
    original = _quiet_risk()
    result = run_agent(
        as_of_date="2024-01-05",
        risk_state=original,
        planner=HeuristicPlanner(),
        verbose=False,
        max_steps=6,
    )
    assert result.stop_reason == "NO_INVESTIGATION_NEEDED"
    assert result.observations == ()
    assert result.state.step <= 1
    assert result.risk_state == original or result.risk_state["deterministic_trigger_count"] == 0
    assert "Observed:" in result.report
    assert "Not confirmed:" in result.report
    assert not contains_forbidden(result.report)


def test_eval_semi_unwind_uses_crowding_tools() -> None:
    original = _semi_unwind_risk()
    fingerprint = original["deterministic_trigger_count"]
    result = run_agent(
        as_of_date="2026-05-29",
        risk_state=original,
        planner=HeuristicPlanner(),
        verbose=False,
        max_steps=6,
        overall_deadline_seconds=10,
    )
    names = _tool_names(result)
    assert result.state.step <= 6
    assert result.stop_reason in {"EVIDENCE_SUFFICIENT", "UNRESOLVABLE", "MAX_STEPS"}
    assert "get_cluster_exposure" in names
    assert "search_positioning" in names or "search_news" in names
    assert result.risk_state["deterministic_trigger_count"] == fingerprint
    assert result.risk_state["theme_cluster"] == ["CIEN", "COHR", "LITE"]
    assert "Observed:" in result.report
    assert "Inferred:" in result.report
    assert "Not confirmed:" in result.report
    assert "crash probability" not in result.report.lower()
    assert result.trace.stop_reason == result.stop_reason
    assert result.trace.run_id


def test_eval_march_2020_uses_recovery_tools() -> None:
    result = run_agent(
        as_of_date="2020-03-24",
        risk_state=_recovery_risk(),
        planner=HeuristicPlanner(),
        verbose=False,
        max_steps=6,
        overall_deadline_seconds=10,
    )
    names = _tool_names(result)
    assert "get_factor_state" in names
    assert "search_news" in names
    assert result.stop_reason in {"EVIDENCE_SUFFICIENT", "UNRESOLVABLE", "MAX_STEPS"}
    for item in result.observations:
        if item.status == "ok" and isinstance(item.payload, dict):
            assert item.payload.get("score_is_probability") is not True or item.name != "get_factor_state"
    factor = next(item for item in result.observations if item.name == "get_factor_state" and item.status == "ok")
    assert factor.payload["score_is_probability"] is False
    assert "Observed:" in result.report


def test_eval_never_modifies_deterministic_state() -> None:
    original = _semi_unwind_risk(monitoring_severity_score=78, score_is_probability=False)
    result = run_agent(
        risk_state=original,
        planner=HeuristicPlanner(),
        verbose=False,
    )
    assert result.risk_state["monitoring_severity_score"] == 78
    assert result.risk_state["score_is_probability"] is False
    result.state._risk_state["deterministic_trigger_count"] = 99
    try:
        result.state.assert_risk_unchanged()
        mutated = True
    except RuntimeError:
        mutated = False
    assert mutated is False
    result.state._risk_state["deterministic_trigger_count"] = original["deterministic_trigger_count"]


def test_eval_report_calibration_sections_exist() -> None:
    result = run_agent(risk_state=_semi_unwind_risk(), planner=HeuristicPlanner(), verbose=False)
    for heading in (
        "Current read",
        "Observed:",
        "Inferred:",
        "Against:",
        "Not confirmed:",
        "Investigation path:",
        "What changed:",
        "Next useful check:",
    ):
        assert heading in result.report
    assert "forced" in result.report.lower() or "Not confirmed" in result.report
