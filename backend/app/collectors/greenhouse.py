import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches
from app.ingestion.models import CollectionResult


class GreenhouseCollector(BaseCollector):
    ats_name = "GREENHOUSE"

    def _fetch_detail(self, token: str, job_id: int | str) -> dict:
        """
        Greenhouse list jobs exposes updated_at, which is NOT a publish date.
        Retrieve the individual job so we can use first_published instead.
        """
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}"
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.json()

    def fetch(self, source):
        token = source.get("token")
        if not token:
            raise RuntimeError(
                "GREENHOUSE requires a board token."
            )

        list_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
        r = requests.get(list_url, params={"content": "true"}, timeout=30)
        r.raise_for_status()

        payload = r.json()
        raw_jobs = payload.get("jobs") or []

        jobs = []
        scanned = len(raw_jobs)

        for raw in raw_jobs:
            title = (raw.get("title") or "").strip()

            if not title_matches(title):
                continue

            loc = raw.get("location") or {}
            job_id = raw.get("id")

            first_published = None
            detail_updated_at = raw.get("updated_at")

            try:
                detail = self._fetch_detail(token, job_id)
                first_published = detail.get("first_published")
                detail_updated_at = detail.get("updated_at") or detail_updated_at
            except Exception as exc:
                # Do NOT substitute updated_at for published_at.
                # Unknown freshness is safer than falsely labeling an old job "new".
                print(
                    f"[GREENHOUSE DETAIL WARNING] "
                    f"{source.get('employer_name')} / {title}: {exc}"
                )

            jobs.append({
                "external_id": str(job_id),
                "source": "GREENHOUSE",
                "source_url": raw.get("absolute_url"),
                "apply_url": raw.get("absolute_url"),
                "company_name_raw": source["employer_name"],
                "title": title,
                "description": BeautifulSoup(
                    raw.get("content") or "",
                    "html.parser"
                ).get_text(" ", strip=True),
                "location_raw": (
                    loc.get("name")
                    if isinstance(loc, dict)
                    else str(loc or "")
                ),

                # Backward compatibility: posted_at now means actual publish time
                # for Greenhouse rather than updated_at.
                "posted_at": first_published,

                "source_published_at": first_published,
                "source_updated_at": detail_updated_at,
                "effective_posted_at": first_published,
                "freshness_confidence": (
                    "HIGH" if first_published else "UNKNOWN"
                ),
                "freshness_source": (
                    "GREENHOUSE_FIRST_PUBLISHED"
                    if first_published
                    else "UNKNOWN"
                ),

                "source_type": source.get("source_type"),
                "ats": "GREENHOUSE",
            })

        return CollectionResult(
            jobs=jobs,
            snapshot_complete=True,
            records_scanned=scanned,
            expected_total=scanned,
            pages_completed=1,
            termination_reason="FULL_BOARD_RESPONSE",
        )


def fetch_greenhouse_jobs(company: str, token: str):
    collector = GreenhouseCollector()

    source = {
        "employer_name": company,
        "source_type": "DIRECT_EMPLOYER",
        "token": token,
    }

    result = collector.fetch(source)

    if isinstance(result, CollectionResult):
        return result.jobs

    return result
