from __future__ import annotations

import re
from difflib import SequenceMatcher

from .normalization import normalize_company_name

STOPWORDS = {
    "inc","incorporated","llc","corp","corporation","company","co","ltd","limited",
    "technologies","technology","systems","services","solutions","group","holdings",
    "international","usa","us","america","americas"
}

MANUAL_ALIASES = {
    "elastic": ["elastic n v", "elastic nv", "elasticsearch"],
    "grafana labs": ["grafana labs", "raintank"],
    "gitlab": ["gitlab"],
    "harvey": ["harvey ai", "counsel ai"],
    "insight global": ["insight global"],
    "robert half": ["robert half international", "robert half"],
    "randstad": ["randstad digital", "randstad north america", "randstad"],
    "teksystems": ["teksystems"],
    "kforce": ["kforce"],

    "amazon": [
        "amazon com services",
        "amazon com services llc",
        "amazon development center us",
        "amazon development center us inc",
        "amazon development center u s",
        "amazon development center u s inc",
        "amazon web services",
        "amazon web services inc",
        "amazon data services",
        "amazon data services inc",
        "amazon com",
        "amazon com inc",
    ],
    "aws": [
        "amazon web services",
        "amazon web services inc",
        "amazon com services",
        "amazon com services llc",
    ],
    "amazon web services": [
        "amazon web services",
        "amazon web services inc",
        "amazon com services",
        "amazon com services llc",
    ],
    "google": ["google", "google llc"],
    "microsoft": ["microsoft", "microsoft corporation"],
    "meta": ["meta platforms", "meta platforms inc", "facebook", "facebook inc"],
    "apple": ["apple", "apple inc"],
    "nvidia": ["nvidia", "nvidia corporation"],
    "salesforce": ["salesforce", "salesforce inc", "salesforce com", "salesforce com inc"],
    "servicenow": ["servicenow", "servicenow inc"],
    "oracle": ["oracle america", "oracle america inc", "oracle"],
    "adobe": ["adobe", "adobe inc"],
    "capital one": [
        "capital one services",
        "capital one services llc",
        "capital one national association",
        "capital one",
    ],
    "jpmorgan chase": [
        "jpmorgan chase",
        "jpmorgan chase and co",
        "jpmorgan chase bank",
        "jpmorgan chase bank na",
    ],
    "visa": [
        "visa",
        "visa usa",
        "visa usa inc",
        "visa technology and operations",
        "visa technology and operations llc",
    ],
    "mastercard": ["mastercard", "mastercard international", "mastercard international incorporated"],
    "paypal": ["paypal", "paypal inc"],
    "intuit": ["intuit", "intuit inc"],
    "walmart": ["walmart", "walmart associates", "walmart associates inc", "walmart global tech"],
    "walmart global tech": ["walmart", "walmart associates", "walmart associates inc", "walmart global tech"],
}

def _tokens(name: str) -> set[str]:
    parts = normalize_company_name(name).split()
    return {p for p in parts if p and p not in STOPWORDS and len(p) > 1}

def candidate_keys(company: str) -> list[str]:
    base = normalize_company_name(company)

    # Curated aliases are checked BEFORE the generic company name.
    # This prevents umbrella brands like Amazon from matching a tiny
    # unrelated legal entity such as "Amazon LLC" before their primary
    # sponsoring entities.
    aliases = [
        normalize_company_name(x)
        for x in MANUAL_ALIASES.get(base, [])
    ]

    keys = aliases + [base]

    return list(
        dict.fromkeys(
            k for k in keys if k
        )
    )

def best_unique_match(company: str, sponsor_names: list[str]) -> tuple[str | None, float, str]:
    sponsor_set = set(sponsor_names)

    for key in candidate_keys(company):
        if key in sponsor_set:
            return key, 1.0, "EXACT_OR_ALIAS"

    company_tokens = _tokens(company)
    if company_tokens:
        subset = []
        for name in sponsor_names:
            st = _tokens(name)
            if company_tokens and company_tokens.issubset(st):
                subset.append(name)
        if len(subset) == 1:
            return subset[0], 0.96, "UNIQUE_TOKEN_SUBSET"

    base = normalize_company_name(company)
    scored = []
    for name in sponsor_names:
        score = SequenceMatcher(None, base, name).ratio()
        if score >= 0.92:
            scored.append((score, name))
    scored.sort(reverse=True)

    if len(scored) == 1:
        return scored[0][1], scored[0][0], "UNIQUE_HIGH_SIMILARITY"

    if len(scored) >= 2 and scored[0][0] - scored[1][0] >= 0.08:
        return scored[0][1], scored[0][0], "CLEAR_BEST_HIGH_SIMILARITY"

    return None, 0.0, "NO_UNAMBIGUOUS_MATCH"
