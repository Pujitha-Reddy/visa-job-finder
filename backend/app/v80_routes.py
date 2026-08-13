from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from .postgres_repository import fetch_jobs, fetch_stats, fetch_facets, update_application_status, health

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
):
    return fetch_jobs(hours, source_type, agency, employment_detail_type, visa_detail_status,
                      experience_band, work_arrangement, application_status)

@router.get("/stats")
def postgres_stats(hours: int = Query(72, ge=1, le=720)):
    return fetch_stats(hours)

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
