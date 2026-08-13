import re

ALIASES = {
    "insight global llc": "insight global",
    "randstad digital": "randstad",
    "randstad usa": "randstad",
    "robert half international": "robert half",
    "tek systems": "teksystems",
    "k force": "kforce",
}

LEGAL_SUFFIXES = {"inc","incorporated","llc","corp","corporation","co","company","ltd","limited","lp","plc"}

def normalize_company_name(name):
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s in ALIASES:
        return ALIASES[s]
    parts = s.split()
    while parts and parts[-1] in LEGAL_SUFFIXES:
        parts.pop()
    s = " ".join(parts)
    return ALIASES.get(s, s)
