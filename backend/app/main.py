from .v80_routes import router as v80_router
from fastapi import FastAPI, Query, HTTPException
from .v78_routes import router as v78_router
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import os

from .database import get_connection, init_db
from .collect import collect_all
from .sponsorship.repository import sponsor_profile
from .sponsorship.enrich import enrich_all_jobs
from .repository import update_application_status, recalculate_all_scores
from .scoring.overall import calculate_overall_score

from .v110_routes import router as v110_router
from .v113_routes import router as v113_router
app = FastAPI(
    title="Visa Job Finder API",
    version="0.1.0",
    description="API for filtered software-engineering jobs with sponsorship and F-1 review signals.",
)

app.include_router(v80_router)

app.include_router(v78_router)
app.include_router(v110_router)
app.include_router(v113_router)


cors_origins = [
    x.strip()
    for x in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if x.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/jobs")
def list_jobs(
    hours: int = Query(default=24, enum=[24, 72]),
    work_arrangement: Optional[str] = None,
    employment_type: Optional[str] = None,
    visa_status: Optional[str] = None,
    decision: Optional[str] = None,
    application_status: str = "NEW",
    min_score: float = 0,
):
    clauses = [
        "COALESCE(is_active, 1) = 1",
        "COALESCE(is_eligible, 1) = 1",
        "overall_score >= ?",
        "datetime(posted_at) >= datetime('now', ?)"
    ]
    params = [
        min_score,
        f"-{hours} hours",
    ]

    if application_status != "ALL":
        clauses.append("application_status = ?")
        params.append(application_status)

    if work_arrangement:
        clauses.append("work_arrangement = ?")
        params.append(work_arrangement)

    if employment_type:
        clauses.append("employment_type = ?")
        params.append(employment_type)

    if visa_status:
        clauses.append("visa_language_status = ?")
        params.append(visa_status)

    if decision:
        clauses.append("decision = ?")
        params.append(decision)

    sql = f"""
        SELECT *
        FROM jobs
        WHERE {' AND '.join(clauses)}
        ORDER BY overall_score DESC, posted_at DESC
        LIMIT 500
    """

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    return [dict(row) for row in rows]


@app.get("/stats")
def stats(hours: int = Query(default=24, enum=[24, 72])):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN work_arrangement='REMOTE' THEN 1 ELSE 0 END) AS remote,
                SUM(CASE WHEN work_arrangement='HYBRID' THEN 1 ELSE 0 END) AS hybrid,
                SUM(CASE WHEN work_arrangement='ONSITE' THEN 1 ELSE 0 END) AS onsite,
                SUM(CASE WHEN decision='APPLY' THEN 1 ELSE 0 END) AS apply_count,
                SUM(CASE WHEN decision='OK_TO_APPLY' THEN 1 ELSE 0 END) AS ok_to_apply_count,
                SUM(CASE WHEN decision='NEEDS_REVIEW' THEN 1 ELSE 0 END) AS review_count,
                SUM(CASE WHEN decision='SKIP' THEN 1 ELSE 0 END) AS skip_count
            FROM jobs
            WHERE COALESCE(is_active, 1) = 1
              AND COALESCE(is_eligible, 1) = 1
              AND datetime(posted_at) >= datetime('now', ?)
            """,
            (f"-{hours} hours",),
        ).fetchone()

    return dict(row)


@app.get("/jobs/{job_id}")
def get_job(job_id: int):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()

    if not row:
        return {"error": "Job not found"}

    return dict(row)


@app.post("/collect")
def run_collection():
    return collect_all(target_titles_only=True)


@app.get("/sponsors/{company_name}")
def get_sponsor_profile(company_name: str):
    return sponsor_profile(company_name)


@app.post("/sponsors/enrich")
def run_sponsor_enrichment():
    return enrich_all_jobs()


class StatusUpdate(BaseModel):
    status: str


@app.patch("/jobs/{job_id}/status")
def set_job_status(job_id: int, payload: StatusUpdate):
    try:
        return update_application_status(job_id, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/scores/recalculate")
def recalculate_scores():
    return recalculate_all_scores()


@app.get("/jobs/{job_id}/debug")
def debug_job(job_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    return {"job": job, "score_breakdown": calculate_overall_score(job)}
