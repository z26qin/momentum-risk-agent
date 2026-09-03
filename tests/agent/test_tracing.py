from __future__ import annotations

from unittest.mock import MagicMock

from langsmith import tracing_context
from langsmith.client import Client

from src.agent.loop import run_agent
from src.agent.models import AgentDecision, ToolCall
from src.agent.orchestrator import run_orchestrated_investigation
from src.agent.planner import LLMPlanner, ScriptedPlanner
from src.agent.state import AgentState
from src.agent.tracing import (
    orchestrator_inputs,
    specialist_inputs,
    usage_metadata,
)
from src.risk_state.models import InvestigationCase
from src.risk_state.provider import FrozenCaseProvider
from src.tools.registry import EmptyArgs, SearchArgs, ToolRegistry, ToolSpec


def _client() -> MagicMock:
    return MagicMock(spec=Client)


def _collect(client: MagicMock):
    return tracing_context(
        enabled=True, client=client, project_name="momentum-risk-agent-test"
    )


def _names(run) -> list[str]:
    return [item.name for item in _walk(run)]


def _walk(run):
    yield run
    for child in run.child_runs or []:
        yield from _walk(child)


def _by_name(run, name: str):
    for item in _walk(run):
        if item.name == name:
            return item
    return None


def _dual_case() -> InvestigationCase:
    raw = FrozenCaseProvider().load("2026-05-29").model_dump(mode="json")
    raw["risk_state"]["mechanisms"]["bear_market_recovery_crash"] = "triggered"
    raw["risk_state"]["triggered_signals"] = ["high_volatility_recovery"]
    return InvestigationCase.model_validate(raw)


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
    )


def _finish() -> AgentDecision:
    return AgentDecision(
        action="finish",
        hypothesis="localized crowded unwind",
        reason="EVIDENCE_SUFFICIENT",
        final_assessment="Localized pressure only.",
    )


def _registry(handlers: dict) -> ToolRegistry:
    specs = []
    for name, handler in handlers.items():
        args_model = SearchArgs if name.startswith("search_") else EmptyArgs
        specs.append(
            ToolSpec(name=name, args_model=args_model, handler=handler, timeout_seconds=2.0)
        )
    return ToolRegistry(specs)


def test_process_inputs_drop_case_blobs() -> None:
    case = FrozenCaseProvider().load("2026-05-29")
    orchestrator = orchestrator_inputs(
        {
            "case": case,
            "max_steps": 6,
            "overall_deadline_seconds": 10.0,
            "use_llm": False,
            "planners": {"crowding": object()},
            "registries": {"crowding": object()},
            "monotonic": object(),
        }
    )
    specialist = specialist_inputs(
        {"case": case, "focus": "kl_crowding", "max_steps": 6, "run_id": "abc", "use_llm": False}
    )

    assert orchestrator == {
        "as_of_date": "2026-05-29",
        "max_steps": 6,
        "overall_deadline_seconds": 10.0,
        "use_llm": False,
    }
    assert specialist["as_of_date"] == "2026-05-29"
    assert specialist["focus"] == "kl_crowding"
    assert "case" not in orchestrator
    assert "risk_state" not in orchestrator
    assert "planners" not in orchestrator


def test_usage_metadata_maps_deepseek_fields() -> None:
    assert usage_metadata(
        {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "prompt_cache_hit_tokens": 3,
        }
    ) == {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "input_token_details": {"cache_read": 3},
    }


def test_orchestrator_trace_nests_threaded_specialists() -> None:
    client = _client()
    collected = []
    with _collect(client):
        result = run_orchestrated_investigation(
            _dual_case(),
            use_llm=False,
            langsmith_extra={"on_end": collected.append},
        )

    assert set(result.spawned) == {"crowding", "recovery"}
    assert collected
    root = collected[0]
    names = _names(root)
    assert root.name == "orchestrated_investigation"
    assert "specialist_loop [kl_crowding]" in names
    assert "specialist_loop [dm_recovery]" in names
    crowding = _by_name(root, "specialist_loop [kl_crowding]")
    recovery = _by_name(root, "specialist_loop [dm_recovery]")
    assert crowding is not None and crowding.parent_run_id == root.id
    assert recovery is not None and recovery.parent_run_id == root.id
    assert "case" not in (root.inputs or {})
    assert "risk_state" not in (root.inputs or {})
    assert root.inputs.get("as_of_date") == "2026-05-29"


