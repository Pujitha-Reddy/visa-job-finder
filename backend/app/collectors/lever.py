import requests
from bs4 import BeautifulSoup
from .base import BaseCollector
from .common import title_matches
from app.ingestion.models import CollectionResult

class LeverCollector(BaseCollector):
    ats_name = "LEVER"

    def fetch(self, source):
        token = source.get("token")
        if not token:
            raise RuntimeError(
                "LEVER requires a company token."
            )
        r = requests.get(f"https://api.lever.co/v0/postings/{token}", params={"mode":"json"}, timeout=30)
        r.raise_for_status()

        raw_jobs = r.json()
        jobs = []
        scanned = len(raw_jobs)

        for raw in raw_jobs:
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
        return CollectionResult(
            jobs=jobs,
            snapshot_complete=True,
            records_scanned=scanned,
            expected_total=scanned,
            pages_completed=1,
            termination_reason="FULL_POSTINGS_RESPONSE",
        )
def fetch_lever_jobs(company: str, token: str):
    collector = LeverCollector()

    source = {
        "employer_name": company,
        "source_type": "DIRECT_EMPLOYER",
        "token": token,
    }

    result = collector.fetch(source)

    if isinstance(result, CollectionResult):
        return result.jobs

    return result
