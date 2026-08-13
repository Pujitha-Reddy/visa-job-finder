import re

def _find(patterns, text):
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
    return None

def classify_visa(description: str) -> dict:
    t = re.sub(r'\s+', ' ', (description or '').lower())

    hard_no = _find([
        r'will not sponsor',
        r'unable to sponsor',
        r'cannot sponsor',
        r'no (?:visa |employment )?sponsorship',
        r'without sponsorship now or in the future',
        r'do not require sponsorship now or in the future',
    ], t)
    if hard_no:
        return {"status":"NO_SPONSORSHIP","evidence":hard_no,
                "reason":"Explicit no-sponsorship language detected."}

    restricted = _find([
        r'u\.?s\.? citizen(?:ship)? required',
        r'must be (?:a )?u\.?s\.? citizen',
        r'green card holders? only',
        r'permanent residents? only',
        r'active .* security clearance required',
    ], t)
    if restricted:
        return {"status":"RESTRICTED","evidence":restricted,
                "reason":"Citizenship/permanent-resident/clearance restriction detected."}

    positive = _find([
        r'h-?1b sponsorship',
        r'visa sponsorship (?:is )?available',
        r'(?:will|can|may) sponsor',
        r'immigration sponsorship',
        r'h-?1b transfer',
    ], t)
    if positive:
        return {"status":"SPONSORSHIP_AVAILABLE","evidence":positive,
                "reason":"Positive sponsorship language detected."}

    f1 = _find([
        r'\bstem opt\b', r'\boptional practical training\b', r'\bf-?1\b',
        r'\bcpt\b', r'\bopt\b', r'\bemployment authorization document\b', r'\bead\b',
    ], t)
    if f1:
        return {"status":"F1_OPT_COMPATIBLE_SIGNAL","evidence":f1,
                "reason":"F-1/OPT/CPT/EAD-related language detected; review exact eligibility."}

    current_auth = _find([
        r'authorized to work in the (?:u\.?s\.?|united states)',
        r'valid work authorization',
        r'legally authorized to work',
    ], t)
    if current_auth:
        return {"status":"WORK_AUTHORIZATION_MENTIONED","evidence":current_auth,
                "reason":"Current work authorization language detected; sponsorship remains unclear."}

    return {"status":"NOT_MENTIONED","evidence":None,
            "reason":"Visa/sponsorship language not found. Needs review, not rejection."}
