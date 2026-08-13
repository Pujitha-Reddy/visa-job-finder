from fastapi import APIRouter, HTTPException
from .jobs_repository import _conn, init_jobs
from .sponsorship.normalization import normalize_company_name

router = APIRouter(prefix="/v79")

@router.get("/jobs/{job_id}/sponsor-debug")
def sponsor_debug(job_id: int):
    init_jobs()
    with _conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    job = dict(row)
    entity = job.get("agency_name") or job.get("company_name_raw")
    return {
        "company": job.get("company_name_raw"),
        "agency_name": job.get("agency_name"),
        "sponsor_entity_used": entity,
        "normalized_sponsor_entity": normalize_company_name(entity),
        "h1b_history_strength": job.get("h1b_history_strength"),
        "sponsorship_score": job.get("sponsorship_score"),
        "visa_language_status": job.get("visa_language_status"),
        "visa_detail_status": job.get("visa_detail_status"),
        "note": "Historical H-1B evidence does not guarantee sponsorship for this posting."
    }
