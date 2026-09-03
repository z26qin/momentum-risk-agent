"""Deterministic tool executor.

The planner may request tools. This module decides whether they run, how they
run, and what the planner is allowed to see afterwards.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, wait
from concurrent.futures import TimeoutError as FuturesTimeout
from typing import Any, Callable, Mapping

from pydantic import ValidationError

from src.agent.cutoff import published_by_cutoff
from src.agent.models import AgentDecision, ToolCall, ToolObservation
from src.agent.state import AgentState
from src.agent.tracing import (
    context_thread_pool,
    executor_inputs,
    executor_outputs,
    log_tool_observation,
    rename_current,
    tool_span,
    traceable,
)
from src.tools.context import ToolContext
from src.tools.registry import MAX_PARALLEL_TOOLS, TOOL_RETRIES, ToolRegistry, default_registry

Monotonic = Callable[[], float]


class _ToolAttemptsExhausted(Exception):
    def __init__(self, cause: BaseException, attempts: int) -> None:
        super().__init__(str(cause))
        self.cause = cause
        self.attempts = attempts


def canonical_key(name: str, args: Mapping[str, Any]) -> str:
    normalized: dict[str, Any] = {}
    for key, value in dict(args).items():
        if value is None or value == "":
            continue
        if key == "query":
            normalized[key] = " ".join(str(value).lower().split())
        elif key == "symbol":
            normalized[key] = str(value).strip().upper()
        elif key == "prior_date":
            normalized[key] = str(value).strip()[:10]
        else:
            normalized[key] = value
    return json.dumps({"name": name, "args": normalized}, sort_keys=True, default=str)


class Executor:
    def __init__(
        self,
        registry: ToolRegistry | None = None,
        *,
        monotonic: Monotonic = time.monotonic,
    ) -> None:
        self.registry = registry or default_registry()
        self.monotonic = monotonic

    def execute_decision(
        self,
        decision: AgentDecision,
        state: AgentState,
        ctx: ToolContext,
        *,
        remaining_seconds: float,
    ) -> list[ToolObservation]:
        if decision.action != "call_tools":
            return []
        return self._execute_tool_batch(
            decision, state, ctx, remaining_seconds=remaining_seconds
        )

    @traceable(
        name="execute_tool_batch",
        run_type="tool",
        process_inputs=executor_inputs,
        process_outputs=executor_outputs,
    )
    def _execute_tool_batch(
        self,
        decision: AgentDecision,
        state: AgentState,
        ctx: ToolContext,
        *,
        remaining_seconds: float,
    ) -> list[ToolObservation]:
        rename_current(f"execute_tool_batch step={state.step}")
        calls = list(decision.tool_calls)[:MAX_PARALLEL_TOOLS]
        prepared: list[tuple[ToolCall, dict[str, Any], Any, ToolObservation | None]] = []
        batch_keys: set[str] = set()
        for index, call in enumerate(calls):
            call_id = call.id or f"s{state.step}-{index + 1}"
            tagged = call.model_copy(update={"id": call_id})
            observation, parsed, args = self._precheck(
                tagged, state, remaining_seconds, batch_keys
            )
            prepared.append((tagged, args, parsed, observation))

        runnable = [
            (call, args, parsed)
            for call, args, parsed, observation in prepared
            if observation is None and parsed is not None
        ]
        executed = (
            self._run_parallel(runnable, ctx, remaining_seconds) if runnable else []
        )
        executed_by_id = {item.tool_call_id: item for item in executed}
        ordered: list[ToolObservation] = []
        for call, args, _parsed, observation in prepared:
            if observation is not None:
                log_tool_observation(observation)
                ordered.append(observation)
                continue
            result = executed_by_id.get(call.id)
            if result is None:
                missed = _error(
                    call,
                    args,
                    "deadline",
                    "deadline",
                    "overall investigation deadline reached",
                )
                log_tool_observation(missed)
                ordered.append(missed)
            else:
                ordered.append(result)
        for item in ordered:
            if item.status == "ok":
                state.executed_keys.add(canonical_key(item.name, item.args))
        return ordered

    def _precheck(
        self,
        call: ToolCall,
        state: AgentState,
        remaining_seconds: float,
        batch_keys: set[str],
    ) -> tuple[ToolObservation | None, Any, dict[str, Any]]:
        args = dict(call.args or {})
        if remaining_seconds <= 0:
            return _error(call, args, "deadline", "deadline", "overall investigation deadline reached"), None, args
        spec = self.registry.get(call.name)
        if spec is None:
            return _error(call, args, "error", "unknown_tool", f"tool {call.name!r} is not registered"), None, args
        try:
            parsed = self.registry.validate_args(call.name, call.args)
        except (ValidationError, ValueError, KeyError) as exc:
            return _error(call, args, "error", "invalid_args", str(exc)), None, args
        args = parsed.model_dump()
        key = canonical_key(call.name, args)
        if key in state.executed_keys or key in batch_keys:
            return (
                ToolObservation(
                    tool_call_id=call.id,
                    name=call.name,
                    status="duplicate",
                    args=args,
                    error_type="duplicate",
                    error_message="semantically identical read already executed in this investigation",
                    payload={"duplicate": True, "canonical_key": key},
                ),
                None,
                args,
            )
        batch_keys.add(key)
        return None, parsed, args

    def _run_parallel(
        self,
        runnable: list[tuple[ToolCall, dict[str, Any], Any]],
        ctx: ToolContext,
        remaining_seconds: float,
    ) -> list[ToolObservation]:
        if not runnable:
            return []
        workers = min(len(runnable), MAX_PARALLEL_TOOLS)
        observations: list[ToolObservation] = []
        with context_thread_pool(max_workers=workers) as pool:
            futures = {}
            for call, args, parsed in runnable:
                spec = self.registry.get(call.name)
                futures[
                    pool.submit(
                        self._run_with_retry,
                        spec,
                        ctx,
                        parsed,
                        remaining_seconds,
                    )
                ] = (call, args)
            done, not_done = wait(futures, timeout=max(0.01, remaining_seconds))
            for future in done:
                call, args = futures[future]
                try:
                    payload, discarded, elapsed_ms, attempts = future.result(timeout=0)
                    observations.append(
                        ToolObservation(
                            tool_call_id=call.id,
                            name=call.name,
                            status="ok",
                            args=args,
                            payload=payload,
                            elapsed_ms=elapsed_ms,
                            discarded_post_cutoff=discarded,
                            attempts=attempts,
                        )
                    )
                except _ToolAttemptsExhausted as exc:
                    if isinstance(exc.cause, TimeoutError):
                        observations.append(
                            _error(
                                call,
                                args,
                                "timeout",
                                "timeout",
                                str(exc.cause),
                                attempts=exc.attempts,
                            )
                        )
                    else:
                        observations.append(
                            _error(
                                call,
                                args,
                                "error",
                                "tool_exception",
                                str(exc.cause),
                                attempts=exc.attempts,
                            )
                        )
                except FuturesTimeout:
                    observations.append(_error(call, args, "timeout", "timeout", "tool exceeded its timeout"))
                except Exception as exc:  # noqa: BLE001 - isolate tool failure
                    observations.append(_error(call, args, "error", "tool_exception", str(exc)))
            for future in not_done:
                call, args = futures[future]
                observations.append(
                    _error(call, args, "deadline", "deadline", "overall investigation deadline reached")
                )
        return observations

    def _run_with_retry(
        self,
        spec,
        ctx: ToolContext,
        parsed,
        remaining_seconds: float,
    ) -> tuple[Any, int, int, int]:
        started = self.monotonic()
        attempts = 0
        last_error: BaseException | None = None
        args = parsed.model_dump() if hasattr(parsed, "model_dump") else {}
        with tool_span(getattr(spec, "name", "tool"), inputs={"args": args}) as run:
            for attempt in range(1, TOOL_RETRIES + 2):
                leftover = remaining_seconds - (self.monotonic() - started)
                timeout = min(spec.timeout_seconds if spec else 0.0, max(0.0, leftover))
                if timeout <= 0:
                    break
                attempts = attempt
                try:
                    payload, discarded, elapsed_ms = self._run_one(
                        spec, ctx, parsed, timeout
                    )
                    if run is not None:
                        run.end(
                            outputs={
                                "status": "ok",
                                "attempts": attempts,
                                "elapsed_ms": elapsed_ms,
                                "discarded_post_cutoff": discarded,
                            }
                        )
                    return payload, discarded, elapsed_ms, attempts
                except Exception as exc:  # noqa: BLE001 - retry only executed handlers
                    last_error = exc
                    if run is not None:
                        run.add_event(
                            {"name": "retry", "attempt": attempt, "error": str(exc)}
                        )
                    if attempt > TOOL_RETRIES:
                        break
            cause = last_error or TimeoutError("overall investigation deadline reached")
            if run is not None:
                run.set(
                    outputs={
                        "status": "error",
                        "attempts": max(1, attempts),
                        "error": str(cause),
                    }
                )
            raise _ToolAttemptsExhausted(cause, max(1, attempts))

    def _run_one(self, spec, ctx: ToolContext, parsed, timeout: float) -> tuple[Any, int, int]:
        if spec is None:
            raise RuntimeError("missing tool spec")
        started = self.monotonic()
        inner = ThreadPoolExecutor(max_workers=1)
        try:
            future = inner.submit(self._invoke, spec, ctx, parsed)
            payload, discarded = future.result(timeout=max(0.01, timeout))
        except FuturesTimeout as exc:
            raise TimeoutError("tool exceeded its timeout") from exc
        finally:
            inner.shutdown(wait=False, cancel_futures=True)
        elapsed_ms = int((self.monotonic() - started) * 1000)
        return payload, discarded, elapsed_ms

    def _invoke(self, spec, ctx: ToolContext, parsed) -> tuple[Any, int]:
        payload = spec.handler(ctx, parsed)
        discarded = 0
        if spec.returns_evidence:
            payload, discarded = filter_cutoff_payload(
                payload, cutoff=ctx.assessment_cutoff, as_of_date=ctx.as_of_date
            )
        return payload, discarded


def filter_cutoff_payload(payload: Any, *, cutoff: str, as_of_date: str) -> tuple[Any, int]:
    if isinstance(payload, list):
        kept, discarded = _filter_docs(payload, cutoff=cutoff, as_of_date=as_of_date)
        return kept, discarded
    if isinstance(payload, dict) and "documents" in payload:
        kept, discarded = _filter_docs(
            list(payload.get("documents") or []), cutoff=cutoff, as_of_date=as_of_date
        )
        updated = dict(payload)
        updated["documents"] = kept
        updated["discarded_post_cutoff"] = discarded
        return updated, discarded
    return payload, 0


def _filter_docs(
    documents: list[Any], *, cutoff: str, as_of_date: str
) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    discarded = 0
    for item in documents:
        if not isinstance(item, dict):
            discarded += 1
            continue
        published = str(
            item.get("published_at")
            or item.get("publication_timestamp")
            or item.get("timestamp")
            or ""
        )
        if not published or not published_by_cutoff(published, cutoff, as_of_date):
            discarded += 1
            continue
        kept.append(item)
    return kept, discarded


def _error(
    call: ToolCall,
    args: Mapping[str, Any],
    status: str,
    error_type: str,
    message: str,
    *,
    attempts: int = 1,
) -> ToolObservation:
    return ToolObservation(
        tool_call_id=call.id or call.name,
        name=call.name,
        status=status,  # type: ignore[arg-type]
        args=dict(args),
        error_type=error_type,
        error_message=message,
        attempts=attempts,
    )
