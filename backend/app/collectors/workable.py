import requests
from .base import BaseCollector
from .common import title_matches

class WorkableCollector(BaseCollector):
    ats_name = "WORKABLE"

    def fetch(self, source):
        subdomain = source.get("token")
        if not subdomain:
            return []
        url = f"https://www.workable.com/api/accounts/{subdomain}"
        r = requests.get(url, params={"details":"true"}, timeout=30)
        r.raise_for_status()
        jobs = []
        for raw in r.json().get("jobs", []):
            title = (raw.get("title") or "").strip()
            if not title_matches(title):
                continue
            location = ", ".join([x for x in [
                raw.get("city"), raw.get("state"), raw.get("country")
            ] if x])
            jobs.append({
                "external_id":str(raw.get("shortcode") or raw.get("code") or raw.get("id") or ""),
                "source":"WORKABLE",
                "source_url":raw.get("url") or raw.get("shortlink") or raw.get("application_url"),
                "apply_url":raw.get("application_url") or raw.get("url"),
                "company_name_raw":source["employer_name"],
                "source_type":source.get("source_type"),
                "ats":"WORKABLE",
                "title":title,
                "description":raw.get("description") or "",
                "location_raw":location,
                "posted_at":raw.get("published_on") or raw.get("created_at"),
                "raw_employment_type":raw.get("employment_type"),
                "raw_workplace_type":raw.get("workplace_type") or ("remote" if raw.get("telecommuting") else None),
            })
        return jobs
