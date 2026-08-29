"""Orchestrator + mechanism-specialist tests. No live LLM required."""

from __future__ import annotations

from src.agent.models import AgentDecision, ToolCall
from src.agent.orchestrator import run_orchestrated_investigation, select_specialists
from src.agent.planner import HeuristicPlanner, ScriptedPlanner
from src.agent.report import contains_forbidden
from src.agent.state import fingerprint_risk_state, freeze_risk_state
from src.agent_prompts import heuristic_classify
from src.tools.registry import (
    CROWDING_TOOL_NAMES,
    EmptyArgs,
    SearchArgs,
    ToolRegistry,
    ToolSpec,
    crowding_registry,
)


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


def _both_risk(**overrides):
    payload = _semi_unwind_risk()
    payload.update(
        {
            "deterministic_trigger_count": 2,
            "triggered_channels": ["portfolio_drawdown", "short_loss_in_recovery"],
            "structural_flags": [
                "crowded_theme_unwind",
                "portfolio_concentration",
                "bear_market_recovery_crash",
            ],
            "supported_mechanisms": [
                "crowded_theme_unwind",
                "bear_market_recovery_crash",
            ],
            "mechanism_statuses": {
                "crowded_theme_unwind": "triggered",
                "bear_market_recovery_crash": "triggered",
            },
        }
    )
    payload.update(overrides)
    return payload


CROWDING_HEADLINE = "hedge fund technology exposure reduction"
RECOVERY_HEADLINE = "loser stocks rebound sharply"


def _ok(_ctx, _args):
    return {"ok": True, "score_is_probability": False}


def _cluster(_ctx, _args):
    return {"cluster_symbols": ["CIEN", "COHR", "LITE"], "cluster_size": 3}


def _inspect(_ctx, args):
    symbol = str(getattr(args, "symbol", "") or "COHR")
    return {"symbol": symbol, "in_theme_cluster": True, "in_book": True}


def _factor(_ctx, _args):
    return {
        "overall_risk_state": "panic_elevated",
        "score_is_probability": False,
        "limitation": "relative band",
    }


def _prior(_ctx, _args):
    return {"status": "unavailable", "changes": [], "limitation": "no prior loaded"}


def _docs(headline: str):
    def handler(_ctx, _args):
        return {
            "documents": [
                {
                    "evidence_id": headline[:12],
                    "published_at": "2026-05-04",
                    "headline": headline,
                    "snippet": headline,
                }
            ]
        }

    return handler


def _registry(handlers: dict, *, evidence: set | None = None) -> ToolRegistry:
    specs = []
    for name, handler in handlers.items():
        args_model = SearchArgs if name.startswith("search_") else EmptyArgs
        if name == "inspect_name":
            from src.tools.registry import InspectArgs

            args_model = InspectArgs
        if name == "compare_prior_state":
            from src.tools.registry import CompareArgs

            args_model = CompareArgs
        specs.append(
            ToolSpec(
                name=name,
                args_model=args_model,
                handler=handler,
                timeout_seconds=2.0,
                returns_evidence=name in (evidence or set()),
            )
        )
    return ToolRegistry(specs)


def _crowding_mocks() -> ToolRegistry:
    return _registry(
        {
            "get_cluster_exposure": _cluster,
            "search_positioning": _docs(CROWDING_HEADLINE),
            "search_news": _docs(CROWDING_HEADLINE),
            "inspect_name": _inspect,
            "get_book_state": _ok,
        },
        evidence={"search_positioning", "search_news"},
    )


def _recovery_mocks() -> ToolRegistry:
    return _registry(
        {
            "get_factor_state": _factor,
            "get_book_state": _ok,
            "search_news": _docs(RECOVERY_HEADLINE),
            "compare_prior_state": _prior,
        },
        evidence={"search_news"},
    )


def _tool_names(result) -> list[str]:
    return [item.name for item in result.observations if item.status == "ok"]


def _headlines(result) -> list[str]:
    found: list[str] = []
    for item in result.observations:
        payload = item.payload if isinstance(item.payload, dict) else {}
        for doc in payload.get("documents") or []:
            if isinstance(doc, dict) and doc.get("headline"):
                found.append(str(doc["headline"]))
    for doc in result.state.evidence:
        if doc.get("headline"):
            found.append(str(doc["headline"]))
    return found


