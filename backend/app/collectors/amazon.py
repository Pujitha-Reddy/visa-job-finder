from __future__ import annotations

import re
from datetime import datetime, timezone

import requests

from .base import BaseCollector
from .common import title_matches


class AmazonCollector(BaseCollector):
    ats_name = "AMAZON"

    SEARCH_URL = "https://www.amazon.jobs/en/search.json"

    @staticmethod
    def _normalize_posted_date(value):
        if not value:
            return None

        # Amazon may include non-breaking spaces.
        clean = str(value).replace("\xa0", " ").strip()
        clean = re.sub(r"\s+", " ", clean)

        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                dt = datetime.strptime(clean, fmt)
                return dt.replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass

        # If Amazon ever returns ISO, preserve it.
        try:
            dt = datetime.fromisoformat(clean.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            return None

    def fetch(self, source):
        jobs = []
        seen = set()

        max_pages = int(source.get("token") or 5)
        limit = 100

        for page in range(max_pages):
            offset = page * limit

            response = requests.get(
                self.SEARCH_URL,
                params={
                    "base_query": "software engineer",
                    "country": "USA",
                    "offset": offset,
                    "result_limit": limit,
                    "sort": "recent",
                },
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Mozilla/5.0 visa-job-finder/1.0",
                },
                timeout=30,
            )
            response.raise_for_status()

            payload = response.json()
            raw_jobs = payload.get("jobs", [])

            if not raw_jobs:
                break

            for raw in raw_jobs:
                title = (raw.get("title") or "").strip()

                if not title or not title_matches(title):
                    continue

                job_id = str(
                    raw.get("id")
                    or raw.get("job_id")
                    or raw.get("icims_id")
                    or ""
                ).strip()

                job_path = (
                    raw.get("job_path")
                    or raw.get("url")
                    or ""
                )

                if job_path.startswith("http"):
                    job_url = job_path
                elif job_path:
                    job_url = f"https://www.amazon.jobs{job_path}"
                elif job_id:
                    job_url = f"https://www.amazon.jobs/en/jobs/{job_id}"
                else:
                    continue

                if job_url in seen:
                    continue
                seen.add(job_url)

                raw_posted = (
                    raw.get("posted_date")
                    or raw.get("posted_at")
                    or raw.get("posted")
                )

                posted = self._normalize_posted_date(raw_posted)

                location = (
                    raw.get("location")
                    or raw.get("location_name")
                    or ""
                )

                description = " ".join(
                    str(raw.get(k) or "")
                    for k in (
                        "description",
                        "basic_qualifications",
                        "preferred_qualifications",
                    )
                ).strip()

                jobs.append({
                    "external_id": job_id or None,
                    "source": "AMAZON",
                    "source_url": job_url,
                    "apply_url": job_url,
                    "company_name_raw": "Amazon",
                    "title": title,
                    "description": description,
                    "location_raw": location,

                    "posted_at": posted,
                    "source_published_at": posted,
                    "source_updated_at": None,
                    "effective_posted_at": posted,

                    "freshness_confidence": (
                        "HIGH" if posted else "UNKNOWN"
                    ),
                    "freshness_source": (
                        "AMAZON_POSTED_DATE"
                        if posted
                        else "UNKNOWN"
                    ),

                    "source_type": "DIRECT_EMPLOYER",
                    "ats": "AMAZON",
                })

            total_hits = int(payload.get("hits") or 0)
            if total_hits and offset + len(raw_jobs) >= total_hits:
                break

        return jobs
