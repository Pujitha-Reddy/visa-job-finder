from __future__ import annotations
import re

LEGAL_SUFFIXES = (
    "inc", "incorporated", "llc", "l l c", "corp", "corporation",
    "co", "company", "ltd", "limited", "lp", "llp", "plc"
)

COMMON_ALIASES = {
    "amazon web services": "amazon",
    "amazon com services": "amazon",
    "amazon development center": "amazon",
    "google llc": "google",
    "microsoft corporation": "microsoft",
    "jpmorgan chase": "jpmorgan chase",
    "jp morgan chase": "jpmorgan chase",
}


def normalize_company_name(name: str | None) -> str:
    if not name:
        return ""

    s = name.lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    words = s.split()
    while words and words[-1] in LEGAL_SUFFIXES:
        words.pop()
    s = " ".join(words).strip()

    return COMMON_ALIASES.get(s, s)


def company_match_key(name: str | None) -> str:
    return normalize_company_name(name)
