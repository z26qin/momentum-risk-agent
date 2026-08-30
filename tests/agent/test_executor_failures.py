"""Failure-mode tests for the deterministic executor and bounded loop."""

from __future__ import annotations

import time

from pydantic import BaseModel, ConfigDict, Field

from src.agent.loop import run_agent
from src.agent.models import AgentDecision, ToolCall
from src.agent.planner import ScriptedPlanner
from src.agent.synthesis import sanitize_text
from src.risk_state.provider import FrozenCaseProvider
from src.tools.registry import EmptyArgs, SearchArgs, ToolRegistry, ToolSpec


def _crowding_case():
    return FrozenCaseProvider().load("2026-05-29")


def _quiet_case():
    return FrozenCaseProvider().load("2024-01-05")


def _decision(*names: str, **kwargs) -> AgentDecision:
    calls = [
        ToolCall(id=f"c{i}", name=name, args=kwargs.get("args", {}).get(name, {}))
        for i, name in enumerate(names, start=1)
    ]
    return AgentDecision(
        action="call_tools",
        hypothesis=kwargs.get("hypothesis", "localized crowded unwind"),
        reason=kwargs.get("reason", "investigate"),
        tool_calls=calls,
        open_questions=kwargs.get("open_questions", []),
    )


def _finish(**kwargs) -> AgentDecision:
    return AgentDecision(
        action="finish",
        hypothesis=kwargs.get("hypothesis", "localized crowded unwind"),
        reason=kwargs.get("reason", "EVIDENCE_SUFFICIENT"),
        final_assessment=kwargs.get("final_assessment", "Localized pressure only."),
    )


class _OkArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _registry(handlers: dict, *, timeouts: dict | None = None, evidence: set | None = None):
    specs = []
    for name, handler in handlers.items():
        args_model = SearchArgs if name.startswith("search_") else EmptyArgs
        if name == "inspect_name":
            from src.tools.registry import InspectArgs

            args_model = InspectArgs
        specs.append(
            ToolSpec(
                name=name,
                args_model=args_model,
                handler=handler,
                timeout_seconds=(timeouts or {}).get(name, 2.0),
                returns_evidence=name in (evidence or set()),
            )
        )
    return ToolRegistry(specs)


def _ok(_ctx, _args):
    return {"ok": True}


def _news_docs(*docs):
    def handler(_ctx, args):
        del args
        return {"documents": [dict(item) for item in docs], "limitation": "test"}

    return handler


def test_malformed_planner_output_fails_closed() -> None:
    original = _crowding_case()
    result = run_agent(
        original,
        planner=ScriptedPlanner([{"hypothesis": "oops"}]),
        registry=_registry({"get_book_state": _ok}),
        overall_deadline_seconds=5,
    )
    assert result.stop_reason == "MALFORMED_PLANNER_OUTPUT"
    assert result.risk_state.monitoring_trigger_count == 0
    assert result.observations == ()


def test_unknown_tool_becomes_observation() -> None:
    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner(
            [
                _decision("not_a_real_tool"),
                _finish(),
            ]
        ),
        registry=_registry({"get_book_state": _ok}),
    )
    assert result.observations[0].status == "error"
    assert result.observations[0].error_type == "unknown_tool"
    assert result.stop_reason == "EVIDENCE_SUFFICIENT"


def test_invalid_tool_args_do_not_crash() -> None:
    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner(
            [
                AgentDecision(
                    action="call_tools",
                    hypothesis="x",
                    reason="y",
                    tool_calls=[ToolCall(id="1", name="search_news", args={})],
                ),
                _finish(),
            ]
        ),
        registry=_registry({"search_news": _news_docs()}, evidence={"search_news"}),
    )
    assert result.observations[0].error_type == "invalid_args"
    assert result.stop_reason == "EVIDENCE_SUFFICIENT"


