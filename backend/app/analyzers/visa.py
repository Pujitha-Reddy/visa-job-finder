from __future__ import annotations
import re

NO_SPONSORSHIP = (
    r"no (?:visa |employment )?sponsorship",
    r"will not sponsor",
    r"unable to sponsor",
    r"cannot sponsor",
    r"not (?:eligible|available) for (?:visa )?sponsorship",
    r"without (?:current or future |now or future )?sponsorship",
    r"without sponsorship now or in the future",
    r"do not require sponsorship now or in the future",
)

POSITIVE_SPONSORSHIP = (
    r"visa sponsorship (?:is )?available",
    r"(?:will|can|may) sponsor",
    r"h-?1b sponsorship",
    r"immigration sponsorship",
    r"employment sponsorship (?:is )?available",
)

F1_OPT = (
    r"\bf-?1\b", r"\bstem opt\b", r"\bopt\b",
    r"optional practical training", r"\bcpt\b"
)

RESTRICTED = (
    r"u\.?s\.? citizen(?:ship)? required",
    r"must be (?:a )?u\.?s\.? citizen",
    r"security clearance required",
    r"active .* clearance required",
)


def analyze_visa_language(description: str) -> dict:
    text = re.sub(r"\s+", " ", (description or "").lower())

    for pattern in NO_SPONSORSHIP:
        m = re.search(pattern, text)
        if m:
            return {
                "status": "NO_SPONSORSHIP",
                "evidence": m.group(0),
                "reason": "Explicit no-sponsorship language detected."
            }

    for pattern in RESTRICTED:
        m = re.search(pattern, text)
        if m:
            return {
                "status": "RESTRICTED",
                "evidence": m.group(0),
                "reason": "Citizenship/security-clearance restriction detected."
            }

    for pattern in POSITIVE_SPONSORSHIP:
        m = re.search(pattern, text)
        if m:
            return {
                "status": "SPONSORSHIP_AVAILABLE",
                "evidence": m.group(0),
                "reason": "Positive sponsorship language detected."
            }

    for pattern in F1_OPT:
        m = re.search(pattern, text)
        if m:
            return {
                "status": "OPT_F1_MENTIONED",
                "evidence": m.group(0),
                "reason": "F-1/OPT/CPT-related language detected."
            }

    return {
        "status": "NOT_MENTIONED",
        "evidence": None,
        "reason": "No visa or sponsorship language was found; manual review required."
    }
