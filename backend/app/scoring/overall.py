from __future__ import annotations

import re
from datetime import datetime, timezone


# ---------------------------------------------------------
# EMPLOYER TIERS
# ---------------------------------------------------------

TIER_1_EMPLOYERS = {
    "amazon",
    "airbnb",
    "anthropic",
    "apple",
    "capital one",
    "chime",
    "coinbase",
    "databricks",
    "datadog",
    "google",
    "jpmorgan chase",
    "mastercard",
    "meta",
    "microsoft",
    "mongodb",
    "nvidia",
    "openai",
    "oracle",
    "pinterest",
    "reddit",
    "robinhood",
    "salesforce",
    "scale ai",
    "servicenow",
    "snowflake",
    "stripe",
    "twilio",
    "visa",
    "walmart global tech",
    "workday",
}

TARGET_TITLE_PATTERNS = (
    r"software engineer",
    r"software developer",
    r"software development engineer",
    r"backend engineer",
    r"backend developer",
    r"full.?stack",
    r"frontend engineer",
    r"front.?end engineer",
    r"platform engineer",
    r"cloud engineer",
    r"application engineer",
    r"api engineer",
    r"distributed systems",
    r"infrastructure engineer",
    r"devops engineer",
    r"site reliability engineer",
    r"\bsre\b",
)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _normalize(value) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or "").strip().lower(),
    )


