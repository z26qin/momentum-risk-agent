"""Investigation agent: code orchestrator plus planner/executor specialists.

``run_orchestrated_investigation`` is the product entry point. ``run_agent``
is the single-planner loop each specialist reuses.
"""

from src.agent.loop import MAX_STEPS, OVERALL_DEADLINE_SECONDS, AgentRunResult, run_agent
from src.agent.models import AgentDecision, AgentRunTrace, OrchestratorTrace, ToolCall, ToolObservation
from src.agent.orchestrator import (
    OrchestratedRunResult,
    run_orchestrated_investigation,
    select_specialists,
)
from src.agent.state import AgentState

__all__ = [
    "MAX_STEPS",
    "OVERALL_DEADLINE_SECONDS",
    "AgentDecision",
    "AgentRunResult",
    "AgentRunTrace",
    "AgentState",
    "OrchestratedRunResult",
    "OrchestratorTrace",
    "ToolCall",
    "ToolObservation",
    "run_agent",
    "run_orchestrated_investigation",
    "select_specialists",
]
