from __future__ import annotations
import re

NEW_GRAD_TERMS = (
    "new grad", "new graduate", "recent graduate", "entry level",
    "entry-level", "junior", "university graduate"
)

REQUIRED_HINTS = ("required", "minimum", "must have", "at least", "qualification")
PREFERRED_HINTS = ("preferred", "nice to have", "ideally", "bonus")


def parse_experience(text: str, max_allowed: float = 6) -> dict:
    t = (text or "").lower()
    candidates = []

    if any(term in t for term in NEW_GRAD_TERMS):
        candidates.append((0.0, 0.0, "new grad / entry level", "required"))

    patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(?:\+?\s*)?years?',
        r'(\d+(?:\.\d+)?)\s*\+\s*years?',
        r'(?:at least|minimum of|minimum)\s+(\d+(?:\.\d+)?)\s+years?',
        r'(\d+(?:\.\d+)?)\s+years?\s+(?:of\s+)?(?:professional\s+)?experience',
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, t):
            window = t[max(0, m.start()-80): min(len(t), m.end()+80)]
            nums = [float(x) for x in m.groups() if x is not None]
            lo, hi = (nums[0], nums[-1])
            kind = "preferred" if any(h in window for h in PREFERRED_HINTS) else "required"
            candidates.append((lo, hi, m.group(0), kind))

    required = [c for c in candidates if c[3] == "required"]
    preferred = [c for c in candidates if c[3] == "preferred"]
    pool = required or preferred

    if not pool:
        return {
            "min_years": None, "max_years": None, "text": None,
            "match": None, "reason": "Experience requirement not confidently detected."
        }

    # Prefer the lowest required threshold because descriptions often mention
    # multiple equivalent qualification paths.
    chosen = min(pool, key=lambda c: c[0])
    lo, hi, evidence, kind = chosen

    # A preferred threshold above 6 does not automatically reject the role.
    if kind == "preferred":
        match = None if lo > max_allowed else True
    else:
        match = lo <= max_allowed

    return {
        "min_years": lo,
        "max_years": hi,
        "text": evidence,
        "match": match,
        "reason": f"Detected {kind} experience evidence: {evidence}"
    }
