from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import requests

from .base import BaseCollector
from .common import title_matches


BASE = "https://jobs.insightglobal.com/jobs/find_a_job/{page}/?miles=False&remote=true&srch=Software+Engineer"


def _dotnet_date_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    m = re.search(r"/Date\((\d+)\)/", value)
    if not m:
        return None
    return datetime.fromtimestamp(int(m.group(1)) / 1000, tz=timezone.utc).isoformat()


def _extract_embedded_jobs(html: str) -> list[dict]:
    """
    Parse complete JSON objects beginning at every {"JobID": occurrence using
    JSONDecoder.raw_decode. This safely handles nested Location objects and
    long Description fields.
    """
    decoder = json.JSONDecoder()
    jobs = []
    seen = set()
    pos = 0

    while True:
        start = html.find('{"JobID":', pos)
        if start < 0:
            break

        try:
            obj, consumed = decoder.raw_decode(html[start:])
        except json.JSONDecodeError:
            pos = start + 9
            continue

        pos = start + consumed

        if not isinstance(obj, dict):
            continue

        job_id = obj.get("JobID")
        if not job_id or job_id in seen:
            continue

        # Strong sanity check for the public Insight Global job payload.
        if not obj.get("Title") or "PostedDate" not in obj or "Description" not in obj:
            continue

        seen.add(job_id)
        jobs.append(obj)

    return jobs


class InsightGlobalCollector(BaseCollector):
    ats_name = "INSIGHT_GLOBAL"

    def fetch(self, source: dict) -> list[dict]:
        max_pages = int(source.get("max_pages") or 12)
        jobs = []
        seen = set()

        for page in range(1, max_pages + 1):
            url = BASE.format(page=page)
            r = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "visa-job-finder/1.0"},
            )
            r.raise_for_status()

            page_jobs = _extract_embedded_jobs(r.text)
            if not page_jobs and page > 1:
                break

            for data in page_jobs:
                job_id = data.get("JobID")
                if job_id in seen:
                    continue

                title = (data.get("Title") or "").strip()
                if not title_matches(title):
                    continue

                seen.add(job_id)

                job_types = data.get("JobType") or []
                if isinstance(job_types, str):
                    job_types = [job_types]

                city = data.get("City") or ""
                state = data.get("State") or ""
                zipcode = data.get("Zip") or ""
                location_text = ", ".join(
                    x for x in [city, state, zipcode] if x
                ) or "Remote"

                # Use the public search URL anchored by the unique job ID rather
                # than inventing an undocumented detail-route format.
                job_url = (
                    "https://jobs.insightglobal.com/jobs/find_a_job/"
                    f"?miles=False&remote=true&srch={job_id}"
                )

                jobs.append({
                    "external_id": str(job_id),
                    "source": "INSIGHT_GLOBAL",
                    "source_url": job_url,
                    "apply_url": job_url,
                    "company_name_raw": source["employer_name"],
                    "source_type": "STAFFING_AGENCY",
                    "ats": "INSIGHT_GLOBAL",
                    "title": title,
                    "description": " ".join(
                        x for x in [
                            data.get("Description") or "",
                            data.get("Requirements") or "",
                            data.get("Skills") or "",
                        ] if x
                    ),
                    "location_raw": location_text,
                    "posted_at": _dotnet_date_to_iso(data.get("PostedDate")),
                    "raw_employment_type": " ".join(job_types),
                    "raw_workplace_type": (
                        "remote"
                        if data.get("IsRemoteJob") or data.get("IsRemote")
                        else None
                    ),
                    "agency_name": "Insight Global",
                    "end_client": data.get("EndClient"),
                })

        return jobs
