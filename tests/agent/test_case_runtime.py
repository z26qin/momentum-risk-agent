from __future__ import annotations

import os
import sys

import pytest
from pydantic import ValidationError

from scripts import run_agent as cli
from scripts.run_agent import _build_parser
from src.agent.loop import run_agent
from src.agent.models import AgentDecision, ToolCall
from src.agent.orchestrator import run_orchestrated_investigation
from src.agent.planner import LLMPlanner
from src.risk_state.models import InvestigationCase
from src.risk_state.provider import FrozenCaseProvider


def _case(as_of_date: str) -> InvestigationCase:
    return FrozenCaseProvider().load(as_of_date)


def _dual_case() -> InvestigationCase:
    raw = _case("2026-05-29").model_dump(mode="json")
    raw["risk_state"]["mechanisms"]["bear_market_recovery_crash"] = "triggered"
    raw["risk_state"]["triggered_signals"] = ["high_volatility_recovery"]
    return InvestigationCase.model_validate(raw)


def test_quiet_case_spawns_nobody_and_runs_no_tools() -> None:
    result = run_orchestrated_investigation(_case("2024-01-05"), use_llm=False)

    assert result.spawned == ()
    assert result.stop_reason == "NO_INVESTIGATION_NEEDED"
    assert result.observations == ()
    assert "no specialists spawned" in result.report.lower()


def test_may_case_routes_only_to_crowding() -> None:
    result = run_orchestrated_investigation(_case("2026-05-29"), use_llm=False)

    assert result.spawned == ("crowding",)
    assert result.stop_reason == "EVIDENCE_SUFFICIENT"
    assert {item.name for item in result.observations if item.status == "ok"} >= {
        "get_cluster_exposure",
        "search_positioning",
        "search_news",
        "inspect_name",
    }
    assert "crash probability" not in result.report.lower()


def test_march_case_routes_only_to_recovery() -> None:
    result = run_orchestrated_investigation(_case("2020-03-24"), use_llm=False)

    assert result.spawned == ("recovery",)
    assert {item.name for item in result.observations if item.status == "ok"} >= {
        "get_factor_state",
        "search_news",
        "compare_prior_state",
    }
    assert result.risk_state.severity.score_is_probability is False


def test_dual_mechanism_case_keeps_specialist_results_isolated() -> None:
    result = run_orchestrated_investigation(_dual_case(), use_llm=False)

    assert result.spawned == ("crowding", "recovery")
    assert set(result.specialist_results) == {"crowding", "recovery"}
    assert result.routing["schedule"] == "parallel_shared_deadline"
    assert result.trace.calibrated["score_is_probability"] is False


def test_result_exposes_the_same_immutable_risk_state_contract() -> None:
    case = _case("2026-05-29")

    result = run_orchestrated_investigation(case, use_llm=False)

    assert result.risk_state == case.risk_state
    with pytest.raises(ValidationError):
        result.risk_state.severity.score = 1


def test_llm_planner_still_accepts_structured_json_only() -> None:
    def transport(**kwargs):
        del kwargs
        return (
            '{"action":"finish","hypothesis":"ordinary noise",'
            '"reason":"NO_INVESTIGATION_NEEDED","tool_calls":[],'
            '"final_assessment":"Quiet book.","open_questions":[]}'
        )

    result = run_agent(
        _case("2024-01-05"),
        planner=LLMPlanner(api_key="test", transport=transport),
    )

    assert result.planner_kind == "llm"
    assert result.stop_reason == "NO_INVESTIGATION_NEEDED"


def test_agent_decision_rejects_actions_with_inconsistent_tool_calls() -> None:
    with pytest.raises(ValidationError):
        AgentDecision(
            action="finish",
            hypothesis="done",
            reason="EVIDENCE_SUFFICIENT",
            tool_calls=[ToolCall(name="get_book_state")],
        )
    with pytest.raises(ValidationError):
        AgentDecision(action="call_tools", hypothesis="probe", reason="investigate")


def test_cli_parser_has_one_execution_path() -> None:
    parser = _build_parser()

    args = parser.parse_args(["--as-of-date", "2026-05-29", "--planner", "heuristic"])
    assert args.as_of_date == "2026-05-29"
    assert not hasattr(args, "mode")
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "single"])


def test_cli_loads_local_deepseek_env_before_planner_selection(
    tmp_path, monkeypatch, capsys
) -> None:
    (tmp_path / ".env").write_text(
        'DEEPSEEK_API_KEY=""\nDEEPSEEK_MODEL="deepseek-v4-pro"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "__test_cleanup_sentinel__")
    monkeypatch.setenv("DEEPSEEK_MODEL", "__test_cleanup_sentinel__")
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    monkeypatch.delenv("DEEPSEEK_MODEL")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_agent.py", "--as-of-date", "2024-01-05", "--planner", "heuristic"],
    )

    assert cli.main() == 0
    assert os.environ["DEEPSEEK_API_KEY"] == ""
    assert os.environ["DEEPSEEK_MODEL"] == "deepseek-v4-pro"
    assert "Current read" in capsys.readouterr().out


def test_cli_explicit_llm_mode_rejects_an_empty_api_key(
    tmp_path, monkeypatch, capsys
) -> None:
    (tmp_path / ".env").write_text('DEEPSEEK_API_KEY=""\n', encoding="utf-8")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "__test_cleanup_sentinel__")
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    monkeypatch.setattr(cli, "ROOT", tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_agent.py", "--as-of-date", "2026-05-29", "--planner", "llm"],
    )

    assert cli.main() == 2
    captured = capsys.readouterr()
    assert "DEEPSEEK_API_KEY" in captured.err
    assert "Current read" not in captured.out