def test_tool_batch_records_duplicates_and_retries() -> None:
    client = _client()
    collected = []
    calls = {"n": 0}

    def flaky(_ctx, _args):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        return {"ok": True}

    query = {"search_news": {"query": "crowded unwind"}}
    with _collect(client):
        result = run_agent(
            FrozenCaseProvider().load("2026-05-29"),
            planner=ScriptedPlanner(
                [
                    _decision("get_book_state"),
                    _decision("search_news", args=query),
                    _decision("search_news", args=query),
                    _finish(),
                ]
            ),
            registry=_registry({"get_book_state": flaky, "search_news": lambda _c, _a: {"documents": []}}),
            langsmith_extra={"on_end": collected.append},
        )

    assert result.observations[0].attempts == 2
    assert "duplicate" in {item.status for item in result.observations}
    root = collected[0]
    names = _names(root)
    assert any(name.startswith("execute_tool_batch") for name in names)
    assert "get_book_state" in names
    assert "search_news" in names
    book = _by_name(root, "get_book_state")
    assert book is not None
    events = [item.get("name") for item in (book.events or []) if isinstance(item, dict)]
    assert "retry" in events
    news_spans = [item for item in _walk(root) if item.name == "search_news"]
    assert any(
        (span.metadata or {}).get("status") == "duplicate"
        or (span.outputs or {}).get("duplicate")
        for span in news_spans
    )


def test_llm_planner_trace_records_messages_without_api_key(monkeypatch) -> None:
    from tests.agent.test_deepseek_transport import _Response, _completion

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *args, **kwargs: _Response(
            _completion(
                content=(
                    '{"action":"finish","hypothesis":"ordinary noise",'
                    '"reason":"NO_INVESTIGATION_NEEDED","tool_calls":[],'
                    '"final_assessment":"Quiet book.","open_questions":[]}'
                )
            )
        ),
    )
    client = _client()
    collected = []
    case = FrozenCaseProvider().load("2024-01-05")
    state = AgentState(
        case=case,
        run_id="test",
        max_steps=6,
        overall_deadline_seconds=10.0,
        remaining_seconds=10.0,
    )
    planner = LLMPlanner(api_key="secret-key", focus="kl_crowding")
    with _collect(client):
        planner.decide(state, langsmith_extra={"on_end": collected.append})

    run = collected[0]
    assert run.name == "llm_planner_decide"
    assert run.run_type == "llm"
    dumped = str(run.inputs)
    assert "secret-key" not in dumped
    assert "messages" in (run.inputs or {})
    usage = (run.metadata or {}).get("usage_metadata") or {}
    assert usage.get("input_tokens") == 10
    assert usage.get("output_tokens") == 5
    assert (run.metadata or {}).get("ls_provider") == "deepseek"
    assert (run.metadata or {}).get("ls_model_name") == "deepseek-v4-flash"


def test_llm_fallback_is_recorded_on_the_planner_span() -> None:
    client = _client()
    collected = []

    def transport(**kwargs):
        del kwargs
        raise TimeoutError("provider unavailable")

    with _collect(client):
        result = run_agent(
            FrozenCaseProvider().load("2026-05-29"),
            planner=LLMPlanner(
                api_key="test",
                transport=transport,
                focus="kl_crowding",
            ),
            focus="kl_crowding",
            langsmith_extra={"on_end": collected.append},
        )

    assert "heuristic" in result.planner_kind
    root = collected[0]
    llm = _by_name(root, "llm_planner_decide")
    assert llm is not None
    assert llm.error
    events = [item.get("name") for item in (root.events or []) if isinstance(item, dict)]
    assert "planner_fallback" in events
