from __future__ import annotations

from .experience import parse_experience
from .location import classify_work_arrangement
from .employment import classify_employment
from .visa import analyze_visa_language
from ..decision_rules import decide_job


def analyze_job(job: dict) -> dict:
    description = job.get("description") or ""
    location = job.get("location_raw") or ""
    title = job.get("title") or ""

    exp = parse_experience(description)
    work = classify_work_arrangement(location, description)
    employment = classify_employment(title, description, job.get("metadata"))
    visa = analyze_visa_language(description)

    decision, reason = decide_job(
        work_arrangement=work["value"],
        visa_language_status=visa["status"],
        experience_match=exp["match"],
    )

    return {
        **job,
        "min_experience_years": exp["min_years"],
        "max_experience_years": exp["max_years"],
        "experience_text": exp["text"],
        "experience_match": exp["match"],
        "work_arrangement": work["value"],
        "employment_type": employment["value"],
        "visa_language_status": visa["status"],
        "visa_evidence_text": visa["evidence"],
        "decision": decision,
        "decision_reason": reason,
        "analysis": {
            "experience": exp,
            "work_arrangement": work,
            "employment": employment,
            "visa": visa,
        },
    }
