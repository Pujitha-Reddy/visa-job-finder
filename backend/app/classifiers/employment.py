import re

def classify_employment(title: str, description: str, raw_type: str | None = None) -> dict:
    t = " ".join(filter(None, [title, description, raw_type])).lower()

    if re.search(r'contract[- ]to[- ]hire|contract to hire|c2h', t):
        return {"value":"CONTRACT_TO_HIRE","reason":"Contract-to-hire language detected."}
    if re.search(r'\bc2c\b|corp[- ]to[- ]corp|corp to corp', t):
        return {"value":"CONTRACT_C2C","reason":"C2C language detected."}
    if re.search(r'\bw-?2\b', t) and re.search(r'\bcontract|contractor|consultant\b', t):
        return {"value":"CONTRACT_W2","reason":"W2 contract language detected."}
    if re.search(r'\bcontract|contractor|consultant\b', t):
        return {"value":"CONTRACT_UNKNOWN","reason":"Contract language detected; W2/C2C unclear."}
    if re.search(r'\bintern(ship)?\b', t):
        return {"value":"INTERNSHIP","reason":"Internship language detected."}
    if re.search(r'\btemporary\b|\btemp\b', t):
        return {"value":"TEMPORARY","reason":"Temporary employment language detected."}
    if re.search(r'\bfull[- ]time\b|\bregular\b', t):
        return {"value":"FULL_TIME","reason":"Full-time language detected."}
    return {"value":"UNKNOWN","reason":"Employment type not explicit."}
