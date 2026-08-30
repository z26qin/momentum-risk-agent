from __future__ import annotations

import json

import pytest

from src.agent.planner import LLMPlanner, resolve_planner
from src.agent.transport import extract_json_object, post_chat_completion
from src.risk_state.provider import FrozenCaseProvider


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args) -> None:
        del args

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _completion(*, content: str = '{"action":"finish"}', finish_reason: str = "stop"):
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1,
        "model": "deepseek-v4-flash",
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "reasoning_content": None,
                },
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 10,
        },
    }


def test_chat_transport_requests_bounded_non_thinking_json_output(monkeypatch) -> None:
    captured = {}

    def urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _Response(_completion())

    monkeypatch.setattr("urllib.request.urlopen", urlopen)

    content = post_chat_completion(
        api_key="secret",
        model="deepseek-v4-flash",
        messages=[{"role": "system", "content": "Return JSON."}],
        base_url="https://api.deepseek.com/",
        temperature=0.0,
        timeout_seconds=7.5,
        max_tokens=800,
    )

    body = json.loads(captured["request"].data)
    assert content == '{"action":"finish"}'
    assert captured["request"].full_url == "https://api.deepseek.com/chat/completions"
    assert captured["timeout"] == 7.5
    assert body == {
        "model": "deepseek-v4-flash",
        "messages": [{"role": "system", "content": "Return JSON."}],
        "temperature": 0.0,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "stream": False,
    }


@pytest.mark.parametrize(
    "content",
    [
        'Result: {"action":"finish"}',
        '```json\n{"action":"finish"}\n```',
        '[{"action":"finish"}]',
    ],
)
def test_json_output_parser_rejects_wrappers_and_non_objects(content: str) -> None:
    with pytest.raises(ValueError):
        extract_json_object(content)


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"choices": []}, "choice"),
        (_completion(content=""), "empty"),
        (_completion(finish_reason="length"), "finish_reason"),
    ],
)
def test_chat_transport_rejects_incomplete_responses(monkeypatch, payload, message) -> None:
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: _Response(payload))

    with pytest.raises(ValueError, match=message):
        post_chat_completion(
            api_key="secret",
            model="deepseek-v4-flash",
            messages=[{"role": "system", "content": "Return JSON."}],
            base_url="https://api.deepseek.com",
            temperature=0.0,
            timeout_seconds=5.0,
            max_tokens=800,
        )


def test_llm_planner_uses_current_deepseek_defaults_and_json_budget(monkeypatch) -> None:
    captured = {}
    monkeypatch.setenv("DEEPSEEK_MODEL", "__test_cleanup_sentinel__")
    monkeypatch.delenv("DEEPSEEK_MODEL")

    def transport(**kwargs):
        captured.update(kwargs)
        return (
            '{"action":"finish","hypothesis":"ordinary noise",'
            '"reason":"NO_INVESTIGATION_NEEDED","tool_calls":[],'
            '"final_assessment":"Quiet book.","open_questions":[]}'
        )

    planner = LLMPlanner(api_key="test", transport=transport)
    state_case = FrozenCaseProvider().load("2024-01-05")
    from src.agent.state import AgentState

    state = AgentState(
        case=state_case,
        run_id="test",
        max_steps=6,
        overall_deadline_seconds=10.0,
        remaining_seconds=10.0,
    )
    planner.decide(state)

    assert captured["model"] == "deepseek-v4-flash"
    assert captured["temperature"] == 0.0
    assert captured["max_tokens"] == 800


def test_explicit_llm_selection_does_not_silently_use_heuristics(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "__test_cleanup_sentinel__")
    monkeypatch.delenv("DEEPSEEK_API_KEY")

    planner = resolve_planner(
        planner=None,
        use_llm=True,
        focus="kl_crowding",
        allowed_tools=("search_news",),
    )

    assert isinstance(planner, LLMPlanner)
