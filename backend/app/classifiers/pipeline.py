from .experience import classify_experience
from .employment import classify_employment
from .visa import classify_visa
from .location import classify_work_arrangement

def analyze_job(job: dict) -> dict:
    exp = classify_experience(job.get("description") or "")
    emp = classify_employment(
        job.get("title") or "",
        job.get("description") or "",
        job.get("raw_employment_type")
    )
    visa = classify_visa(job.get("description") or "")
    work = classify_work_arrangement(
        job.get("location_raw") or "",
        job.get("description") or "",
        job.get("raw_workplace_type")
    )

    if visa["status"] in {"NO_SPONSORSHIP","RESTRICTED"}:
        decision = "SKIP"
    elif work["value"] == "REMOTE":
        decision = "APPLY" if visa["status"] in {"SPONSORSHIP_AVAILABLE","F1_OPT_COMPATIBLE_SIGNAL"} else "NEEDS_REVIEW"
    elif work["value"] == "HYBRID":
        decision = "OK_TO_APPLY" if visa["status"] not in {"NOT_MENTIONED"} else "NEEDS_REVIEW"
    else:
        decision = "NEEDS_REVIEW"

    return {
        **job,
        "min_experience_years": exp["min_years"],
        "max_experience_years": exp["max_years"],
        "experience_text": exp["evidence"],
        "experience_match": exp["match"],
        "experience_band": exp["band"],
        "employment_type": (
            "CONTRACT_UNKNOWN"
            if emp["value"] == "CONTRACT_TO_HIRE"
            else emp["value"]
        ),
        "employment_detail_type": emp["value"],
        "visa_language_status": (
            "OPT_F1_MENTIONED"
            if visa["status"] == "F1_OPT_COMPATIBLE_SIGNAL"
            else "NOT_MENTIONED"
            if visa["status"] == "WORK_AUTHORIZATION_MENTIONED"
            else visa["status"]
        ),
        "visa_detail_status": visa["status"],
        "visa_evidence_text": visa["evidence"],
        "work_arrangement": work["value"],
        "decision": decision,
        "decision_reason": visa["reason"],
    }
