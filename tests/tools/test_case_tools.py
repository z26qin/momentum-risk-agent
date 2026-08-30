from __future__ import annotations

from src.risk_state.provider import FrozenCaseProvider
from src.tools.context import ToolContext
from src.tools.evidence import search_news, search_positioning
from src.tools.registry import CompareArgs, EmptyArgs, InspectArgs, SearchArgs, case_registry
from src.tools.state import (
    compare_prior_state,
    get_book_state,
    get_cluster_exposure,
    get_factor_state,
    inspect_name,
)


def _context(as_of_date: str) -> ToolContext:
    return ToolContext.from_case(FrozenCaseProvider().load(as_of_date))


def test_state_tools_project_only_validated_case_facts() -> None:
    ctx = _context("2026-05-29")

    book = get_book_state(ctx, EmptyArgs())
    factor = get_factor_state(ctx, EmptyArgs())
    cluster = get_cluster_exposure(ctx, EmptyArgs())

    assert book["monitoring_trigger_count"] == 0
    assert book["book"]["portfolio_drawdown"] == -0.07522682931760427
    assert factor["market_regime"] == "normal"
    assert factor["triggered_mechanisms"] == ["crowded_theme_unwind"]
    assert factor["score_is_probability"] is False
    assert cluster["cluster_symbols"] == ["CIEN", "COHR", "LITE"]
    assert cluster["cluster_size"] == 3


def test_case_evidence_search_uses_query_and_channel() -> None:
    ctx = _context("2026-05-29")

    news = search_news(ctx, SearchArgs(query="hedge fund technology"))
    positioning = search_positioning(ctx, SearchArgs(query="hedge fund technology"))

    news_ids = {item["evidence_id"] for item in news["documents"]}
    positioning_ids = {item["evidence_id"] for item in positioning["documents"]}
    assert {"CSU-2026-013", "CSU-2026-014"} <= news_ids
    assert positioning_ids == {"CSU-2026-013", "CSU-2026-014"}
    assert news["source"] == "frozen_case"
    assert positioning["source"] == "frozen_case"


def test_missing_evidence_remains_empty() -> None:
    result = search_news(_context("2024-01-05"), SearchArgs(query="crowding"))

    assert result["documents"] == []
    assert "missing" in result["limitation"].lower()


def test_name_inspection_reads_case_holding_and_local_evidence() -> None:
    ctx = _context("2026-05-29")

    result = inspect_name(ctx, InspectArgs(symbol="cohr"))

    assert result["symbol"] == "COHR"
    assert result["in_theme_cluster"] is True
    assert result["in_book"] is True
    assert result["holding"]["leg"] == "long"
    assert result["holding"]["weight"] == 0.1
    assert [item["evidence_id"] for item in result["local_evidence"]] == ["CSU-2026-008"]


def test_prior_comparison_reports_only_discrete_contract_changes() -> None:
    result = compare_prior_state(_context("2026-05-29"), CompareArgs())

    assert result["status"] == "available"
    assert result["prior_as_of_date"] == "2026-04-30"
    assert "crowded_theme_unwind: watch → triggered" in result["changes"]
    assert not any("severity score" in change.lower() for change in result["changes"])


def test_prior_comparison_is_explicitly_unavailable_when_missing() -> None:
    result = compare_prior_state(_context("2024-01-05"), CompareArgs())

    assert result["status"] == "unavailable"
    assert result["changes"] == []


def test_case_registry_contains_only_specialist_union() -> None:
    registry = case_registry()

    assert set(registry.names()) == {
        "get_book_state",
        "get_factor_state",
        "get_cluster_exposure",
        "compare_prior_state",
        "search_news",
        "search_positioning",
        "inspect_name",
    }
    assert registry.get("search_filings") is None
