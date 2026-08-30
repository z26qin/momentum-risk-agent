"""Point-in-time evidence cutoff checks."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")


def published_by_cutoff(published_at: str, cutoff: str, as_of_date: str) -> bool:
    try:
        published = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        boundary = datetime.fromisoformat(str(cutoff).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if published.tzinfo is None:
        published = published.replace(tzinfo=NEW_YORK)
    if boundary.tzinfo is None:
        return False
    return published.astimezone(NEW_YORK).date().isoformat() <= as_of_date and published <= boundary
