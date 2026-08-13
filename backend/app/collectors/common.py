import re

TARGET_PATTERNS = [
    r"\bsoftware engineer\b",
    r"\bsoftware developer\b",
    r"\bsoftware development engineer\b",
    r"\bsde\b",
    r"\bbackend engineer\b",
    r"\bbackend developer\b",
    r"\bfront[- ]?end engineer\b",
    r"\bfront[- ]?end developer\b",
    r"\bfull[- ]stack engineer\b",
    r"\bfull[- ]stack developer\b",
    r"\bjava developer\b",
    r"\bjava engineer\b",
    r"\breact developer\b",
    r"\breact engineer\b",
    r"\bplatform engineer\b",
    r"\bcloud engineer\b",
    r"\bapi engineer\b",
    r"\bapplication engineer\b",
    r"\bapplication developer\b",
    r"\bweb engineer\b",
    r"\bassociate software engineer\b",
    r"\bjunior software engineer\b",
    r"\bsoftware engineer i\b",
    r"\bsoftware engineer ii\b",
    r"\bnew grad software engineer\b",
    r"\bentry[- ]level software engineer\b",
]

def title_matches(title):
    t = re.sub(r"\s+", " ", (title or "").lower()).strip()
    return any(re.search(p, t) for p in TARGET_PATTERNS)
