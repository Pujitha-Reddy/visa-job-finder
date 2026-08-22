from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)


# ==========================================================
# EXPERIENCE FIT
# ==========================================================


EXPERIENCE_FIT = {
    "EARLY_CAREER": 100.0,
    "MID": 100.0,
    "EXPERIENCED": 90.0,
    "SENIOR": 80.0,
    "LEAD": 72.0,

    # These should normally not be AUTO-ELIGIBLE.
    "UNKNOWN": 50.0,
    "STAFF": 35.0,
    "PRINCIPAL": 25.0,
    "MANAGER": 20.0,
    "EXECUTIVE": 10.0,
    "INTERN": 10.0,
}


VISA_SIGNAL_SCORE = {
    "EXPLICIT_SPONSORSHIP": 100.0,
    "POSSIBLE_SPONSORSHIP": 90.0,
    "NO_EXPLICIT_LANGUAGE": 60.0,
    "EXPLICIT_NO_SPONSORSHIP": 0.0,
}


def clamp(
    value,
    low=0.0,
    high=100.0,
):
    try:
        value = float(value)
    except Exception:
        value = 0.0

    return max(
        low,
        min(
            high,
            value,
        ),
    )


def parse_datetime(value):
    if not value:
        return None

    value = str(
        value
    ).strip()

    if not value:
        return None

    try:
        if value.endswith("Z"):
            value = (
                value[:-1]
                + "+00:00"
            )

        dt = datetime.fromisoformat(
            value
        )

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone(
            timezone.utc
        )

    except Exception:
        pass

    # SQLite-style timestamps.
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(
                value,
                fmt,
            )

            return dt.replace(
                tzinfo=timezone.utc
            )

        except Exception:
            continue

    return None


# ==========================================================
# FRESHNESS
# ==========================================================


def freshness_score(
    *,
    posted_at,
    last_seen_at,
    now=None,
):
    if now is None:
        now = datetime.now(
            timezone.utc
        )

    posted = parse_datetime(
        posted_at
    )

    seen = parse_datetime(
        last_seen_at
    )

    reference = (
        posted
        or seen
    )

    if reference is None:
        return 40.0

    age_days = max(
        0.0,
        (
            now - reference
        ).total_seconds()
        / 86400.0,
    )

    if age_days <= 1:
        return 100.0

    if age_days <= 3:
        return 98.0

    if age_days <= 7:
        return 95.0

    if age_days <= 14:
        return 90.0

    if age_days <= 30:
        return 82.0

    if age_days <= 45:
        return 74.0

    if age_days <= 60:
        return 65.0

    if age_days <= 90:
        return 52.0

    if age_days <= 120:
        return 40.0

    if age_days <= 180:
        return 28.0

    return 15.0


# ==========================================================
# ROLE / EXPERIENCE RELEVANCE
# ==========================================================


def relevance_score(
    *,
    software_role_score,
    seniority_band,
    min_experience_years,
):
    software = clamp(
        software_role_score
    )

    band = (
        seniority_band
        or "UNKNOWN"
    )

    experience = EXPERIENCE_FIT.get(
        band,
        50.0,
    )

    # ======================================================
    # Explicit years refine experience fit.
    #
    # IMPORTANT:
    # They must NOT erase title seniority.
    #
    # Example:
    #
    #   Lead Software Engineer
    #   description contains "1+ year..."
    #
    # remains a LEAD-level ranking signal rather than
    # becoming a perfect early-career fit.
    # ======================================================

    if min_experience_years is not None:
        years = float(
            min_experience_years
        )

        if band in {
            "LEAD",
            "SENIOR",
        }:
            if years > 6:
                experience = min(
                    experience,
                    40.0,
                )

            # Otherwise preserve title-derived fit.

        elif band in {
            "STAFF",
            "PRINCIPAL",
            "MANAGER",
            "EXECUTIVE",
        }:
            # These should normally never reach the
            # automatic eligible feed, but preserve
            # conservative scoring if they do.
            experience = min(
                experience,
                EXPERIENCE_FIT.get(
                    band,
                    30.0,
                ),
            )

        else:
            if years <= 2:
                experience = max(
                    experience,
                    100.0,
                )

            elif years <= 3:
                experience = max(
                    experience,
                    98.0,
                )

            elif years <= 4:
                experience = max(
                    experience,
                    95.0,
                )

            elif years <= 6:
                experience = max(
                    experience,
                    85.0,
                )

            else:
                experience = min(
                    experience,
                    40.0,
                )

    return round(
        (
            software * 0.50
            + experience * 0.50
        ),
        2,
    )


# ==========================================================
# SOURCE QUALITY
# ==========================================================


def source_quality_score(
    *,
    best_source_confidence,
    source_count,
):
    confidence = clamp(
        best_source_confidence
    )

    # Multiple independent observations increase confidence,
    # but cannot turn a weak source into a great source.
    source_bonus = min(
        max(
            int(
                source_count
                or 1
            )
            - 1,
            0,
        )
        * 3.0,
        10.0,
    )

    return round(
        clamp(
            confidence
            + source_bonus
        ),
        2,
    )


# ==========================================================
# FINAL RANK
# ==========================================================


def rank_job(job):
    sponsorship = clamp(
        job.get(
            "sponsorship_score"
        )
    )

    relevance = relevance_score(
        software_role_score=(
            job.get(
                "software_role_score"
            )
        ),

        seniority_band=(
            job.get(
                "seniority_band"
            )
        ),

        min_experience_years=(
            job.get(
                "min_experience_years"
            )
        ),
    )

    freshness = freshness_score(
        posted_at=job.get(
            "posted_at"
        ),

        last_seen_at=job.get(
            "last_seen_at"
        ),
    )

    source_quality = (
        source_quality_score(
            best_source_confidence=(
                job.get(
                    "best_source_confidence"
                )
            ),

            source_count=(
                job.get(
                    "source_count"
                )
            ),
        )
    )

    visa_signal = (
        VISA_SIGNAL_SCORE.get(
            job.get(
                "visa_language_status"
            )
            or "NO_EXPLICIT_LANGUAGE",
            50.0,
        )
    )

    # ======================================================
    # Weighted score
    # ======================================================

    overall = (
        sponsorship * 0.35
        + relevance * 0.25
        + freshness * 0.20
        + source_quality * 0.10
        + visa_signal * 0.10
    )

    # ======================================================
    # Small evidence bonuses
    #
    # These are intentionally small. They should break ties,
    # not overpower the ranking model.
    # ======================================================

    if (
        job.get(
            "visa_language_status"
        )
        == "EXPLICIT_SPONSORSHIP"
    ):
        overall += 3.0

    if (
        job.get(
            "work_arrangement"
        )
        == "REMOTE"
        and job.get(
            "is_us_remote"
        ) == 1
    ):
        overall += 1.5

    if int(
        job.get(
            "source_count"
        )
        or 1
    ) > 1:
        overall += 1.0

    overall = clamp(
        overall
    )

    return {
        "relevance_score": (
            relevance
        ),

        "freshness_score": (
            round(
                freshness,
                2,
            )
        ),

        "source_quality_score": (
            source_quality
        ),

        "overall_score": (
            round(
                overall,
                2,
            )
        ),

        "visa_signal_score": (
            visa_signal
        ),

        "sponsorship_component": (
            sponsorship
        ),
    }
