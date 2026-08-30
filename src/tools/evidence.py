"""Read-only search over cutoff-dated frozen case evidence."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.tools.context import ToolContext

MAX_DOCS = 8


def search_news(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    return _search(ctx, str(getattr(args, "query", "")), channel="news")


def search_positioning(ctx: ToolContext, args: BaseModel) -> dict[str, Any]:
    return _search(ctx, str(getattr(args, "query", "")), channel="positioning")


def _search(ctx: ToolContext, query: str, *, channel: str) -> dict[str, Any]:
    documents = []
    for item in ctx.case.evidence:
        if channel not in item.channels:
            continue
        blob = f"{item.headline} {item.snippet} {item.source}"
        if not _matches(query, blob):
            continue
        documents.append(item.model_dump(mode="json"))
    return {
        "documents": documents[:MAX_DOCS],
        "source": "frozen_case",
        "limitation": (
            "Search is limited to cutoff-dated frozen case evidence; "
            "missing evidence remains missing."
        ),
    }


def _matches(query: str, text: str) -> bool:
    tokens = [token for token in query.lower().split() if len(token) > 3]
    haystack = text.lower()
    return any(token in haystack for token in tokens) if tokens else True
