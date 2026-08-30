"""Point-in-time evidence adapters over bundled local packs and GDELT.

Live EDGAR / broker / social feeds are not available. Empty results stay empty.
Cutoff filtering is enforced by the executor, not by inventing substitutes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.agent_prompts import (
    _hits,
    as_document,
    retrieve_local_evidence,
    search_news as gdelt_search_news,
    search_positioning_evidence,
)
from src.tools.context import ToolContext
from src.utils.io import REPO_ROOT, read_json

EVIDENCE_PACKS: dict[str, Path] = {
    "2026-05-29": REPO_ROOT / "data/evaluation/current_semi_unwind/candidate_evidence.json",
    "2020-03-24": REPO_ROOT / "data/evaluation/march_2020_reference/candidate_evidence.json",
}

_FILING_HINTS = (
    "10-k",
    "10-q",
    "8-k",
    "earnings",
    "investor relations",
    "sec",
    "filing",
    "quarterly",
    "revenue",
    "capex",
    "guidance",
)

_MAX_DOCS = 8


def search_news(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    query = str(getattr(args, "query", "")).strip()
    if ctx.case is not None:
        return _search_case(ctx, query, channel="news")
    local = _filter_pack(ctx.as_of_date, query)
    remote = _safe_list(
        gdelt_search_news, query, ctx.assessment_cutoff, as_of_date=ctx.as_of_date
    )
    merged = _merge_docs(local + remote)
    return {
        "documents": merged[:_MAX_DOCS],
        "source": "bundled_pack+gdelt",
        "limitation": (
            "News search uses the dated GDELT panel and frozen case packs. "
            "It is not a live web crawl."
        ),
    }


def search_positioning(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    query = str(getattr(args, "query", "")).strip()
    if ctx.case is not None:
        return _search_case(ctx, query, channel="positioning")
    local = [
        item
        for item in _filter_pack(ctx.as_of_date, query)
        if _looks_like_positioning(item)
    ]
    remote = _safe_list(
        search_positioning_evidence,
        query,
        ctx.assessment_cutoff,
        as_of_date=ctx.as_of_date,
    )
    fallback = _safe_list(
        retrieve_local_evidence, query, ctx.assessment_cutoff, as_of_date=ctx.as_of_date
    )
    merged = _merge_docs(local + remote + fallback)
    return {
        "documents": merged[:_MAX_DOCS],
        "source": "bundled_pack+local+gdelt",
        "limitation": (
            "Positioning evidence is a public-text / bundled-note proxy. "
            "It does not observe prime-brokerage leverage or fund-level holdings."
        ),
    }


def search_filings(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    query = str(getattr(args, "query", "")).strip()
    symbol = getattr(args, "symbol", None)
    symbol_text = str(symbol).strip().upper() if symbol else ""
    found: list[dict[str, Any]] = []
    for item in _filter_pack(ctx.as_of_date, query):
        haystack = f"{item.get('headline', '')} {item.get('snippet', '')} {item.get('source', '')}".lower()
        if not any(hint in haystack for hint in _FILING_HINTS):
            continue
        if symbol_text and symbol_text.lower() not in haystack and symbol_text not in str(item):
            continue
        found.append(item)
    return {
        "documents": found[:_MAX_DOCS],
        "source": "bundled_case_pack",
        "limitation": (
            "Filings search reads bundled earnings / IR notes for frozen cases. "
            "It is not a live EDGAR pull. Missing filings remain missing."
        ),
    }


def local_mentions(as_of_date: str, symbol: str) -> list[dict[str, Any]]:
    needle = symbol.strip().upper()
    found: list[dict[str, Any]] = []
    for item in _load_pack(as_of_date):
        haystack = f"{item.get('headline', '')} {item.get('snippet', '')}".upper()
        if needle in haystack:
            found.append(item)
    return found


def _load_pack(as_of_date: str) -> list[dict[str, Any]]:
    path = EVIDENCE_PACKS.get(as_of_date)
    if path is None or not path.is_file():
        return []
    try:
        payload = read_json(path)
    except (OSError, ValueError):
        return []
    items = payload.get("items") if isinstance(payload, dict) else payload
    documents: list[dict[str, Any]] = []
    for raw in items or []:
        if not isinstance(raw, dict):
            continue
        documents.append(as_document(raw, query="", channel="local_pack"))
    return documents


def _filter_pack(as_of_date: str, query: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for item in _load_pack(as_of_date):
        haystack = f"{item.get('headline', '')} {item.get('snippet', '')}"
        if _hits(query, haystack):
            tagged = dict(item)
            tagged["query"] = query
            found.append(tagged)
    return found


def _looks_like_positioning(item: MappingLike) -> bool:
    blob = f"{item.get('headline', '')} {item.get('snippet', '')}".lower()
    return any(token in blob for token in ("hedge fund", "prime", "position", "delever", "exposure"))


def _merge_docs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in items:
        key = str(item.get("evidence_id") or item.get("headline") or len(merged))
        if key not in merged:
            merged[key] = item
    return list(merged.values())


def _safe_list(func, query: str, cutoff: str, *, as_of_date: str) -> list[dict[str, Any]]:
    try:
        raw = func(query, cutoff, as_of_date=as_of_date)
    except Exception:  # noqa: BLE001 - tool failure is isolated by the executor
        return []
    return [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []


MappingLike = dict[str, Any]


def _search_case(ctx: ToolContext, query: str, *, channel: str) -> dict[str, Any]:
    documents = []
    for item in ctx.case.evidence if ctx.case is not None else ():
        if channel not in item.channels:
            continue
        blob = f"{item.headline} {item.snippet} {item.source}"
        if not _hits(query, blob):
            continue
        documents.append(item.model_dump(mode="json"))
    return {
        "documents": documents[:_MAX_DOCS],
        "source": "frozen_case",
        "limitation": (
            "Search is limited to cutoff-dated frozen case evidence; "
            "missing evidence remains missing."
        ),
    }
