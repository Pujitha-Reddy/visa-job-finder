from __future__ import annotations

from ..database import get_connection
from .repository import sponsor_profile
from .scoring import combine_job_and_sponsor


def enrich_job_sponsorship(job_id: int) -> dict:
    with get_connection() as conn:
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not job:
            raise ValueError(f"Job {job_id} not found")

    job = dict(job)
    profile = sponsor_profile(job["company_name_raw"])
    combined = combine_job_and_sponsor(
        visa_language_status=job["visa_language_status"],
        sponsor_strength=profile["strength"],
        sponsor_score=profile["score"],
    )

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET h1b_history_strength = ?,
                sponsorship_score = ?,
                decision_reason = CASE
                    WHEN visa_language_status IN ('NOT_MENTIONED','UNKNOWN')
                    THEN ?
                    ELSE decision_reason
                END
            WHERE id = ?
            """,
            (
                profile["strength"],
                combined["sponsorship_score"],
                combined["reason"],
                job_id,
            ),
        )
        conn.commit()

    return {
        "job_id": job_id,
        "company": job["company_name_raw"],
        "sponsor_profile": profile,
        "combined": combined,
    }


def enrich_all_jobs() -> dict:
    with get_connection() as conn:
        ids = [r["id"] for r in conn.execute("SELECT id FROM jobs").fetchall()]

    errors = 0
    for job_id in ids:
        try:
            enrich_job_sponsorship(job_id)
        except Exception:
            errors += 1

    return {"jobs_processed": len(ids), "errors": errors}