def test_select_specialists_quiet_spawns_nobody() -> None:
    assert select_specialists(_quiet_risk()) == ()


def test_quiet_january_2024_spawns_zero_and_does_not_search() -> None:
    original = _quiet_risk()
    _, fingerprint = freeze_risk_state(original)
    forbidden = ScriptedPlanner(
        [
            AgentDecision(
                action="call_tools",
                hypothesis="should not run",
                reason="investigate",
                tool_calls=[ToolCall(id="1", name="search_news", args={"query": "crowding"})],
            )
        ]
    )
    result = run_orchestrated_investigation(
        as_of_date="2024-01-05",
        risk_state=original,
        crowding_planner=forbidden,
        recovery_planner=forbidden,
        crowding_tools=_crowding_mocks(),
        recovery_tools=_recovery_mocks(),
        use_llm=False,
        verbose=False,
    )
    assert result.spawned == ()
    assert result.stop_reason == "NO_INVESTIGATION_NEEDED"
    assert result.observations == ()
    assert result.specialist_results == {}
    assert "no specialists spawned" in result.report.lower()
    assert "Observed:" in result.report
    assert not contains_forbidden(result.report)
    assert fingerprint_risk_state(result.risk_state) == fingerprint


def test_semi_unwind_runs_crowding_skips_recovery() -> None:
    original = _semi_unwind_risk()
    result = run_orchestrated_investigation(
        as_of_date="2026-05-29",
        risk_state=original,
        crowding_planner=HeuristicPlanner(focus="kl_crowding"),
        crowding_tools=_crowding_mocks(),
        recovery_tools=_recovery_mocks(),
        use_llm=False,
        verbose=False,
    )
    assert result.spawned == ("crowding",)
    assert "recovery" not in result.specialist_results
    names = _tool_names(result)
    assert "get_cluster_exposure" in names
    assert "search_positioning" in names or "search_news" in names
    assert "get_factor_state" not in names
    assert "compare_prior_state" not in names
    crowding = result.specialist_results["crowding"]
    assert crowding.stop_reason in {"EVIDENCE_SUFFICIENT", "UNRESOLVABLE", "MAX_STEPS"}
    assert "Orchestrator spawned: crowding" in result.report


def test_march_2020_runs_recovery_skips_crowding() -> None:
    result = run_orchestrated_investigation(
        as_of_date="2020-03-24",
        risk_state=_recovery_risk(),
        recovery_planner=HeuristicPlanner(focus="dm_recovery"),
        crowding_tools=_crowding_mocks(),
        recovery_tools=_recovery_mocks(),
        use_llm=False,
        verbose=False,
    )
    assert result.spawned == ("recovery",)
    assert "crowding" not in result.specialist_results
    names = _tool_names(result)
    assert "get_factor_state" in names
    assert "search_news" in names
    assert "get_cluster_exposure" not in names
    assert "search_positioning" not in names
    factor = next(item for item in result.observations if item.name == "get_factor_state")
    assert factor.status == "ok"
    assert factor.payload["score_is_probability"] is False


def test_both_flags_keep_evidence_isolated() -> None:
    result = run_orchestrated_investigation(
        as_of_date="2026-05-29",
        risk_state=_both_risk(),
        crowding_planner=HeuristicPlanner(focus="kl_crowding"),
        recovery_planner=HeuristicPlanner(focus="dm_recovery"),
        crowding_tools=_crowding_mocks(),
        recovery_tools=_recovery_mocks(),
        use_llm=False,
        verbose=False,
    )
    assert result.spawned == ("crowding", "recovery")
    crowding = result.specialist_results["crowding"]
    recovery = result.specialist_results["recovery"]
    crowding_headlines = _headlines(crowding)
    recovery_headlines = _headlines(recovery)
    assert CROWDING_HEADLINE in crowding_headlines
    assert RECOVERY_HEADLINE not in crowding_headlines
    assert RECOVERY_HEADLINE in recovery_headlines
    assert CROWDING_HEADLINE not in recovery_headlines

    crowding_class = heuristic_classify(crowding.state.evidence, mechanism="kl_crowding")
    recovery_class = heuristic_classify(recovery.state.evidence, mechanism="dm_recovery")
    crowding_blob = " ".join(
        crowding_class.get("supported_claims") or []
        + crowding_class.get("contradicting_claims") or []
        + [str(doc.get("headline") or "") for doc in crowding.state.evidence]
    ).lower()
    recovery_blob = " ".join(
        recovery_class.get("supported_claims") or []
        + recovery_class.get("contradicting_claims") or []
        + [str(doc.get("headline") or "") for doc in recovery.state.evidence]
    ).lower()
    assert "loser stocks rebound" not in crowding_blob
    assert "technology exposure reduction" not in recovery_blob
    assert "loser rebound" not in " ".join(crowding_class.get("supported_claims") or []).lower()
    assert "technology" not in " ".join(recovery_class.get("supported_claims") or []).lower()


