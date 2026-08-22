from __future__ import annotations


# ==========================================================
# Eligibility policy
# ==========================================================

HARD_EXCLUDE_SENIORITY = {
    "EXECUTIVE",
    "MANAGER",
    "PRINCIPAL",
    "STAFF",
}

SOFT_REVIEW_SENIORITY = {
    "LEAD",
    "SENIOR",
    "UNKNOWN",
}

ACCEPTABLE_SPONSOR_STRENGTH = {
    "STRONG",
    "GOOD",
    "MODERATE",
}

MAX_EXPERIENCE_YEARS = 6


def evaluate_location(job):
    is_us_job = job.get("is_us_job")
    is_us_remote = job.get("is_us_remote")
    arrangement = job.get("work_arrangement")

    if is_us_job == 0:
        return {
            "status": "REJECT",
            "reason": "NON_US_JOB",
        }

    if is_us_remote == 1:
        return {
            "status": "KEEP",
            "reason": "US_REMOTE",
        }

    if is_us_job == 1:
        return {
            "status": "KEEP",
            "reason": "US_LOCATION",
        }

    if arrangement == "REMOTE":
        return {
            "status": "REVIEW",
            "reason": "REMOTE_COUNTRY_UNKNOWN",
        }

    return {
        "status": "REVIEW",
        "reason": "LOCATION_UNKNOWN",
    }


def evaluate_experience(job):
    band = job.get("seniority_band")
    min_years = job.get("min_experience_years")

    if band == "INTERN":
        return {
            "status": "REJECT",
            "reason": "INTERNSHIP",
        }

    if band in HARD_EXCLUDE_SENIORITY:
        return {
            "status": "REJECT",
            "reason": f"SENIORITY_{band}",
        }

    if (
        min_years is not None
        and float(min_years) > MAX_EXPERIENCE_YEARS
    ):
        return {
            "status": "REJECT",
            "reason": "EXPERIENCE_ABOVE_6_YEARS",
        }

    if band in {
        "EARLY_CAREER",
        "MID",
        "EXPERIENCED",
    }:
        return {
            "status": "KEEP",
            "reason": f"SENIORITY_{band}",
        }

    if band in SOFT_REVIEW_SENIORITY:
        if (
            min_years is not None
            and float(min_years) <= MAX_EXPERIENCE_YEARS
        ):
            return {
                "status": "KEEP",
                "reason": (
                    f"{band}_WITH_ACCEPTABLE_EXPLICIT_YEARS"
                ),
            }

        return {
            "status": "REVIEW",
            "reason": f"SENIORITY_{band}_REVIEW",
        }

    return {
        "status": "REVIEW",
        "reason": "EXPERIENCE_UNKNOWN",
    }


def evaluate_sponsorship(job):
    visa = job.get("visa_language_status")
    strength = job.get("sponsor_history_strength")
    score = float(
        job.get("sponsorship_score")
        or 0
    )

    if visa == "EXPLICIT_NO_SPONSORSHIP":
        return {
            "status": "REJECT",
            "reason": "JOB_EXPLICIT_NO_SPONSORSHIP",
        }

    if visa == "EXPLICIT_SPONSORSHIP":
        return {
            "status": "KEEP",
            "reason": "JOB_EXPLICIT_SPONSORSHIP",
        }

    if visa == "POSSIBLE_SPONSORSHIP":
        if score >= 50:
            return {
                "status": "KEEP",
                "reason": "POSSIBLE_SPONSORSHIP_WITH_HISTORY",
            }

        return {
            "status": "REVIEW",
            "reason": "POSSIBLE_SPONSORSHIP_WEAK_HISTORY",
        }

    if strength in ACCEPTABLE_SPONSOR_STRENGTH:
        return {
            "status": "KEEP",
            "reason": f"SPONSOR_HISTORY_{strength}",
        }

    if strength == "WEAK":
        return {
            "status": "REVIEW",
            "reason": "SPONSOR_HISTORY_WEAK",
        }

    return {
        "status": "REVIEW",
        "reason": "SPONSOR_HISTORY_UNKNOWN",
    }


def evaluate_job(job):
    if not job.get("is_active"):
        return {
            "is_eligible": 0,
            "eligibility_reason": "INACTIVE",
            "location_eligibility": None,
            "experience_eligibility": None,
            "sponsorship_eligibility": None,
        }

    if not job.get("is_software_role"):
        return {
            "is_eligible": 0,
            "eligibility_reason": "NOT_SOFTWARE_ROLE",
            "location_eligibility": None,
            "experience_eligibility": None,
            "sponsorship_eligibility": None,
        }

    location = evaluate_location(job)
    experience = evaluate_experience(job)
    sponsorship = evaluate_sponsorship(job)

    components = {
        "location": location,
        "experience": experience,
        "sponsorship": sponsorship,
    }

    # ------------------------------------------------------
    # Hard rejection wins.
    # ------------------------------------------------------

    for name in (
        "location",
        "experience",
        "sponsorship",
    ):
        result = components[name]

        if result["status"] == "REJECT":
            return {
                "is_eligible": 0,
                "eligibility_reason": result["reason"],
                "location_eligibility": location["reason"],
                "experience_eligibility": experience["reason"],
                "sponsorship_eligibility": sponsorship["reason"],
            }

    # ------------------------------------------------------
    # Any unresolved component => review.
    #
    # We preserve these in the enrichment layer, but do not
    # put them in the primary automatic feed yet.
    # ------------------------------------------------------

    reviews = [
        result["reason"]
        for result in components.values()
        if result["status"] == "REVIEW"
    ]

    if reviews:
        return {
            "is_eligible": 0,
            "eligibility_reason": (
                "REVIEW:"
                + "|".join(reviews)
            ),
            "location_eligibility": location["reason"],
            "experience_eligibility": experience["reason"],
            "sponsorship_eligibility": sponsorship["reason"],
        }

    return {
        "is_eligible": 1,
        "eligibility_reason": "KEEP",
        "location_eligibility": location["reason"],
        "experience_eligibility": experience["reason"],
        "sponsorship_eligibility": sponsorship["reason"],
    }
