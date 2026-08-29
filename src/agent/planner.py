"""Planners emit validated AgentDecision objects. They never execute tools."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any, Mapping, Protocol

from src.agent.models import AgentDecision, MalformedPlannerOutput, ToolCall
from src.agent.prompts import format_planner_user, planner_system_prompt
from src.agent.state import AgentState
from src.agent_prompts import (
    MECHANISM_QUERIES,
    crowding_signal_present,
    no_meaningful_risk_signal,
    recovery_setup_present,
    want_fundamentals,
)


class Planner(Protocol):
    kind: str

    def decide(self, state: AgentState) -> AgentDecision:
        ...


class ScriptedPlanner:
    """Test double: replay a queue of decisions or raise the queued error."""

    kind = "scripted"

    def __init__(self, decisions: Sequence[AgentDecision | Mapping[str, Any] | BaseException]) -> None:
        self._queue = list(decisions)

    def decide(self, state: AgentState) -> AgentDecision:
        del state
        if not self._queue:
            return AgentDecision(
                action="finish",
                hypothesis="script exhausted",
                reason="UNRESOLVABLE",
                final_assessment="No further scripted decisions.",
            )
        item = self._queue.pop(0)
        if isinstance(item, BaseException):
            raise item
        if isinstance(item, AgentDecision):
            return item
        if isinstance(item, Mapping):
            return dict(item)
        raise MalformedPlannerOutput(f"unsupported scripted decision: {type(item)!r}")


class HeuristicPlanner:
    """Fail-closed planner when no LLM key is available.

    It still returns structured AgentDecision objects. The executor, not this
    class, is responsible for validation, timeouts, and evidence cutoff.
    ``focus`` restricts the planner to one mechanism specialist; ``None``
    keeps the original combined single-loop behavior.
    """

    kind = "heuristic"

    def __init__(self, focus: str | None = None) -> None:
        self.focus = focus
        self.kind = f"heuristic-{focus}" if focus else "heuristic"

    def decide(self, state: AgentState) -> AgentDecision:
        if no_meaningful_risk_signal(state.risk_state) and not state.investigated_hypotheses:
            return AgentDecision(
                action="finish",
                hypothesis="ordinary noise",
                reason="NO_INVESTIGATION_NEEDED",
                final_assessment=(
                    "The deterministic state does not justify additional evidence search."
                ),
            )
        called = {item.name for item in state.observations if item.status in {"ok", "duplicate"}}
        crowding = crowding_signal_present(state.risk_state) and self.focus in {None, "kl_crowding"}
        recovery = recovery_setup_present(state.risk_state) and self.focus in {None, "dm_recovery"}
        if crowding and "get_cluster_exposure" not in called:
            return AgentDecision(
                action="call_tools",
                hypothesis="localized crowded unwind",
                reason="cluster concentration may explain the pressure",
                tool_calls=[
                    ToolCall(id="s1-cluster", name="get_cluster_exposure", args={}),
                    ToolCall(
                        id="s1-pos",
                        name="search_positioning",
                        args={"query": MECHANISM_QUERIES["kl_crowding"]},
                    ),
                    ToolCall(
                        id="s1-news",
                        name="search_news",
                        args={"query": "hedge fund technology exposure reduction optical networking"},
                    ),
                ],
            )
        cluster = [str(item).upper() for item in (state.risk_state.get("theme_cluster") or [])]
        if crowding and "inspect_name" not in called and cluster:
            symbol = "COHR" if "COHR" in cluster else cluster[0]
            return AgentDecision(
                action="call_tools",
                hypothesis="forced deleveraging still unconfirmed",
                reason="drill into the concentrated long before stopping",
                tool_calls=[
                    ToolCall(id="s2-name", name="inspect_name", args={"symbol": symbol}),
                ],
            )
        if recovery and "get_factor_state" not in called:
            return AgentDecision(
                action="call_tools",
                hypothesis="recovery-driven reversal",
                reason="DM recovery flags are present in the deterministic state",
                tool_calls=[
                    ToolCall(id="s1-factor", name="get_factor_state", args={}),
                    ToolCall(
                        id="s1-dm-news",
                        name="search_news",
                        args={"query": MECHANISM_QUERIES["dm_recovery"]},
                    ),
                ],
            )
        if recovery and self.focus == "dm_recovery" and "compare_prior_state" not in called:
            return AgentDecision(
                action="call_tools",
                hypothesis="recovery-driven reversal",
                reason="compare the current recovery snapshot with the loaded prior state",
                tool_calls=[
                    ToolCall(id="s2-prior", name="compare_prior_state", args={}),
                ],
            )
        if self.focus is None and want_fundamentals(state) and "search_filings" not in called:
            return AgentDecision(
                action="call_tools",
                hypothesis="fundamental deterioration",
                reason="check bundled filings/earnings for the book names",
                tool_calls=[
                    ToolCall(
                        id="s-filings",
                        name="search_filings",
                        args={"query": MECHANISM_QUERIES["fundamentals"]},
                    ),
                ],
            )
        crowding = crowding_signal_present(state.risk_state) and self.focus in {None, "kl_crowding"}
        if crowding:
            finish_text = (
                "Localized crowding pressure is supported. Forced deleveraging "
                "and a book-wide unwind remain unconfirmed."
            )
        elif recovery_setup_present(state.risk_state) and self.focus in {None, "dm_recovery"}:
            finish_text = (
                "Recovery conditions were investigated. This remains an "
                "interpretation of the deterministic state, not a crash call."
            )
        else:
            finish_text = (
                "Remaining uncertainty cannot be resolved into a confirmed "
                "unwind or crash from available tools."
            )
        return AgentDecision(
            action="finish",
            hypothesis=state.investigated_hypotheses[-1] if state.investigated_hypotheses else "ordinary noise",
            reason="EVIDENCE_SUFFICIENT" if state.observations else "UNRESOLVABLE",
            open_questions=list(state.open_questions),
            final_assessment=finish_text,
        )


class LLMPlanner:
    """DeepSeek (or compatible) structured-output planner."""

    kind = "llm"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        transport: Any | None = None,
        timeout_seconds: float = 20.0,
        focus: str | None = None,
        allowed_tools: Sequence[str] | None = None,
    ) -> None:
        self.api_key = (api_key or os.environ.get("DEEPSEEK_API_KEY") or "").strip()
        self.model = model or os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat"
        self.base_url = (
            base_url
            or os.environ.get("DEEPSEEK_BASE_URL")
            or "https://api.deepseek.com"
        )
        self.transport = transport
        self.timeout_seconds = timeout_seconds
        self.focus = focus
        self.allowed_tools = tuple(allowed_tools) if allowed_tools is not None else None
        self.kind = f"llm-{focus}" if focus else "llm"

    def decide(self, state: AgentState) -> AgentDecision:
        if not self.api_key and self.transport is None:
            raise MalformedPlannerOutput("DEEPSEEK_API_KEY is not set")
        from src.evidence.deepseek_explainer import (
            _extract_json_object,
            _post_chat_completion,
        )

        timeout = min(self.timeout_seconds, max(0.5, state.remaining_seconds))
        post = self.transport or _post_chat_completion
        try:
            content = post(
                api_key=self.api_key or "test",
                model=self.model,
                messages=[
                    {"role": "system", "content": planner_system_prompt(self.focus)},
                    {
                        "role": "user",
                        "content": format_planner_user(
                            state,
                            allowed_tools=self.allowed_tools,
                            focus=self.focus,
                        ),
                    },
                ],
                base_url=self.base_url,
                temperature=0.1,
                timeout_seconds=timeout,
            )
        except Exception as exc:  # noqa: BLE001
            raise TimeoutError(f"planner transport failed: {exc}") from exc
        try:
            parsed = _extract_json_object(content)
        except Exception as exc:  # noqa: BLE001
            raise MalformedPlannerOutput(f"planner output was not JSON: {exc}") from exc
        return parsed


def resolve_planner(
    *,
    planner: Planner | None,
    use_llm: bool | None,
    focus: str | None = None,
    allowed_tools: Sequence[str] | None = None,
) -> Planner:
    if planner is not None:
        return planner
    if use_llm is False:
        return HeuristicPlanner(focus=focus)
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if use_llm is True or key:
        if not key and use_llm is True:
            return HeuristicPlanner(focus=focus)
        return LLMPlanner(api_key=key, focus=focus, allowed_tools=allowed_tools)
    return HeuristicPlanner(focus=focus)
