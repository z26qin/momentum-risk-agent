"""Investigation agent: orchestrator plus planner/executor specialists.

The original heuristic loop lives in ``src.agent.heuristic`` and remains the
compatibility path for existing tests. ``run_orchestrated_investigation`` is
the product entry point; ``run_agent`` is the single-planner loop each
specialist reuses.
"""

from src.agent.heuristic import (
    FINISH,
    FOLLOWUP_SEARCH,
    SEARCH_DM_RECOVERY,
    SEARCH_FUNDAMENTALS,
    SEARCH_KL_CROWDING,
    AgentAction,
    AgentReport,
    AgentState as HeuristicAgentState,
    build_pm_report,
    classify_evidence,
    decide_next_action,
    default_tool_registry,
    execute_tool,
    observe,
    run_investigation_agent,
    run_investigation_loop,
    update_memory,
)
from src.agent.loop import MAX_STEPS, OVERALL_DEADLINE_SECONDS, AgentRunResult, run_agent
from src.agent.models import AgentDecision, AgentRunTrace, OrchestratorTrace, ToolCall, ToolObservation
from src.agent.orchestrator import (
    OrchestratedRunResult,
    run_orchestrated_investigation,
    select_specialists,
)
from src.agent.state import AgentState

__all__ = [
    "FINISH",
    "FOLLOWUP_SEARCH",
    "MAX_STEPS",
    "OVERALL_DEADLINE_SECONDS",
    "SEARCH_DM_RECOVERY",
    "SEARCH_FUNDAMENTALS",
    "SEARCH_KL_CROWDING",
    "AgentAction",
    "AgentDecision",
    "AgentReport",
    "AgentRunResult",
    "AgentRunTrace",
    "AgentState",
    "HeuristicAgentState",
    "OrchestratedRunResult",
    "OrchestratorTrace",
    "ToolCall",
    "ToolObservation",
    "build_pm_report",
    "classify_evidence",
    "decide_next_action",
    "default_tool_registry",
    "execute_tool",
    "observe",
    "run_agent",
    "run_investigation_agent",
    "run_investigation_loop",
    "run_orchestrated_investigation",
    "select_specialists",
    "update_memory",
]