def test_specialist_unknown_tool_outside_allowlist() -> None:
    result = run_orchestrated_investigation(
        as_of_date="2026-05-29",
        risk_state=_semi_unwind_risk(),
        crowding_planner=ScriptedPlanner(
            [
                AgentDecision(
                    action="call_tools",
                    hypothesis="localized crowded unwind",
                    reason="probe recovery by mistake",
                    tool_calls=[ToolCall(id="1", name="get_factor_state", args={})],
                ),
                AgentDecision(
                    action="finish",
                    hypothesis="localized crowded unwind",
                    reason="EVIDENCE_SUFFICIENT",
                    final_assessment="Crowding note only.",
                ),
            ]
        ),
        crowding_tools=crowding_registry(_crowding_mocks()),
        use_llm=False,
        verbose=False,
    )
    assert result.spawned == ("crowding",)
    observation = result.specialist_results["crowding"].observations[0]
    assert observation.status == "error"
    assert observation.error_type == "unknown_tool"
    assert "get_factor_state" not in CROWDING_TOOL_NAMES


def test_combined_report_calibration_and_no_trade_language() -> None:
    result = run_orchestrated_investigation(
        as_of_date="2026-05-29",
        risk_state=_both_risk(),
        crowding_planner=ScriptedPlanner(
            [
                AgentDecision(
                    action="finish",
                    hypothesis="localized crowded unwind",
                    reason="EVIDENCE_SUFFICIENT",
                    final_assessment="Sell the longs. Localized crowding only.",
                )
            ]
        ),
        recovery_planner=ScriptedPlanner(
            [
                AgentDecision(
                    action="finish",
                    hypothesis="recovery-driven reversal",
                    reason="EVIDENCE_SUFFICIENT",
                    final_assessment="Crash probability is 80%. Recovery setup only.",
                )
            ]
        ),
        crowding_tools=_crowding_mocks(),
        recovery_tools=_recovery_mocks(),
        use_llm=False,
        verbose=False,
    )
    report = result.report
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
        assert heading in report
    assert "Crowding (Khandani–Lo)" in report
    assert "Recovery (Daniel–Moskowitz)" in report
    assert "crash probability" not in report.lower()
    assert "sell the longs" not in report.lower()
    assert not contains_forbidden(report)
    assert result.trace.calibrated["score_is_probability"] is False
    assert result.trace.spawned == ["crowding", "recovery"]


def test_risk_state_fingerprint_unchanged_after_orchestration() -> None:
    original = _both_risk(monitoring_severity_score=78, score_is_probability=False)
    _, fingerprint = freeze_risk_state(original)
    result = run_orchestrated_investigation(
        risk_state=original,
        crowding_planner=HeuristicPlanner(focus="kl_crowding"),
        recovery_planner=HeuristicPlanner(focus="dm_recovery"),
        crowding_tools=_crowding_mocks(),
        recovery_tools=_recovery_mocks(),
        use_llm=False,
        verbose=False,
    )
    assert fingerprint_risk_state(original) == fingerprint
    assert fingerprint_risk_state(result.risk_state) == fingerprint
    assert result.risk_state["monitoring_severity_score"] == 78
    assert result.risk_state["score_is_probability"] is False
    for specialist in result.specialist_results.values():
        specialist.state.assert_risk_unchanged()
        assert specialist.risk_state["deterministic_trigger_count"] == original[
            "deterministic_trigger_count"
        ]
