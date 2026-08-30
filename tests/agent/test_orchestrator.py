from __future__ import annotations

import time

from src.agent.models import AgentDecision, ToolCall
from src.agent.orchestrator import run_orchestrated_investigation
from src.agent.planner import HeuristicPlanner, ScriptedPlanner
from src.risk_state.models import InvestigationCase
from src.risk_state.provider import FrozenCaseProvider
from src.tools.registry import EmptyArgs, ToolRegistry, ToolSpec


def _dual_case() -> InvestigationCase:
    raw = FrozenCaseProvider().load("2026-05-29").model_dump(mode="json")
    raw["risk_state"]["mechanisms"]["bear_market_recovery_crash"] = "triggered"
    raw["risk_state"]["triggered_signals"] = ["high_volatility_recovery"]
    return InvestigationCase.model_validate(raw)


def _call(name: str) -> AgentDecision:
    return AgentDecision(
        action="call_tools",
        hypothesis="probe",
        reason="investigate",
        tool_calls=[ToolCall(id="1", name=name, args={})],
    )


def _finish() -> AgentDecision:
    return AgentDecision(
        action="finish",
        hypothesis="probe",
        reason="EVIDENCE_SUFFICIENT",
        final_assessment="Investigation complete.",
    )


def _registry(name: str, handler) -> ToolRegistry:
    return ToolRegistry([ToolSpec(name, EmptyArgs, handler, timeout_seconds=2.0)])


def test_specialist_allowlist_rejects_cross_mechanism_tool() -> None:
    planner = ScriptedPlanner([_call("get_factor_state"), _finish()])

    result = run_orchestrated_investigation(
        FrozenCaseProvider().load("2026-05-29"),
        planners={"crowding": planner},
        use_llm=False,
    )

    observation = result.specialist_results["crowding"].observations[0]
    assert observation.status == "error"
    assert observation.error_type == "unknown_tool"


def test_one_specialist_failure_does_not_remove_other_result() -> None:
    result = run_orchestrated_investigation(
        _dual_case(),
        planners={
            "crowding": ScriptedPlanner([RuntimeError("planner failed")]),
            "recovery": HeuristicPlanner(focus="dm_recovery"),
        },
        use_llm=False,
    )

    assert "crowding" not in result.specialist_results
    assert "recovery" in result.specialist_results
    crowding_decision = next(
        item for item in result.trace.decisions if item.get("actor") == "crowding"
    )
    assert crowding_decision["action"] == "failed"
    assert "planner failed" in crowding_decision["error"]


def test_specialists_overlap_on_one_shared_deadline() -> None:
    started: dict[str, float] = {}

    def slow(label: str):
        def handler(_ctx, _args):
            started[label] = time.monotonic()
            time.sleep(0.2)
            return {"ok": True}

        return handler

    before = time.monotonic()
    result = run_orchestrated_investigation(
        _dual_case(),
        planners={
            "crowding": ScriptedPlanner([_call("get_cluster_exposure"), _finish()]),
            "recovery": ScriptedPlanner([_call("get_factor_state"), _finish()]),
        },
        registries={
            "crowding": _registry("get_cluster_exposure", slow("crowding")),
            "recovery": _registry("get_factor_state", slow("recovery")),
        },
        overall_deadline_seconds=5,
        use_llm=False,
    )
    elapsed = time.monotonic() - before

    assert result.routing["schedule"] == "parallel_shared_deadline"
    assert set(started) == {"crowding", "recovery"}
    assert abs(started["crowding"] - started["recovery"]) < 0.15
    assert elapsed < 0.36


def test_combined_synthesis_is_rendered_once() -> None:
    result = run_orchestrated_investigation(_dual_case(), use_llm=False)

    for heading in ("Current read", "Observed:", "Inferred:", "Against:", "Not confirmed:"):
        assert result.report.count(heading) == 1
    assert "not merged into one score" in result.report.lower()
    assert result.trace.calibrated["score_is_probability"] is False
