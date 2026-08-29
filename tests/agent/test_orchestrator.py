"""Orchestrator routing and isolation. Planner is heuristic or scripted."""

from __future__ import annotations

import time

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
from tests.cases import (
    both_mechanisms_risk,
    leftover_quiet_risk,
    quiet_risk,
    recovery_risk,
    semi_unwind_risk,
)

CROWDING_HEADLINE = "hedge fund technology exposure reduction"
RECOVERY_HEADLINE = "loser stocks rebound sharply"


def _ok(_ctx, _args):
    return {"ok": True, "score_is_probability": False}


def _cluster(_ctx, _args):
    return {"cluster_symbols": ["CIEN", "COHR", "LITE"], "cluster_size": 3}


def _inspect(_ctx, args):
    return {"symbol": str(getattr(args, "symbol", "") or "COHR"), "in_theme_cluster": True, "in_book": True}


def _factor(_ctx, _args):
    return {"overall_risk_state": "panic_elevated", "score_is_probability": False}


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
        from src.tools.registry import CompareArgs, InspectArgs

        args_model = SearchArgs if name.startswith("search_") else EmptyArgs
        if name == "inspect_name":
            args_model = InspectArgs
        if name == "compare_prior_state":
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


def _run(risk, *, planners=None, registries=None, **kwargs):
    regs = {"crowding": _crowding_mocks(), "recovery": _recovery_mocks()}
    if registries:
        regs.update(registries)
    return run_orchestrated_investigation(
        as_of_date=risk["as_of_date"],
        risk_state=risk,
        planners=planners or {},
        registries=regs,
        use_llm=False,
        **kwargs,
    )


def _ok_names(result) -> list[str]:
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


def test_quiet_leftover_driver_spawns_nobody() -> None:
    for risk in (quiet_risk(), leftover_quiet_risk()):
        assert select_specialists(risk) == ()
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
    original = leftover_quiet_risk()
    _, fingerprint = freeze_risk_state(original)
    result = _run(original, planners={"crowding": forbidden, "recovery": forbidden})
    assert result.spawned == ()
    assert result.stop_reason == "NO_INVESTIGATION_NEEDED"
    assert result.observations == ()
    assert result.specialist_results == {}
    assert "no specialists spawned" in result.report.lower()
    assert not contains_forbidden(result.report)
    assert fingerprint_risk_state(result.risk_state) == fingerprint


def test_semi_unwind_runs_crowding_skips_recovery() -> None:
    result = _run(semi_unwind_risk(), planners={"crowding": HeuristicPlanner(focus="kl_crowding")})
    names = _ok_names(result)
    assert result.spawned == ("crowding",)
    assert "recovery" not in result.specialist_results
    assert "get_cluster_exposure" in names
    assert "search_positioning" in names or "search_news" in names
    assert "get_factor_state" not in names
    assert "Orchestrator spawned: crowding" in result.report


def test_march_2020_runs_recovery_skips_crowding() -> None:
    result = _run(recovery_risk(), planners={"recovery": HeuristicPlanner(focus="dm_recovery")})
    names = _ok_names(result)
    assert result.spawned == ("recovery",)
    assert "crowding" not in result.specialist_results
    assert "get_factor_state" in names
    assert "get_cluster_exposure" not in names
    factor = next(item for item in result.observations if item.name == "get_factor_state")
    assert factor.payload["score_is_probability"] is False


def test_both_flags_keep_evidence_isolated() -> None:
    result = _run(
        both_mechanisms_risk(),
        planners={
            "crowding": HeuristicPlanner(focus="kl_crowding"),
            "recovery": HeuristicPlanner(focus="dm_recovery"),
        },
    )
    crowding = result.specialist_results["crowding"]
    recovery = result.specialist_results["recovery"]
    assert result.spawned == ("crowding", "recovery")
    assert CROWDING_HEADLINE in _headlines(crowding)
    assert RECOVERY_HEADLINE not in _headlines(crowding)
    assert RECOVERY_HEADLINE in _headlines(recovery)
    assert CROWDING_HEADLINE not in _headlines(recovery)
    crowding_class = heuristic_classify(crowding.state.evidence, mechanism="kl_crowding")
    recovery_class = heuristic_classify(recovery.state.evidence, mechanism="dm_recovery")
    assert "loser rebound" not in " ".join(crowding_class.get("supported_claims") or []).lower()
    assert "technology" not in " ".join(recovery_class.get("supported_claims") or []).lower()


