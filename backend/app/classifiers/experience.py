import re

NEW_GRAD = (
    "new grad","new graduate","recent graduate","entry level","entry-level",
    "junior","university graduate","early career"
)

def classify_experience(text: str) -> dict:
    t = (text or "").lower()

    if any(k in t for k in NEW_GRAD):
        return {
            "min_years": 0.0,
            "max_years": 1.0,
            "evidence": "new grad / entry-level language",
            "band": "NEW_GRAD",
            "match": True,
        }

    candidates = []
    patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(?:\+?\s*)?years?',
        r'(?:minimum of|minimum|at least)\s+(\d+(?:\.\d+)?)\s*\+?\s*years?',
        r'(\d+(?:\.\d+)?)\s*\+\s*years?',
        r'(\d+(?:\.\d+)?)\s+years?\s+(?:of\s+)?(?:professional\s+)?experience',
    ]
    for pat in patterns:
        for m in re.finditer(pat, t):
            nums = [float(x) for x in m.groups() if x is not None]
            lo, hi = nums[0], nums[-1]
            window = t[max(0,m.start()-80):m.end()+80]
            preferred = any(x in window for x in ("preferred","ideally","nice to have","bonus"))
            candidates.append((lo, hi, m.group(0), preferred))

    required = [c for c in candidates if not c[3]]
    pool = required or candidates
    if not pool:
        return {
            "min_years": None, "max_years": None, "evidence": None,
            "band": "NOT_SPECIFIED", "match": None,
        }

    lo, hi, evidence, preferred = min(pool, key=lambda x: x[0])

    if lo == 0:
        band = "0-1"
    elif lo < 2:
        band = "1-2"
    elif lo < 3:
        band = "2-3"
    elif lo < 4:
        band = "3-4"
    elif lo < 5:
        band = "4-5"
    elif lo < 6:
        band = "5-6"
    else:
        band = "6+"

    match = None if preferred and lo > 6 else lo <= 6
    return {
        "min_years": lo,
        "max_years": hi,
        "evidence": evidence,
        "band": band,
        "match": match,
    }
