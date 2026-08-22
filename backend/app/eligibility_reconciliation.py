from __future__ import annotations

from .database import get_connection


def reconcile_job_eligibility(
    employer_name: str,
    eligible_jobs: list[dict],
    excluded_jobs: list[dict],
):
    """
    Reconcile feed eligibility independently from source lifecycle.

    IMPORTANT:
    - This function does NOT insert excluded jobs.
    - It only updates jobs that already exist in the jobs table.
    - is_active is intentionally untouched.
    - Lifecycle owns is_active.
    """

    eligible_updated = 0
    excluded_updated = 0

    with get_connection() as conn:
        # --------------------------------------------------
        # Current eligible jobs
        # --------------------------------------------------

        for job in eligible_jobs:
            source_url = (
                job.get("source_url")
                or ""
            ).strip()

            if not source_url:
                continue

            cur = conn.execute(
                """
                UPDATE jobs
                SET
                    is_eligible=1,
                    eligibility_reason=?,
                    location_eligibility=?,
                    experience_eligibility=?,
                    last_seen_at=CURRENT_TIMESTAMP
                WHERE company_name_raw=?
                  AND source_url=?
                """,
                (
                    job.get("eligibility_reason")
                    or "KEEP",

                    job.get(
                        "location_eligibility"
                    ),

                    job.get(
                        "experience_eligibility"
                    ),

                    employer_name,
                    source_url,
                ),
            )

            eligible_updated += (
                cur.rowcount
                or 0
            )

        # --------------------------------------------------
        # Current source jobs that fail eligibility
        # --------------------------------------------------

        for job in excluded_jobs:
            source_url = (
                job.get("source_url")
                or ""
            ).strip()

            if not source_url:
                continue

            cur = conn.execute(
                """
                UPDATE jobs
                SET
                    is_eligible=0,
                    eligibility_reason=?,
                    location_eligibility=?,
                    experience_eligibility=?,
                    last_seen_at=CURRENT_TIMESTAMP
                WHERE company_name_raw=?
                  AND source_url=?
                """,
                (
                    job.get(
                        "eligibility_reason"
                    )
                    or "EXCLUDED",

                    job.get(
                        "location_eligibility"
                    ),

                    job.get(
                        "experience_eligibility"
                    ),

                    employer_name,
                    source_url,
                ),
            )

            excluded_updated += (
                cur.rowcount
                or 0
            )

        conn.commit()

    return {
        "eligible_updated":
            eligible_updated,

        "excluded_updated":
            excluded_updated,
    }
