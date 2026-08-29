"""Structured contracts for the planner/executor investigation loop.

Executable actions come only from a validated ``AgentDecision``. Free-form
model text is never parsed to decide what to run.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TOOL_NAMES = (
    "get_book_state",
    "get_factor_state",
    "get_cluster_exposure",
    "compare_prior_state",
    "search_news",
    "search_positioning",
    "search_filings",
    "inspect_name",
)

StopReason = Literal[
    "EVIDENCE_SUFFICIENT",
    "EVIDENCE_CONTRADICTED",
    "NO_INVESTIGATION_NEEDED",
    "UNRESOLVABLE",
    "MAX_STEPS",
    "DEADLINE_EXCEEDED",
    "ESCALATED",
    "MALFORMED_PLANNER_OUTPUT",
    "PLANNER_TIMEOUT",
]

ObservationStatus = Literal["ok", "error", "duplicate", "timeout", "deadline"]


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    name: str
    args: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _name_must_be_nonempty(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("tool name is required")
        return text

    @field_validator("args", mode="before")
    @classmethod
    def _args_must_be_mapping(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ValueError("tool args must be an object")
        return value


class AgentDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: Literal["call_tools", "finish", "escalate"]
    hypothesis: str
    reason: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    final_assessment: str | None = None
    open_questions: list[str] = Field(default_factory=list)

    @field_validator("hypothesis", "reason")
    @classmethod
    def _required_text(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("hypothesis and reason must be non-empty")
        return text

    @field_validator("tool_calls", mode="before")
    @classmethod
    def _tool_calls_list(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("tool_calls must be a list")
        return value

    @field_validator("open_questions", mode="before")
    @classmethod
    def _questions_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if not isinstance(value, list):
            raise ValueError("open_questions must be a list")
        return [str(item) for item in value if str(item).strip()]


class ToolObservation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tool_call_id: str
    name: str
    status: ObservationStatus
    args: dict[str, Any] = Field(default_factory=dict)
    payload: Any = None
    error_type: str | None = None
    error_message: str | None = None
    elapsed_ms: int = 0
    discarded_post_cutoff: int = 0


class AgentRunTrace(BaseModel):
    """Audit trail for one investigation. Does not store chain-of-thought."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    as_of_date: str
    assessment_cutoff: str
    planner_kind: str
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    stop_reason: str
    final_assessment: str | None = None
    calibrated: dict[str, Any] = Field(default_factory=dict)


class MalformedPlannerOutput(ValueError):
    """Planner returned text or JSON that is not a valid AgentDecision."""
