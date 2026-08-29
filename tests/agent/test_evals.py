"""Behavior evals on frozen-case shaped states. Planner is heuristic or scripted."""

from __future__ import annotations

import pytest

from src.agent.loop import run_agent
from src.agent.planner import HeuristicPlanner
from src.agent.report import contains_forbidden
from tests.cases import leftover_quiet_risk, quiet_risk, recovery_risk, semi_unwind_risk


def _tool_names(result) -> list[str]:
    return [item.name for item in result.observations if item.status == "ok"]


@pytest.mark.parametrize("risk", [quiet_risk(), leftover_quiet_risk()])
def test_eval_quiet_does_not_search(risk) -> None:
    result = run_agent(
        as_of_date=risk["as_of_date"],
        risk_state=risk,
        planner=HeuristicPlanner(),
        max_steps=6,
    )
    assert result.stop_reason == "NO_INVESTIGATION_NEEDED"
    assert result.observations == ()
    assert result.state.step <= 1
    assert "Observed:" in result.report
    assert not contains_forbidden(result.report)


def test_eval_semi_unwind_uses_crowding_tools() -> None:
    original = semi_unwind_risk()
    result = run_agent(
        as_of_date="2026-05-29",
        risk_state=original,
        planner=HeuristicPlanner(),
        max_steps=6,
        overall_deadline_seconds=10,
    )
    names = _tool_names(result)
    assert result.stop_reason in {"EVIDENCE_SUFFICIENT", "UNRESOLVABLE", "MAX_STEPS"}
    assert "get_cluster_exposure" in names
    assert "search_positioning" in names or "search_news" in names
    assert result.risk_state["theme_cluster"] == ["CIEN", "COHR", "LITE"]
    assert "crash probability" not in result.report.lower()


def test_eval_march_2020_uses_recovery_tools() -> None:
    result = run_agent(
        as_of_date="2020-03-24",
        risk_state=recovery_risk(),
        planner=HeuristicPlanner(),
        max_steps=6,
        overall_deadline_seconds=10,
    )
    names = _tool_names(result)
    assert "get_factor_state" in names
    assert "search_news" in names
    factor = next(
        item for item in result.observations if item.name == "get_factor_state" and item.status == "ok"
    )
    assert factor.payload["score_is_probability"] is False


def test_eval_never_modifies_deterministic_state() -> None:
    original = semi_unwind_risk(monitoring_severity_score=78, score_is_probability=False)
    result = run_agent(risk_state=original, planner=HeuristicPlanner())
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
    result = run_agent(risk_state=semi_unwind_risk(), planner=HeuristicPlanner())
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
