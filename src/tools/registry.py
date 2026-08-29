"""Allowlisted, typed, read-only tool registry.

Unknown names are not imported. Tools are registered in code, not by the model.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.tools.context import ToolContext

TOOL_TIMEOUT_SECONDS = 4.0
MAX_PARALLEL_TOOLS = 4


class EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)


class InspectArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)


class CompareArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prior_date: str | None = None


class FilingArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    symbol: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    handler: Callable[[ToolContext, BaseModel], Any]
    timeout_seconds: float = TOOL_TIMEOUT_SECONDS
    returns_evidence: bool = False
    description: str = ""


CROWDING_TOOL_NAMES = (
    "get_cluster_exposure",
    "search_positioning",
    "search_news",
    "inspect_name",
    "get_book_state",
)
RECOVERY_TOOL_NAMES = (
    "get_factor_state",
    "get_book_state",
    "search_news",
    "compare_prior_state",
)


class ToolRegistry:
    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def names(self) -> tuple[str, ...]:
        return tuple(self._specs)

    def subset(self, names: Sequence[str]) -> ToolRegistry:
        """Allowlisted specialist registry. Unknown names stay unregistered."""

        specs: list[ToolSpec] = []
        for name in names:
            spec = self._specs.get(name)
            if spec is None:
                raise KeyError(f"tool {name!r} is not registered")
            specs.append(spec)
        return ToolRegistry(specs)

    def validate_args(self, name: str, args: dict[str, Any]) -> BaseModel:
        spec = self._specs[name]
        return spec.args_model.model_validate(args)


def default_registry() -> ToolRegistry:
    from src.tools import evidence, market, portfolio

    return ToolRegistry(
        [
            ToolSpec(
                "get_book_state",
                EmptyArgs,
                portfolio.get_book_state,
                timeout_seconds=2.0,
                description="Deterministic current PM-book risk state",
            ),
            ToolSpec(
                "get_factor_state",
                EmptyArgs,
                market.get_factor_state,
                timeout_seconds=2.0,
                description="UMD / regime / recovery state",
            ),
            ToolSpec(
                "get_cluster_exposure",
                EmptyArgs,
                portfolio.get_cluster_exposure,
                timeout_seconds=2.0,
                description="Concentration / theme / long-short pressure",
            ),
            ToolSpec(
                "compare_prior_state",
                CompareArgs,
                market.compare_prior_state,
                timeout_seconds=2.0,
                description="Compare current compact state with a previous date",
            ),
            ToolSpec(
                "search_news",
                SearchArgs,
                evidence.search_news,
                timeout_seconds=TOOL_TIMEOUT_SECONDS,
                returns_evidence=True,
                description="Point-in-time public news evidence",
            ),
            ToolSpec(
                "search_positioning",
                SearchArgs,
                evidence.search_positioning,
                timeout_seconds=TOOL_TIMEOUT_SECONDS,
                returns_evidence=True,
                description="Crowding / positioning evidence from bundled sources",
            ),
            ToolSpec(
                "search_filings",
                FilingArgs,
                evidence.search_filings,
                timeout_seconds=TOOL_TIMEOUT_SECONDS,
                returns_evidence=True,
                description="Local filings / earnings evidence if bundled",
            ),
            ToolSpec(
                "inspect_name",
                InspectArgs,
                portfolio.inspect_name,
                timeout_seconds=3.0,
                description="Drill into one ticker against the book and cluster",
            ),
        ]
    )


def crowding_registry(base: ToolRegistry | None = None) -> ToolRegistry:
    """Khandani–Lo crowding monitor: cluster, positioning, news, name, book."""

    return (base or default_registry()).subset(CROWDING_TOOL_NAMES)


def recovery_registry(base: ToolRegistry | None = None) -> ToolRegistry:
    """Daniel–Moskowitz recovery monitor: factor, book, news, prior comparison."""

    return (base or default_registry()).subset(RECOVERY_TOOL_NAMES)
