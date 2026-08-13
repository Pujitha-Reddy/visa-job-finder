from __future__ import annotations

from .database import get_connection


FIELDS = (
    "external_id", "source", "source_url", "apply_url",
    "company_name_raw", "title", "description", "location_raw", "posted_at",
    "min_experience_years", "max_experience_years", "experience_text",
    "experience_match", "work_arrangement", "employment_type",
    "visa_language_status", "visa_evidence_text", "decision", "decision_reason"
)


def upsert_job(job: dict) -> str:
    if not job.get("source_url"):
        raise ValueError("source_url is required")

    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM jobs WHERE source_url = ?", (job["source_url"],)
        ).fetchone()

        values = [job.get(f) for f in FIELDS]

        if existing:
            assignments = ", ".join(f"{f} = ?" for f in FIELDS if f != "source_url")
            update_values = [job.get(f) for f in FIELDS if f != "source_url"]
            conn.execute(
                f"UPDATE jobs SET {assignments}, last_seen_at=CURRENT_TIMESTAMP WHERE id=?",
                update_values + [existing["id"]],
            )
            conn.commit()
            return "UPDATED"

        placeholders = ",".join("?" for _ in FIELDS)
        conn.execute(
            f"INSERT INTO jobs ({','.join(FIELDS)}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        return "ADDED"


def save_jobs(jobs: list[dict]) -> dict:
    stats = {"found": len(jobs), "added": 0, "updated": 0, "errors": 0}
    for job in jobs:
        try:
            result = upsert_job(job)
            stats[result.lower()] += 1
        except Exception as exc:
            stats["errors"] += 1
            print(f"[SAVE ERROR] {job.get('title')}: {exc}")
    return stats


def update_application_status(job_id: int, status: str) -> dict:
    allowed = {"NEW", "SAVED", "APPLIED", "INTERVIEW", "REJECTED", "SKIPPED"}
    if status not in allowed:
        raise ValueError(f"Invalid application status: {status}")

    with get_connection() as conn:
        row = conn.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise ValueError(f"Job {job_id} not found")

        if status == "APPLIED":
            conn.execute(
                "UPDATE jobs SET application_status=?, date_applied=COALESCE(date_applied, CURRENT_TIMESTAMP) WHERE id=?",
                (status, job_id),
            )
        else:
            conn.execute("UPDATE jobs SET application_status=? WHERE id=?", (status, job_id))

        conn.commit()
        return dict(conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())


def recalculate_all_scores() -> dict:
    from .scoring.overall import calculate_overall_score
    with get_connection() as conn:
        jobs = [dict(r) for r in conn.execute("SELECT * FROM jobs").fetchall()]
        for job in jobs:
            score = calculate_overall_score(job)["score"]
            conn.execute("UPDATE jobs SET overall_score=? WHERE id=?", (score, job["id"]))
        conn.commit()
    return {"jobs_scored": len(jobs)}