def _parse_datetime(value):
    if not value:
        return None

    raw = str(value).strip()

    try:
        dt = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc)

    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d",
        "%B %d, %Y",
        "%b %d, %Y",
    ):
        try:
            return datetime.strptime(
                raw,
                fmt,
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def _job_age_hours(job):
    # Source publication date is authoritative.
    value = (
        job.get("source_published_at")
        or job.get("effective_posted_at")
    )

    dt = _parse_datetime(value)

    if not dt:
        return None

    now = datetime.now(timezone.utc)

    hours = (now - dt).total_seconds() / 3600

    # Future timestamps should not earn extra credit.
    return max(0.0, hours)


# ---------------------------------------------------------
# FRESHNESS: 0–25
# ---------------------------------------------------------

def _freshness_score(job):
    confidence = _normalize(
        job.get("freshness_confidence")
    ).upper()

    hours = _job_age_hours(job)

    if hours is None:
        return 0, "Posting date unknown"

    # The strict 24h feed already requires HIGH confidence.
    # Scoring still gives MEDIUM dates partial usefulness.
    confidence_factor = {
        "HIGH": 1.0,
        "MEDIUM": 0.80,
        "UNKNOWN": 0.50,
        "": 0.50,
    }.get(confidence, 0.50)

    if hours <= 24:
        points = 25
        label = "Posted within 24 hours"

    elif hours <= 48:
        points = 21
        label = "Posted within 48 hours"

    elif hours <= 72:
        points = 17
        label = "Posted within 3 days"

    elif hours <= 168:
        points = 8
        label = "Posted within 7 days"

    else:
        points = 0
        label = "Older than 7 days"

    points = round(points * confidence_factor)

    return points, label


# ---------------------------------------------------------
# EXPERIENCE: 0–20
# ---------------------------------------------------------

def _experience_score(job):
    years = job.get("min_experience_years")

    if years is None:
        return 10, "Experience requirement not specified"

    try:
        years = float(years)
    except (TypeError, ValueError):
        return 10, "Experience requirement unclear"

    if years <= 4:
        return 20, f"{years:g}+ YOE is a strong fit"

    if years <= 5:
        return 18, f"{years:g}+ YOE is a good fit"

    if years <= 6:
        return 15, f"{years:g}+ YOE is within target range"

    return 0, f"{years:g}+ YOE exceeds target range"


# ---------------------------------------------------------
# SPONSORSHIP: 0–20
# ---------------------------------------------------------

def _sponsorship_score(job):
    visa_detail = _normalize(
        job.get("visa_detail_status")
        or job.get("visa_language_status")
    ).upper()

    history = _normalize(
        job.get("h1b_history_strength")
    ).upper()

    # Explicit current-job language gets first priority.
    if visa_detail == "SPONSORSHIP_AVAILABLE":
        return 20, "Posting explicitly supports sponsorship"

    if visa_detail in {
        "F1_OPT_COMPATIBLE_SIGNAL",
        "OPT_F1_MENTIONED",
    }:
        if history == "STRONG":
            return 20, "F-1/OPT signal + strong sponsor history"

        return 18, "F-1/OPT-compatible language detected"

    if visa_detail == "WORK_AUTHORIZATION_MENTIONED":
        if history == "STRONG":
            return 17, "Work authorization language + strong sponsor history"

        return 13, "Work authorization language detected"

    if visa_detail in {
        "NO_SPONSORSHIP",
        "RESTRICTED",
    }:
        return 0, "Posting contains restrictive sponsorship language"

    # No explicit posting language: rely on historical evidence.
    return {
        "STRONG": (
            17,
            "Strong historical H-1B sponsorship evidence",
        ),
        "MEDIUM": (
            12,
            "Moderate historical H-1B sponsorship evidence",
        ),
        "LOW": (
            6,
            "Limited historical H-1B sponsorship evidence",
        ),
        "UNKNOWN": (
            2,
            "Sponsorship history unknown",
        ),
        "": (
            2,
            "Sponsorship history unknown",
        ),
    }.get(
        history,
        (2, "Sponsorship history unknown"),
    )


# ---------------------------------------------------------
# EMPLOYER / SOURCE QUALITY: 0–15
# ---------------------------------------------------------

def _employer_score(job):
    source_type = _normalize(
        job.get("source_type")
    ).upper()

    company = _normalize(
        job.get("company_name_raw")
    )

    if source_type == "DIRECT_EMPLOYER":
        if company in TIER_1_EMPLOYERS:
            return 15, "Priority direct employer"

        return 12, "Direct employer"

    if source_type == "STARTUP":
        return 10, "Startup direct source"

    if source_type == "CONSULTING":
        return 6, "Consulting employer"

    if source_type == "STAFFING_AGENCY":
        return 4, "Staffing agency"

    return 7, "Source type requires review"


# ---------------------------------------------------------
# ROLE / SKILL FIT: 0–10
# ---------------------------------------------------------

def _role_score(job):
    title = _normalize(job.get("title"))

    if not title:
        return 0, "Missing job title"

    for pattern in TARGET_TITLE_PATTERNS:
        if re.search(pattern, title, re.I):
            return 10, "Strong software-engineering title match"

    # Still keep technical roles for review.
    if any(
        term in title
        for term in (
            "engineer",
            "developer",
            "architect",
            "programmer",
        )
    ):
        return 6, "Related technical role"

    return 2, "Weak role-title match"


# ---------------------------------------------------------
# LOCATION: 0–10
# ---------------------------------------------------------

def _location_score(job):
    location = _normalize(
        job.get("location_raw")
    )

    work = _normalize(
        job.get("work_arrangement")
    ).upper()

    # -----------------------------------------------------
    # Explicit non-US locations receive no location points.
    # -----------------------------------------------------

    non_us = (
        "remote uk",
        "united kingdom",
        "england",
        "ireland",
        "dublin",
        "canada",
        "toronto",
        "vancouver",
        "india",
        "bengaluru",
        "bangalore",
        "hyderabad",
        "gurugram",
        "germany",
        "france",
        "spain",
        "poland",
        "greece",
        "israel",
        "china",
        "singapore",
        "australia",
        "japan",
    )

    if any(place in location for place in non_us):
        return 0, "Non-US location"

    # -----------------------------------------------------
    # Preferred US remote locations.
    # -----------------------------------------------------

    us_remote_signals = (
        "remote - united states",
        "remote united states",
        "united states - remote",
        "united states(remote)",
        "remote us",
        "remote, us",
        "remote - us",
        "us remote",
        "remote, usa",
        "remote usa",
    )

    if any(signal in location for signal in us_remote_signals):
        return 10, "US remote"

    # Some ATSs simply use "United States" for a remote-US role.
    if (
        work == "REMOTE"
        and location.strip() in {
            "united states",
            "usa",
            "us",
            "u.s.",
        }
    ):
        return 10, "US remote"

    # -----------------------------------------------------
    # Approved onsite/hybrid metros.
    # -----------------------------------------------------

    approved = (
        # Florida
        "florida",
        "miami",
        "orlando",
        "tampa",
        "jacksonville",
        "fort lauderdale",
        "boca raton",
        "west palm beach",

        # Dallas / DFW
        "dallas",
        "fort worth",
        "plano",
        "irving",
        "richardson",
        "frisco",
        "dfw",

        # Chicago
        "chicago",
        "naperville",
        "schaumburg",
        "evanston",
        "oak brook",

        # St. Louis
        "st. louis",
        "st louis",
        "saint louis",
        "chesterfield",

        # Kansas City
        "kansas city",
        "overland park",
        "lenexa",
        "olathe",
    )

    if any(place in location for place in approved):
        return 10, "Preferred onsite/hybrid metro"

    # -----------------------------------------------------
    # Explicit US location outside preferred metros.
    #
    # These jobs can stay in the database, but they should
    # not receive location-fit credit.
    # -----------------------------------------------------

    explicit_us = (
        "usa",
        "united states",
        ", ca",
        "california",
        ", ny",
        "new york",
        ", wa",
        "washington",
        ", ma",
        "massachusetts",
        ", tx",
        "texas",
        ", co",
        "colorado",
        ", or",
        "oregon",
    )

    if any(signal in location for signal in explicit_us):
        return 0, "US location outside preferred metros"

    # Truly ambiguous remote can receive small review credit.
    if work == "REMOTE":
        return 3, "Remote country requires review"

    if work == "UNKNOWN":
        return 2, "Work arrangement requires review"

    return 0, "Location outside preferred set"


# ---------------------------------------------------------
# FINAL V9 SCORE
# ---------------------------------------------------------

def calculate_overall_score(job: dict) -> dict:
    reasons = []
    breakdown = {}

    freshness, reason = _freshness_score(job)
    breakdown["freshness"] = freshness
    reasons.append(
        f"{reason} (+{freshness}/25)"
    )

    experience, reason = _experience_score(job)
    breakdown["experience"] = experience
    reasons.append(
        f"{reason} (+{experience}/20)"
    )

    sponsorship, reason = _sponsorship_score(job)
    breakdown["sponsorship"] = sponsorship
    reasons.append(
        f"{reason} (+{sponsorship}/20)"
    )

    employer, reason = _employer_score(job)
    breakdown["employer"] = employer
    reasons.append(
        f"{reason} (+{employer}/15)"
    )

    role, reason = _role_score(job)
    breakdown["role"] = role
    reasons.append(
        f"{reason} (+{role}/10)"
    )

    location, reason = _location_score(job)
    breakdown["location"] = location
    reasons.append(
        f"{reason} (+{location}/10)"
    )

    score = (
        freshness
        + experience
        + sponsorship
        + employer
        + role
        + location
    )

    # Explicitly restrictive postings should never become
    # high-priority recommendations even if other signals are good.
    visa_detail = _normalize(
        job.get("visa_detail_status")
        or job.get("visa_language_status")
    ).upper()

    if visa_detail in {
        "NO_SPONSORSHIP",
        "RESTRICTED",
    }:
        score = min(score, 35)

    # Jobs above the target experience range should similarly
    # never rank highly if they somehow exist outside the strict feed.
    years = job.get("min_experience_years")

    try:
        if years is not None and float(years) > 6:
            score = min(score, 45)
    except (TypeError, ValueError):
        pass

    score = int(
        max(
            0,
            min(100, round(score)),
        )
    )

    if score >= 90:
        band = "BEST_MATCH"

    elif score >= 80:
        band = "STRONG_MATCH"

    elif score >= 70:
        band = "GOOD_MATCH"

    elif score >= 60:
        band = "REVIEW"

    else:
        band = "LOW_PRIORITY"

    return {
        "score": score,
        "band": band,
        "reasons": reasons,
        "breakdown": breakdown,
    }