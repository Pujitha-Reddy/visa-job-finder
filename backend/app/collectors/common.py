from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import re
from bs4 import BeautifulSoup


TARGET_TITLE_TERMS = (
    "software engineer",
    "software developer",
    "full stack engineer",
    "full-stack engineer",
    "full stack developer",
    "backend engineer",
    "back-end engineer",
    "backend developer",
    "frontend engineer",
    "front-end engineer",
    "frontend developer",
    "java developer",
    "java software engineer",
)


def clean_html(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def title_matches(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", title.lower()).strip()
    return any(term in normalized for term in TARGET_TITLE_TERMS)


def iso_from_millis(value) -> str | None:
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc).isoformat()
    except Exception:
        return None


def iso_from_string(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    # Preserve valid ISO timestamps when possible.
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(timezone.utc).isoformat()
    except Exception:
        return value
