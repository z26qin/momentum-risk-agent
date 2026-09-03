"""LangSmith tracing helpers. Spans are no-ops unless tracing is enabled.

LangSmith is used as a standalone SDK. This module does not import LangChain.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any

from langsmith import get_current_run_tree, trace, traceable
from langsmith.utils import ContextThreadPoolExecutor, tracing_is_enabled

from src.agent.config import DEFAULT_LANGSMITH_PROJECT as DEFAULT_PROJECT

__all__ = [
    "DEFAULT_PROJECT",
    "context_thread_pool",
    "executor_inputs",
    "executor_outputs",
    "flush_traces",
    "langsmith_extra_kwargs",
    "llm_planner_inputs",
    "llm_planner_outputs",
    "log_tool_observation",
    "orchestrator_inputs",
    "orchestrator_outputs",
    "parent_run",
    "planner_inputs",
    "planner_outputs",
    "record_event",
    "record_usage",
    "rename_current",
    "specialist_inputs",
    "specialist_outputs",
    "tool_span",
    "traceable",
    "usage_metadata",
]


def tracer_project() -> str:
    return (
        os.environ.get("LANGSMITH_PROJECT")
        or os.environ.get("LANGCHAIN_PROJECT")
        or DEFAULT_PROJECT
    )


def parent_run() -> Any:
    try:
        return get_current_run_tree()
    except Exception:  # noqa: BLE001 - tracing must never break the agent
        return None


def langsmith_extra_kwargs(**fields: Any) -> dict[str, Any]:
    extra = {key: value for key, value in fields.items() if value is not None}
    return {"langsmith_extra": extra} if extra else {}


def rename_current(name: str) -> None:
    run = parent_run()
    if run is not None:
        run.name = name


def record_event(name: str, payload: Mapping[str, Any] | None = None) -> None:
    run = parent_run()
    if run is None:
        return
    event: dict[str, Any] = {"name": name}
    if payload:
        event.update(dict(payload))
    try:
        run.add_event(event)
    except Exception:  # noqa: BLE001
        return


def usage_metadata(usage: Mapping[str, Any] | None) -> dict[str, Any]:
    if not usage:
        return {}
    mapped: dict[str, Any] = {}
    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens"))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens"))
    total_tokens = usage.get("total_tokens")
    if isinstance(input_tokens, int):
        mapped["input_tokens"] = input_tokens
    if isinstance(output_tokens, int):
        mapped["output_tokens"] = output_tokens
    if isinstance(total_tokens, int):
        mapped["total_tokens"] = total_tokens
    cache_read = usage.get("prompt_cache_hit_tokens")
    if isinstance(cache_read, int) and cache_read:
        mapped["input_token_details"] = {"cache_read": cache_read}
    return mapped


def record_usage(usage: Mapping[str, Any] | None) -> None:
    mapped = usage_metadata(usage)
    if not mapped:
        return
    run = parent_run()
    if run is None:
        return
    try:
        run.set(usage_metadata=mapped)
    except Exception:  # noqa: BLE001
        return


def context_thread_pool(*, max_workers: int) -> ThreadPoolExecutor:
    return ContextThreadPoolExecutor(max_workers=max_workers)


@contextmanager
def tool_span(
    name: str,
    inputs: Mapping[str, Any] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> Iterator[Any]:
    if not tracing_is_enabled():
        yield None
        return
    with trace(name, "tool", inputs=dict(inputs or {}), metadata=dict(metadata or {})) as run:
        yield run


def log_tool_observation(observation: Any) -> None:
    if not tracing_is_enabled():
        return
    with tool_span(
        getattr(observation, "name", "tool"),
        inputs={"args": dict(getattr(observation, "args", None) or {})},
        metadata={
            "status": getattr(observation, "status", None),
            "error_type": getattr(observation, "error_type", None),
            "attempts": getattr(observation, "attempts", None),
        },
    ) as run:
        if run is not None:
            run.end(outputs=_observation_summary(observation))


def flush_traces() -> None:
    if not (
        os.environ.get("LANGSMITH_API_KEY", "").strip()
        or os.environ.get("LANGCHAIN_API_KEY", "").strip()
    ):
        return
    try:
        from langsmith.client import Client

        Client().flush()
    except Exception:  # noqa: BLE001
        return


def orchestrator_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of_date": _as_of_date(inputs.get("case")),
        "max_steps": inputs.get("max_steps"),
        "overall_deadline_seconds": inputs.get("overall_deadline_seconds"),
        "use_llm": inputs.get("use_llm"),
    }


def orchestrator_outputs(result: Any) -> dict[str, Any]:
    return {
        "run_id": getattr(result, "run_id", None),
        "as_of_date": getattr(result, "as_of_date", None),
        "stop_reason": getattr(result, "stop_reason", None),
        "spawned": list(getattr(result, "spawned", ()) or ()),
        "report": getattr(result, "report", None),
    }


def specialist_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "as_of_date": _as_of_date(inputs.get("case")),
        "focus": inputs.get("focus"),
        "max_steps": inputs.get("max_steps"),
        "run_id": inputs.get("run_id"),
        "use_llm": inputs.get("use_llm"),
    }


def specialist_outputs(result: Any) -> dict[str, Any]:
    state = getattr(result, "state", None)
    observations = getattr(result, "observations", ()) or ()
    return {
        "run_id": getattr(result, "run_id", None),
        "stop_reason": getattr(result, "stop_reason", None),
        "planner_kind": getattr(result, "planner_kind", None),
        "steps": getattr(state, "step", None),
        "tools": [getattr(item, "name", None) for item in observations],
        "errors": list(getattr(state, "errors", []) or []),
    }


def planner_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    state = inputs.get("state")
    planner = inputs.get("self")
    return {
        "focus": getattr(planner, "focus", None),
        "kind": getattr(planner, "kind", None),
        "as_of_date": getattr(state, "as_of_date", None),
        "step": getattr(state, "step", None),
        "remaining_seconds": getattr(state, "remaining_seconds", None),
        "open_questions": list(getattr(state, "open_questions", []) or []),
        "investigated_hypotheses": list(
            getattr(state, "investigated_hypotheses", []) or []
        ),
        "observation_names": [
            getattr(item, "name", None)
            for item in getattr(state, "observations", []) or []
        ],
    }


def planner_outputs(decision: Any) -> dict[str, Any]:
    dumped = _model_dump(decision)
    if dumped is None and isinstance(decision, Mapping):
        dumped = dict(decision)
    if dumped is None:
        return {"output": str(decision)[:500]}
    return {
        "action": dumped.get("action"),
        "hypothesis": dumped.get("hypothesis"),
        "reason": dumped.get("reason"),
        "tool_calls": [
            {"name": call.get("name"), "args": call.get("args")}
            for call in dumped.get("tool_calls") or []
        ],
        "final_assessment": dumped.get("final_assessment"),
    }


def llm_planner_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    filtered = planner_inputs(inputs)
    filtered.pop("kind", None)
    return filtered


def llm_planner_outputs(decision: Any) -> dict[str, Any]:
    return planner_outputs(decision)


def executor_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    decision = inputs.get("decision")
    state = inputs.get("state")
    calls = getattr(decision, "tool_calls", None) or []
    return {
        "action": getattr(decision, "action", None),
        "step": getattr(state, "step", None),
        "focus": getattr(state, "focus", None),
        "remaining_seconds": inputs.get("remaining_seconds"),
        "tools": [getattr(call, "name", None) for call in calls],
    }


def executor_outputs(observations: Any) -> dict[str, Any]:
    return {"observations": [_observation_summary(item) for item in observations or []]}


def _observation_summary(observation: Any) -> dict[str, Any]:
    status = getattr(observation, "status", None)
    return {
        "name": getattr(observation, "name", None),
        "status": status,
        "attempts": getattr(observation, "attempts", None),
        "elapsed_ms": getattr(observation, "elapsed_ms", None),
        "error_type": getattr(observation, "error_type", None),
        "error_message": getattr(observation, "error_message", None),
        "duplicate": status == "duplicate",
    }


def _as_of_date(case: Any) -> str | None:
    try:
        return case.risk_state.as_of_date.isoformat()
    except Exception:  # noqa: BLE001
        return None


def _model_dump(value: Any) -> dict[str, Any] | None:
    dump = getattr(value, "model_dump", None)
    if not callable(dump):
        return None
    try:
        dumped = dump()
    except Exception:  # noqa: BLE001
        return None
    return dumped if isinstance(dumped, dict) else None
