from __future__ import annotations
import re

NON_US_LOCATION_TERMS = {
    "poland","dublin","ireland","canada","mexico","united kingdom","england","scotland",
    "germany","france","spain","italy","netherlands","belgium","sweden","norway",
    "denmark","finland","switzerland","austria","portugal","czech","romania","hungary",
    "india","singapore","australia","new zealand","japan","china","hong kong","taiwan",
    "philippines","brazil","argentina","colombia","chile","peru","israel",
    "united arab emirates","south africa"
}

TITLE_REGION_CONFLICT = re.compile(
    r"\b(japan|india|emea|europe|apac|asia pacific|canada|uk|united kingdom|"
    r"germany|france|poland|ireland|australia|singapore)\b",
    re.I,
)

US_HINTS = {
    "united states","usa","u.s.","u.s.a.","remote - us","remote us","us remote",
    "nationwide","washington, d.c.","washington dc"
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

ALLOWED_ONSITE_HYBRID_TERMS = {
    # Florida statewide
    "florida","miami","orlando","tampa","jacksonville","fort lauderdale",
    "west palm beach","boca raton","clearwater","st. petersburg","st petersburg",
    # Dallas / DFW
    "dallas","fort worth","plano","irving","richardson","frisco","addison","dfw",
    # Chicago metro
    "chicago","chicagoland","naperville","schaumburg","evanston","oak brook",
    # St. Louis metro
    "st. louis","st louis","saint louis","clayton","chesterfield",
    # Kansas City metro (MO + KS)
    "kansas city","overland park","lenexa","shawnee","olathe",
}

def _location_text(job: dict) -> str:
    return f"{job.get('location_raw') or ''} {job.get('country') or ''}".lower().strip()

def location_country_signal(job: dict) -> str:
    text = _location_text(job)

    if any(term in text for term in NON_US_LOCATION_TERMS):
        return "NON_US"

    if any(term in text for term in US_HINTS):
        return "US"

    if any(state in text for state in US_STATE_NAMES):
        return "US"

    # common US state abbreviations after comma
    if re.search(r",\s*(al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy|dc)\b", text):
        return "US"

    return "UNKNOWN"

def location_eligibility(job: dict) -> str:
    loc_text = _location_text(job)
    signal = location_country_signal(job)
    work = (job.get("work_arrangement") or "UNKNOWN").upper()
    title = job.get("title") or ""

    if signal == "NON_US":
        return "NON_US"

    if TITLE_REGION_CONFLICT.search(title):
        # Keep in DB for review, but production strict query can hide conflicts.
        return "REVIEW_TITLE_LOCATION_CONFLICT"

    if work == "REMOTE":
        return "US_REMOTE" if signal == "US" else "REVIEW_REMOTE_COUNTRY_UNKNOWN"

    if work in {"HYBRID", "ONSITE"}:
        if signal != "US":
            return "NON_US_OR_UNKNOWN_ONSITE"
        if any(term in loc_text for term in ALLOWED_ONSITE_HYBRID_TERMS):
            return "ALLOWED_METRO"
        return "OUTSIDE_ALLOWED_METROS"

    # UNKNOWN arrangement stays reviewable; strict UI decides whether to show it.
    return "REVIEW_WORK_ARRANGEMENT"

def experience_eligibility(job: dict) -> str:
    min_y = job.get("min_experience_years")
    if min_y is not None:
        try:
            return "OVER_6" if float(min_y) > 6 else "IN_RANGE"
        except Exception:
            pass

    text = (job.get("experience_text") or "").lower()
    nums = [int(x) for x in re.findall(r"\b(\d{1,2})\s*\+?\s*years?\b", text)]
    if nums:
        return "OVER_6" if min(nums) > 6 else "IN_RANGE"

    return "NOT_SPECIFIED"

def employment_eligibility(job: dict) -> str:
    emp = (job.get("employment_type") or "UNKNOWN").upper()
    detail = (job.get("employment_detail_type") or "").upper()
    if emp in {"INTERNSHIP", "TEMPORARY"} or detail in {"INTERNSHIP", "TEMPORARY"}:
        return "EXCLUDE"
    return "KEEP"

def source_confidence(job: dict) -> tuple[int, str]:
    ats = (job.get("ats") or "").upper()
    source_type = (job.get("source_type") or "").upper()
    url = (job.get("source_url") or "").lower()

    score = 50

    if ats in {
        "GREENHOUSE","LEVER","ASHBY","WORKDAY","SMARTRECRUITERS",
        "WORKABLE","AMAZON_JOBS"
    }:
        score += 30

    if source_type == "DIRECT_EMPLOYER":
        score += 15
    elif source_type == "STAFFING_AGENCY":
        score += 8

    if any(x in url for x in (
        "greenhouse.io","lever.co","ashbyhq.com","myworkdayjobs.com",
        "smartrecruiters.com","workable.com","amazon.jobs"
    )):
        score += 5

    score = max(0, min(100, score))

    if score >= 90:
        label = "VERIFIED_ORIGINAL"
    elif score >= 75:
        label = "HIGH_CONFIDENCE"
    else:
        label = "NEEDS_REVIEW"

    return score, label

def eligibility_gate(job: dict) -> dict:
    loc = location_eligibility(job)
    exp = experience_eligibility(job)
    emp = employment_eligibility(job)
    conf_score, conf_label = source_confidence(job)

    if emp == "EXCLUDE":
        eligible = False
        reason = "EMPLOYMENT_EXCLUDED"
    elif exp == "OVER_6":
        eligible = False
        reason = "OVER_6_YOE"
    elif loc in {"NON_US","NON_US_OR_UNKNOWN_ONSITE","OUTSIDE_ALLOWED_METROS"}:
        eligible = False
        reason = loc
    else:
        # review states remain collected so we don't lose potentially useful jobs.
        eligible = True
        reason = "KEEP"

    return {
        "eligible": eligible,
        "reason": reason,
        "location": loc,
        "experience": exp,
        "source_confidence_score": conf_score,
        "source_confidence_label": conf_label,
    }
