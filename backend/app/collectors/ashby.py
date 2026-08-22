import requests
from .base import BaseCollector
from .common import title_matches
from app.ingestion.models import CollectionResult

class AshbyCollector(BaseCollector):
    ats_name = "ASHBY"

    def fetch(self, source):
        board = source.get("token")
        if not board:
            raise RuntimeError(
                "ASHBY requires a board token."
            )
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
        r = requests.get(url, params={"includeCompensation":"true"}, timeout=30)
        r.raise_for_status()
        payload = r.json()
        raw_jobs = payload.get("jobs") or []

        jobs = []
        scanned = len(raw_jobs)

        for raw in raw_jobs:
            if not raw.get("isListed", True):
                continue
            title = (raw.get("title") or "").strip()
            if not title_matches(title):
                continue
            desc = raw.get("descriptionPlain") or raw.get("descriptionHtml") or raw.get("description") or ""
            jobs.append({
                "external_id": str(raw.get("id") or raw.get("jobUrl") or ""),
                "source":"ASHBY",
                "source_url":raw.get("jobUrl"),
                "apply_url":raw.get("applyUrl") or raw.get("jobUrl"),
                "company_name_raw":source["employer_name"],
                "source_type":source.get("source_type"),
                "ats":"ASHBY",
                "title":title,
                "description":desc,
                "location_raw":raw.get("location") or "",
                "posted_at":raw.get("publishedAt") or raw.get("createdAt"),
                "raw_employment_type":raw.get("employmentType"),
                "raw_workplace_type":raw.get("workplaceType"),
            })
        return CollectionResult(
            jobs=jobs,
            snapshot_complete=True,
            records_scanned=scanned,
            expected_total=scanned,
            pages_completed=1,
            termination_reason="FULL_BOARD_RESPONSE",
        )
