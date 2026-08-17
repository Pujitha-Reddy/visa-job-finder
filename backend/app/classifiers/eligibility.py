from __future__ import annotations
import re

NON_US_HINTS = {
    "poland","canada","mexico","united kingdom","uk","england","scotland","ireland",
    "germany","france","spain","italy","netherlands","belgium","sweden","norway",
    "denmark","finland","switzerland","austria","portugal","czech","romania","hungary",
    "india","singapore","australia","new zealand","japan","china","hong kong","taiwan",
    "philippines","brazil","argentina","colombia","chile","peru","israel","uae",
    "united arab emirates","south africa"
}

US_HINTS = {
    "united states","usa","u.s.","u.s.a.","us remote","remote - us","remote, us",
    "remote us","nationwide","anywhere in the us","anywhere in the united states"
}

US_STATE_NAMES = {
    "alabama","alaska","arizona","arkansas","california","colorado","connecticut",
    "delaware","florida","georgia","hawaii","idaho","illinois","indiana","iowa",
    "kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan",
    "minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire",
    "new jersey","new mexico","new york","north carolina","north dakota","ohio",
    "oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota",
    "tennessee","texas","utah","vermont","virginia","washington","west virginia",
    "wisconsin","wyoming","district of columbia"
}

SENIORITY_REVIEW = re.compile(r"\b(staff|principal|lead|distinguished|architect)\b", re.I)

def classify_us_eligibility(location_raw: str | None, country: str | None = None) -> str:
    text = f"{location_raw or ''} {country or ''}".lower().strip()
    if any(h in text for h in NON_US_HINTS):
        return "NON_US"
    if any(h in text for h in US_HINTS):
        return "US"
    if any(state in text for state in US_STATE_NAMES):
        return "US"
    if "remote" in text or not text:
        return "REVIEW"
    return "REVIEW"

def experience_eligibility(min_years, max_years, experience_text: str | None = None) -> str:
    try:
        min_y = float(min_years) if min_years is not None else None
    except Exception:
        min_y = None
    try:
        max_y = float(max_years) if max_years is not None else None
    except Exception:
        max_y = None
    if min_y is not None and min_y > 6:
        return "OVER_6"
    if min_y is not None and min_y <= 6:
        return "IN_RANGE"
    text = (experience_text or "").lower()
    nums = [int(x) for x in re.findall(r"\b(\d{1,2})\s*\+?\s*years?\b", text)]
    if nums:
        first = min(nums)
        return "OVER_6" if first > 6 else "IN_RANGE"
    return "NOT_SPECIFIED"

def seniority_flag(title: str | None) -> str:
    return "SENIORITY_REVIEW" if SENIORITY_REVIEW.search(title or "") else "OK"

def eligibility_gate(job: dict) -> dict:
    us = classify_us_eligibility(job.get("location_raw"), job.get("country"))
    exp = experience_eligibility(
        job.get("min_experience_years"),
        job.get("max_experience_years"),
        job.get("experience_text"),
    )
    seniority = seniority_flag(job.get("title"))
    if us == "NON_US":
        return {"eligible": False, "reason": "NON_US", "us_eligibility": us,
                "experience_eligibility": exp, "seniority_flag": seniority}
    if exp == "OVER_6":
        return {"eligible": False, "reason": "OVER_6_YOE", "us_eligibility": us,
                "experience_eligibility": exp, "seniority_flag": seniority}
    return {"eligible": True, "reason": "KEEP", "us_eligibility": us,
            "experience_eligibility": exp, "seniority_flag": seniority}
