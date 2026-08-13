from fastapi import APIRouter, Query
from .jobs_repository import _conn, init_jobs

router = APIRouter(prefix="/v78")

@router.get("/jobs")
def jobs(
    hours: int = Query(72, ge=1, le=720),
    source_type: str | None = None,
    agency: str | None = None,
    employment_detail_type: str | None = None,
    visa_detail_status: str | None = None,
    experience_band: str | None = None,
    work_arrangement: str | None = None,
    application_status: str = "NEW",
):
    init_jobs()

    clauses = ["1=1"]
    params = []

    # Some agency sources do not expose a reliable posted timestamp.
    # Only apply date filtering where posted_at exists.
    clauses.append("(posted_at IS NULL OR datetime(posted_at) >= datetime('now', ?))")
    params.append(f"-{hours} hours")

    mapping = {
        "source_type": source_type,
        "agency_name": agency,
        "employment_detail_type": employment_detail_type,
        "visa_detail_status": visa_detail_status,
        "experience_band": experience_band,
        "work_arrangement": work_arrangement,
    }

    for col, value in mapping.items():
        if value:
            clauses.append(f"{col}=?")
            params.append(value)

    if application_status != "ALL":
        clauses.append("application_status=?")
        params.append(application_status)

    with _conn() as c:
        rows = c.execute(f"""
            SELECT * FROM jobs
            WHERE {' AND '.join(clauses)}
            ORDER BY overall_score DESC, COALESCE(posted_at,last_seen_at) DESC
            LIMIT 2000
        """, params).fetchall()

    return [dict(r) for r in rows]

@router.get("/facets")
def facets():
    init_jobs()
    with _conn() as c:
        def group(column):
            return [
                dict(r) for r in c.execute(
                    f"""
                    SELECT COALESCE({column},'UNKNOWN') AS value, COUNT(*) AS count
                    FROM jobs
                    GROUP BY COALESCE({column},'UNKNOWN')
                    ORDER BY count DESC
                    """
                ).fetchall()
            ]

        return {
            "source_type": group("source_type"),
            "agency": group("agency_name"),
            "employment_detail_type": group("employment_detail_type"),
            "visa_detail_status": group("visa_detail_status"),
            "experience_band": group("experience_band"),
            "work_arrangement": group("work_arrangement"),
        }
