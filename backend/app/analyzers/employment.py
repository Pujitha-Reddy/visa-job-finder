from __future__ import annotations
import re


def classify_employment(title: str, description: str, metadata: dict | None = None) -> dict:
    t = f"{title or ''} {description or ''} {metadata or {}}".lower()

    if re.search(r'\bc2c\b|corp[- ]to[- ]corp|corp to corp', t):
        return {"value": "CONTRACT_C2C", "reason": "C2C/corp-to-corp language detected."}

    if re.search(r'\bw-?2\b', t) and re.search(r'\bcontract|contractor|contracting\b', t):
        return {"value": "CONTRACT_W2", "reason": "W2 contract language detected."}

    if re.search(r'\bcontract|contractor|contracting\b', t):
        return {"value": "CONTRACT_UNKNOWN", "reason": "Contract language detected; W2/C2C unclear."}

    if re.search(r'\bintern(ship)?\b', t):
        return {"value": "INTERNSHIP", "reason": "Internship language detected."}

    if re.search(r'\btemporary\b|\btemp\b', t):
        return {"value": "TEMPORARY", "reason": "Temporary employment language detected."}

    if re.search(r'\bfull[- ]time\b|\bregular employee\b', t):
        return {"value": "FULL_TIME", "reason": "Full-time employment language detected."}

    return {"value": "UNKNOWN", "reason": "Employment type is not explicit."}
