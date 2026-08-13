import requests
from bs4 import BeautifulSoup
from .base import BaseCollector
from .common import title_matches

class GreenhouseCollector(BaseCollector):
    ats_name = "GREENHOUSE"

    def fetch(self, source):
        token = source.get("token")
        if not token:
            return []
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        r = requests.get(url, params={"content": "true"}, timeout=30)
        r.raise_for_status()
        jobs = []
        for raw in r.json().get("jobs", []):
            title = (raw.get("title") or "").strip()
            if not title_matches(title):
                continue
            loc = raw.get("location") or {}
            jobs.append({
                "external_id": str(raw.get("id")),
                "source": "GREENHOUSE",
                "source_url": raw.get("absolute_url"),
                "apply_url": raw.get("absolute_url"),
                "company_name_raw": source["employer_name"],
                "title": title,
                "description": BeautifulSoup(raw.get("content") or "", "html.parser").get_text(" ", strip=True),
                "location_raw": loc.get("name") if isinstance(loc, dict) else str(loc or ""),
                "posted_at": raw.get("updated_at"),
                "source_type": source.get("source_type"),
                "ats": "GREENHOUSE"
            })
        return jobs
def fetch_greenhouse_jobs(company: str, token: str):
    collector = GreenhouseCollector()

    source = {
        "employer_name": company,
        "source_type": "DIRECT_EMPLOYER",
        "token": token,
    }

    return collector.fetch(source)
