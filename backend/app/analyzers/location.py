from __future__ import annotations

REMOTE = ("remote", "work from home", "work-from-home", "distributed")
HYBRID = ("hybrid", "flexible workplace", "flexible work")
ONSITE = ("onsite", "on-site", "in office", "in-office", "office-based")


def classify_work_arrangement(location: str, description: str) -> dict:
    loc = (location or "").lower()
    desc = (description or "").lower()
    combined = f"{loc} {desc}"

    # Explicit hybrid should win over generic "remote days" wording.
    if any(x in combined for x in HYBRID):
        return {"value": "HYBRID", "reason": "Hybrid/flexible workplace language detected."}

    if any(x in loc for x in REMOTE) or any(x in combined for x in REMOTE):
        return {"value": "REMOTE", "reason": "Remote-work language detected."}

    if any(x in combined for x in ONSITE):
        return {"value": "ONSITE", "reason": "Onsite/in-office language detected."}

    # A physical location alone is not enough to assert onsite.
    return {"value": "UNKNOWN", "reason": "Work arrangement is not explicit."}