def test_specialist_unknown_tool_outside_allowlist() -> None:
    result = _run(
        semi_unwind_risk(),
        planners={
            "crowding": ScriptedPlanner(
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
            )
        },
        registries={"crowding": crowding_registry(_crowding_mocks())},
    )
    observation = result.specialist_results["crowding"].observations[0]
    assert observation.error_type == "unknown_tool"
    assert "get_factor_state" not in CROWDING_TOOL_NAMES


def test_combined_note_is_calibrated_once() -> None:
    result = _run(
        both_mechanisms_risk(),
        planners={
            "crowding": ScriptedPlanner(
                [
                    AgentDecision(
                        action="finish",
                        hypothesis="localized crowded unwind",
                        reason="EVIDENCE_SUFFICIENT",
                        final_assessment="Sell the longs. Localized crowding only.",
                    )
                ]
            ),
            "recovery": ScriptedPlanner(
                [
                    AgentDecision(
                        action="finish",
                        hypothesis="recovery-driven reversal",
                        reason="EVIDENCE_SUFFICIENT",
                        final_assessment="Crash probability is 80%. Recovery setup only.",
                    )
                ]
            ),
        },
    )
    report = result.report
    for heading in (
        "Current read",
        "Observed:",
        "Inferred:",
        "Against:",
        "Not confirmed:",
        "Citations:",
        "Investigation path:",
    ):
        assert heading in report
    assert report.count("Observed:") == 1
    assert "Orchestrator spawned: crowding, recovery" in report
    assert "crash probability" not in report.lower()
    assert "sell the longs" not in report.lower()
    assert not contains_forbidden(report)
    assert result.trace.calibrated["score_is_probability"] is False


def test_risk_state_fingerprint_unchanged() -> None:
    original = both_mechanisms_risk(monitoring_severity_score=78, score_is_probability=False)
    _, fingerprint = freeze_risk_state(original)
    result = _run(
        original,
        planners={
            "crowding": HeuristicPlanner(focus="kl_crowding"),
            "recovery": HeuristicPlanner(focus="dm_recovery"),
        },
    )
    assert fingerprint_risk_state(result.risk_state) == fingerprint
    assert result.risk_state["score_is_probability"] is False
    for specialist in result.specialist_results.values():
        specialist.state.assert_risk_unchanged()


def test_specialists_overlap_on_shared_wall_clock() -> None:
    started: dict[str, float] = {}

    def _slow(label: str):
        def handler(_ctx, _args):
            started[label] = time.monotonic()
            time.sleep(0.2)
            return {"ok": True, "score_is_probability": False}

        return handler

    crowding_planner = ScriptedPlanner(
        [
            AgentDecision(
                action="call_tools",
                hypothesis="localized crowded unwind",
                reason="probe",
                tool_calls=[ToolCall(id="1", name="get_cluster_exposure", args={})],
            ),
            AgentDecision(
                action="finish",
                hypothesis="localized crowded unwind",
                reason="EVIDENCE_SUFFICIENT",
                final_assessment="Crowding done.",
            ),
        ]
    )
    recovery_planner = ScriptedPlanner(
        [
            AgentDecision(
                action="call_tools",
                hypothesis="recovery-driven reversal",
                reason="probe",
                tool_calls=[ToolCall(id="1", name="get_factor_state", args={})],
            ),
            AgentDecision(
                action="finish",
                hypothesis="recovery-driven reversal",
                reason="EVIDENCE_SUFFICIENT",
                final_assessment="Recovery done.",
            ),
        ]
    )
    t0 = time.monotonic()
    result = _run(
        both_mechanisms_risk(),
        planners={"crowding": crowding_planner, "recovery": recovery_planner},
        registries={
            "crowding": _registry({"get_cluster_exposure": _slow("crowding")}),
            "recovery": _registry({"get_factor_state": _slow("recovery")}),
        },
        overall_deadline_seconds=5.0,
    )
    elapsed = time.monotonic() - t0
    assert result.spawned == ("crowding", "recovery")
    assert result.routing["schedule"] == "parallel_shared_deadline"
    assert result.routing["deadline_seconds"] == 5.0
    assert set(started) == {"crowding", "recovery"}
    assert set(result.specialist_results) == {"crowding", "recovery"}
    assert abs(started["crowding"] - started["recovery"]) < 0.15
    assert elapsed < 0.36
