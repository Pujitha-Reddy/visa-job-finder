from __future__ import annotations

from collections import defaultdict

from app.database import (
    get_connection,
)


def ranked_candidates(
    limit=1000,
):
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                j.id,
                j.canonical_title,
                j.canonical_location,
                j.posted_at,
                j.last_seen_at,
                j.preferred_apply_url,
                j.preferred_source_url,

                i.id AS employer_identity_id,
                i.canonical_name AS employer_name,

                e.software_role_family,
                e.work_arrangement,

                e.seniority_band,
                e.min_experience_years,
                e.max_experience_years,

                e.sponsor_history_strength,
                e.visa_language_status,
                e.sponsorship_score,

                e.relevance_score,
                e.freshness_score,
                e.source_quality_score,
                e.overall_score

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            JOIN employer_identities i
              ON i.id=j.employer_identity_id

            WHERE j.is_active=1
              AND e.is_eligible=1

            ORDER BY
                e.overall_score DESC,

                COALESCE(
                    j.posted_at,
                    j.last_seen_at
                ) DESC,

                j.id DESC

            LIMIT ?
        """, (
            int(limit),
        )).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def diversified_feed(
    *,
    limit=100,
    max_per_employer=4,
    candidate_pool=1000,
):
    """
    Preserve the original ranking while limiting employer
    concentration in one returned feed/page.

    No job's stored overall_score is altered.
    """

    candidates = ranked_candidates(
        limit=candidate_pool,
    )

    selected = []
    employer_counts = defaultdict(
        int
    )

    # ------------------------------------------------------
    # Pass 1:
    # diversified results
    # ------------------------------------------------------

    for job in candidates:

        employer_id = job[
            "employer_identity_id"
        ]

        if (
            employer_counts[
                employer_id
            ]
            >= max_per_employer
        ):
            continue

        selected.append(
            job
        )

        employer_counts[
            employer_id
        ] += 1

        if len(selected) >= limit:
            return selected

    # ------------------------------------------------------
    # Pass 2:
    #
    # If diversification prevented us from filling the
    # requested page, backfill using remaining ranked jobs.
    # ------------------------------------------------------

    selected_ids = {
        job["id"]
        for job in selected
    }

    for job in candidates:

        if job["id"] in selected_ids:
            continue

        selected.append(
            job
        )

        if len(selected) >= limit:
            break

    return selected
