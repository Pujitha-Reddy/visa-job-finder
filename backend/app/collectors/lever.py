import requests
from bs4 import BeautifulSoup
from .base import BaseCollector
from .common import title_matches

class LeverCollector(BaseCollector):
    ats_name = "LEVER"

    def fetch(self, source):
        token = source.get("token")
        if not token:
            return []
        r = requests.get(f"https://api.lever.co/v0/postings/{token}", params={"mode":"json"}, timeout=30)
        r.raise_for_status()
        jobs = []
        for raw in r.json():
            title = (raw.get("text") or "").strip()
            if not title_matches(title):
                continue
            cats = raw.get("categories") or {}
            desc = " ".join(filter(None, [
                raw.get("descriptionPlain") or raw.get("description"),
                raw.get("additionalPlain") or raw.get("additional")
            ]))
            jobs.append({
                "external_id": str(raw.get("id")),
                "source": "LEVER",
                "source_url": raw.get("hostedUrl"),
                "apply_url": raw.get("applyUrl") or raw.get("hostedUrl"),
                "company_name_raw": source["employer_name"],
                "title": title,
                "description": BeautifulSoup(desc, "html.parser").get_text(" ", strip=True),
                "location_raw": cats.get("location") or "",
                "posted_at": None,
                "source_type": source.get("source_type"),
                "ats": "LEVER"
            })
        return jobs
def fetch_lever_jobs(company: str, token: str):
    collector = LeverCollector()

    source = {
        "employer_name": company,
        "source_type": "DIRECT_EMPLOYER",
        "token": token,
    }

    return collector.fetch(source)
