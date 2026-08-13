import requests
from .base import BaseCollector
from .common import title_matches

class AshbyCollector(BaseCollector):
    ats_name = "ASHBY"

    def fetch(self, source):
        board = source.get("token")
        if not board:
            return []
        url = f"https://api.ashbyhq.com/posting-api/job-board/{board}"
        r = requests.get(url, params={"includeCompensation":"true"}, timeout=30)
        r.raise_for_status()
        jobs = []
        for raw in r.json().get("jobs", []):
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
        return jobs
