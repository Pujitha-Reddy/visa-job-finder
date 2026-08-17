from __future__ import annotations
from datetime import datetime, timezone

def parse_iso(value):
    if not value:
        return None
    s = str(value).strip().replace("Z","+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

def freshness_metadata(source_published_at, source_updated_at, first_seen_at):
    published = parse_iso(source_published_at)
    updated = parse_iso(source_updated_at)
    first_seen = parse_iso(first_seen_at)

    if published:
        return {
            "effective_posted_at": published.isoformat(),
            "freshness_confidence": "HIGH",
            "freshness_source": "ATS_PUBLISHED_AT",
        }

    # First seen is discovery time, not posting time. Keep it visible but don't
    # claim strict 24h/72h freshness.
    if first_seen:
        return {
            "effective_posted_at": None,
            "freshness_confidence": "UNKNOWN",
            "freshness_source": "FIRST_SEEN_ONLY",
        }

    return {
        "effective_posted_at": None,
        "freshness_confidence": "UNKNOWN",
        "freshness_source": "UNKNOWN",
    }