def test_duplicate_tool_call_is_not_reexecuted() -> None:
    calls = {"n": 0}

    def news(_ctx, args):
        del args
        calls["n"] += 1
        return {
            "documents": [
                {
                    "evidence_id": "E1",
                    "published_at": "2026-05-04",
                    "headline": "hedge fund technology exposure reduction",
                    "snippet": "hedge funds cut tech",
                }
            ]
        }

    query = {"search_news": {"query": "crowded unwind"}}
    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner(
            [
                _decision("search_news", args=query),
                _decision("search_news", args=query),
                _finish(),
            ]
        ),
        registry=_registry({"search_news": news}, evidence={"search_news"}),
    )
    statuses = [item.status for item in result.observations]
    assert calls["n"] == 1
    assert "ok" in statuses
    assert "duplicate" in statuses


def test_in_batch_duplicate_is_canonicalized() -> None:
    calls = {"n": 0}

    def news(_ctx, args):
        del args
        calls["n"] += 1
        return {"documents": []}

    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner(
            [
                AgentDecision(
                    action="call_tools",
                    hypothesis="x",
                    reason="y",
                    tool_calls=[
                        ToolCall(id="a", name="search_news", args={"query": "Crowded Unwind"}),
                        ToolCall(id="b", name="search_news", args={"query": "  crowded   unwind "}),
                    ],
                ),
                _finish(),
            ]
        ),
        registry=_registry({"search_news": news}, evidence={"search_news"}),
    )
    assert calls["n"] == 1
    assert {item.status for item in result.observations} == {"ok", "duplicate"}


def test_tool_timeout_is_isolated() -> None:
    def slow(_ctx, _args):
        time.sleep(1.0)
        return {"ok": True}

    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner([_decision("get_book_state"), _finish()]),
        registry=_registry({"get_book_state": slow}, timeouts={"get_book_state": 0.05}),
        overall_deadline_seconds=3,
    )
    assert result.observations[0].status == "timeout"
    assert result.stop_reason == "EVIDENCE_SUFFICIENT"


def test_one_parallel_tool_failing_does_not_kill_run() -> None:
    def boom(_ctx, _args):
        raise RuntimeError("backend down")

    def ok(_ctx, _args):
        return {"cluster_symbols": ["COHR"]}

    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner(
            [
                AgentDecision(
                    action="call_tools",
                    hypothesis="x",
                    reason="y",
                    tool_calls=[
                        ToolCall(id="a", name="get_cluster_exposure", args={}),
                        ToolCall(id="b", name="get_book_state", args={}),
                    ],
                ),
                _finish(),
            ]
        ),
        registry=_registry({"get_cluster_exposure": ok, "get_book_state": boom}),
    )
    by_name = {item.name: item for item in result.observations}
    assert by_name["get_cluster_exposure"].status == "ok"
    assert by_name["get_book_state"].status == "error"


def test_given_transient_handler_error_when_budget_remains_then_tool_retries_once() -> None:
    calls = {"count": 0}

    def flaky(_ctx, _args):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient")
        return {"ok": True}

    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner([_decision("get_book_state"), _finish()]),
        registry=_registry({"get_book_state": flaky}),
    )

    assert calls["count"] == 2
    assert result.observations[0].status == "ok"
    assert result.observations[0].attempts == 2


def test_given_transient_timeout_when_budget_remains_then_tool_retries_once() -> None:
    calls = {"count": 0}

    def flaky(_ctx, _args):
        calls["count"] += 1
        if calls["count"] == 1:
            time.sleep(0.05)
        return {"ok": True}

    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner([_decision("get_book_state"), _finish()]),
        registry=_registry({"get_book_state": flaky}, timeouts={"get_book_state": 0.01}),
    )

    assert calls["count"] == 2
    assert result.observations[0].status == "ok"
    assert result.observations[0].attempts == 2


def test_given_two_handler_failures_when_executed_then_final_error_is_isolated() -> None:
    calls = {"count": 0}

    def broken(_ctx, _args):
        calls["count"] += 1
        raise RuntimeError("still down")

    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner([_decision("get_book_state"), _finish()]),
        registry=_registry({"get_book_state": broken}),
    )

    assert calls["count"] == 2
    assert result.observations[0].status == "error"
    assert result.observations[0].attempts == 2
    assert result.stop_reason == "EVIDENCE_SUFFICIENT"
    assert "Observed:" in result.report


