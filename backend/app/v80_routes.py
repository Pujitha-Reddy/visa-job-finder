from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .postgres_repository import (
    fetch_facets,
    fetch_jobs,
    fetch_stats,
    health,
    update_application_status,
)

router = APIRouter(prefix="/v80", tags=["Postgres / Supabase"])


class StatusUpdate(BaseModel):
    status: str


@router.get("/health")
def postgres_health():
    return {"ok": True, "backend": "supabase-postgres", **health()}


@router.get("/jobs")
def postgres_jobs(
    hours: int = Query(72, ge=1, le=720),
    source_type: str | None = None,
    agency: str | None = None,
    employment_detail_type: str | None = None,
    visa_detail_status: str | None = None,
    experience_band: str | None = None,
    work_arrangement: str | None = None,
    application_status: str = "NEW",
    q: str | None = None,
    sort: str = Query("best", pattern="^(best|newest|sponsor|experience|company)$"),
):
    return fetch_jobs(
        hours=hours,
        source_type=source_type,
        agency=agency,
        employment_detail_type=employment_detail_type,
        visa_detail_status=visa_detail_status,
        experience_band=experience_band,
        work_arrangement=work_arrangement,
        application_status=application_status,
        query_text=q,
        sort=sort,
    )


@router.get("/stats")
def postgres_stats(
    hours: int = Query(72, ge=1, le=720),
    source_type: str | None = "DIRECT_EMPLOYER",
):
    return fetch_stats(hours, source_type)


@router.get("/facets")
def postgres_facets():
    return fetch_facets()


@router.patch("/jobs/{job_id}/status")
def postgres_status(job_id: int, body: StatusUpdate):
    try:
        row = update_application_status(job_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    return row
