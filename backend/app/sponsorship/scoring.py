from __future__ import annotations
from datetime import datetime


def score_sponsor_history(records: list[dict], current_year: int | None = None) -> dict:
    """
    Produce a conservative employer-history score.

    This is NOT a claim that a specific opening sponsors.
    It measures historical H-1B/LCA evidence only.
    """
    current_year = current_year or datetime.utcnow().year
    total_filings = 0
    total_approved = 0
    total_denied = 0
    recent_filings = 0
    sources = set()
    years = set()

    for r in records:
        filings = int(r.get("filings_count") or 0)
        approved = int(r.get("approved_count") or 0)
        denied = int(r.get("denied_count") or 0)
        year = r.get("source_year")

        total_filings += filings
        total_approved += approved
        total_denied += denied
        sources.add(r.get("source") or "UNKNOWN")

        if year:
            years.add(int(year))
            if int(year) >= current_year - 2:
                recent_filings += filings

    score = 0

    # Volume signal.
    if total_filings >= 500:
        score += 45
    elif total_filings >= 100:
        score += 38
    elif total_filings >= 25:
        score += 30
    elif total_filings >= 5:
        score += 20
    elif total_filings >= 1:
        score += 10

    # Recency signal.
    if recent_filings >= 100:
        score += 30
    elif recent_filings >= 25:
        score += 24
    elif recent_filings >= 5:
        score += 16
    elif recent_filings >= 1:
        score += 8

    # Multiple official sources increase confidence.
    official_sources = {s.upper() for s in sources} & {"DOL", "USCIS"}
    if len(official_sources) == 2:
        score += 15
    elif len(official_sources) == 1:
        score += 8

    # Approval signal when USCIS-style approval/denial counts are available.
    decisions = total_approved + total_denied
    if decisions:
        approval_rate = total_approved / decisions
        if approval_rate >= 0.95:
            score += 10
        elif approval_rate >= 0.80:
            score += 7
        elif approval_rate >= 0.60:
            score += 3

    score = min(100, score)

    if score >= 70:
        strength = "STRONG"
    elif score >= 45:
        strength = "MEDIUM"
    elif score > 0:
        strength = "LOW"
    else:
        strength = "UNKNOWN"

    return {
        "score": score,
        "strength": strength,
        "total_filings": total_filings,
        "recent_filings": recent_filings,
        "total_approved": total_approved,
        "total_denied": total_denied,
        "sources": sorted(sources),
        "years": sorted(years),
    }


def combine_job_and_sponsor(
    visa_language_status: str,
    sponsor_strength: str,
    sponsor_score: float,
) -> dict:
    """
    Current-job language always outranks historical sponsor evidence.
    """
    if visa_language_status in {"NO_SPONSORSHIP", "RESTRICTED"}:
        return {
            "sponsorship_score": 0,
            "label": "SKIP",
            "reason": "Current job contains explicit sponsorship/work-authorization restrictions."
        }

    if visa_language_status == "SPONSORSHIP_AVAILABLE":
        return {
            "sponsorship_score": min(100, max(85, sponsor_score)),
            "label": "POSITIVE",
            "reason": "Current job explicitly indicates sponsorship availability."
        }

    if visa_language_status == "OPT_F1_MENTIONED":
        return {
            "sponsorship_score": min(100, max(70, sponsor_score)),
            "label": "POSITIVE_REVIEW",
            "reason": "Current job mentions F-1/OPT/CPT; future H-1B sponsorship still requires review."
        }

    # Missing language is NEVER automatic rejection.
    if sponsor_strength == "STRONG":
        return {
            "sponsorship_score": sponsor_score,
            "label": "NEEDS_REVIEW_STRONG_HISTORY",
            "reason": "No job-specific visa language found, but employer has strong historical sponsor evidence."
        }

    if sponsor_strength == "MEDIUM":
        return {
            "sponsorship_score": sponsor_score,
            "label": "NEEDS_REVIEW_MEDIUM_HISTORY",
            "reason": "No job-specific visa language found; employer has moderate historical sponsor evidence."
        }

    return {
        "sponsorship_score": sponsor_score,
        "label": "NEEDS_REVIEW",
        "reason": "No job-specific visa language found and sponsor history is weak or unknown."
    }