def test_overall_deadline_exceeded() -> None:
    def slow(_ctx, _args):
        time.sleep(1.0)
        return {"ok": True}

    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner([_decision("get_book_state")]),
        registry=_registry({"get_book_state": slow}, timeouts={"get_book_state": 5.0}),
        overall_deadline_seconds=0.05,
        max_steps=6,
    )
    assert result.stop_reason in {"DEADLINE_EXCEEDED", "PLANNER_TIMEOUT"}
    if result.observations:
        assert result.observations[0].status in {"timeout", "deadline"}


def test_given_valid_and_future_evidence_when_synthesized_then_only_valid_is_cited() -> None:
    docs = _news_docs(
        {
            "evidence_id": "OK",
            "published_at": "2026-05-04",
            "headline": "hedge fund technology exposure reduction",
            "snippet": "tech reduction",
        },
        {
            "evidence_id": "FUTURE",
            "published_at": "2026-06-15",
            "headline": "future leak",
            "snippet": "should be dropped",
        },
    )
    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner(
            [
                AgentDecision(
                    action="call_tools",
                    hypothesis="x",
                    reason="y",
                    tool_calls=[ToolCall(id="1", name="search_news", args={"query": "crowding"})],
                ),
                _finish(),
            ]
        ),
        registry=_registry({"search_news": docs}, evidence={"search_news"}),
    )
    payload = result.observations[0].payload
    ids = {item["evidence_id"] for item in payload["documents"]}
    assert "OK" in ids
    assert "FUTURE" not in ids
    assert result.observations[0].discarded_post_cutoff >= 1
    assert "Citations:" in result.report
    assert "[OK] 2026-05-04 hedge fund technology exposure reduction" in result.report
    assert "[FUTURE]" not in result.report
    assert "future leak" not in result.report.lower()


def test_repeated_same_search_stops_without_looping() -> None:
    def news(_ctx, args):
        del args
        return {"documents": []}

    query_decision = AgentDecision(
        action="call_tools",
        hypothesis="x",
        reason="y",
        tool_calls=[ToolCall(id="1", name="search_news", args={"query": "crowded unwind"})],
    )
    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner([query_decision, query_decision, query_decision]),
        registry=_registry({"search_news": news}, evidence={"search_news"}),
        max_steps=6,
    )
    assert result.stop_reason == "UNRESOLVABLE"
    assert sum(1 for item in result.observations if item.status == "ok") == 1
    assert result.state.step <= 3


def test_max_steps_reached() -> None:
    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner(
            [
                _decision("get_book_state"),
                _decision("get_factor_state"),
                _decision("get_cluster_exposure"),
            ]
        ),
        registry=_registry(
            {
                "get_book_state": _ok,
                "get_factor_state": _ok,
                "get_cluster_exposure": _ok,
            }
        ),
        max_steps=2,
    )
    assert result.stop_reason == "MAX_STEPS"
    assert result.state.step == 2


def test_trade_language_is_stripped_from_report() -> None:
    result = run_agent(
        _crowding_case(),
        planner=ScriptedPlanner(
            [
                _finish(
                    final_assessment="Sell the longs overnight. Localized crowding only."
                )
            ]
        ),
        registry=_registry({"get_book_state": _ok}),
    )
    assert "sell the longs" not in result.report.lower()
    assert "Observed:" in result.report
    assert "Not confirmed:" in result.report


def test_trade_filter_preserves_factual_short_leg_language() -> None:
    text = sanitize_text("Short NVDA now. Short-leg pain is observed.")

    assert text == "Short-leg pain is observed."


def test_llm_planner_accepts_structured_json_only() -> None:
    from src.agent.planner import LLMPlanner

    def transport(**kwargs):
        del kwargs
        return (
            '{"action":"finish","hypothesis":"ordinary noise",'
            '"reason":"NO_INVESTIGATION_NEEDED","tool_calls":[],'
            '"final_assessment":"Quiet book.","open_questions":[]}'
        )

    result = run_agent(
        _quiet_case(),
        planner=LLMPlanner(api_key="test", transport=transport),
        registry=_registry({"get_book_state": _ok}),
    )
    assert result.planner_kind == "llm"
    assert result.stop_reason == "NO_INVESTIGATION_NEEDED"
    assert result.observations == ()
