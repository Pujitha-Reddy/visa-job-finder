from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from .base import BaseCollector
from .common import title_matches

class SmartRecruitersCollector(BaseCollector):
    ats_name = "SMARTRECRUITERS"
    BASE = "https://api.smartrecruiters.com/v1/companies"

    def _get(self, url, params=None):
        r = requests.get(
            url, params=params, timeout=30,
            headers={"Accept":"application/json","User-Agent":"visa-job-finder/1.0"},
        )
        r.raise_for_status()
        return r.json()

    def _text(self, value):
        return BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)

    def _location(self, raw):
        loc = raw.get("location") or {}
        if isinstance(loc, str):
            return loc.strip()
        return ", ".join(str(loc.get(k)).strip() for k in ("city","region","country") if loc.get(k))

    def _published(self, raw):
        for k in ("releasedDate","releasedAt","postingDate","postedDate","publishedAt"):
            if raw.get(k):
                return str(raw[k])
        return None

    def fetch(self, source):
        token = (source.get("token") or "").strip()
        if not token:
            return []
        jobs, offset, limit = [], 0, 100

        while True:
            data = self._get(
                f"{self.BASE}/{token}/postings",
                {"offset":offset,"limit":limit,"destination":"PUBLIC"},
            )
            content = data.get("content") or []
            total = int(data.get("totalFound") or len(content))
            if not content:
                break

            for raw in content:
                title = (raw.get("name") or raw.get("title") or "").strip()
                if not title_matches(title):
                    continue

                pid = str(raw.get("id") or raw.get("uuid") or "").strip()
                detail = raw
                if pid:
                    try:
                        detail = self._get(f"{self.BASE}/{token}/postings/{pid}")
                    except Exception as exc:
                        print(f"[SMARTRECRUITERS DETAIL WARNING] {source.get('employer_name')} / {title}: {exc}")

                title = (detail.get("name") or detail.get("title") or title).strip()
                if not title_matches(title):
                    continue

                published = self._published(detail) or self._published(raw)
                location = self._location(detail) or self._location(raw)

                desc_parts = []
                for blob in (detail.get("jobAd") or {}, detail.get("sections") or {}):
                    if isinstance(blob, dict):
                        for v in blob.values():
                            if isinstance(v, str):
                                desc_parts.append(self._text(v))
                            elif isinstance(v, dict):
                                for vv in v.values():
                                    if isinstance(vv, str):
                                        desc_parts.append(self._text(vv))

                apply_url = detail.get("applyUrl") or raw.get("applyUrl")
                job_url = detail.get("jobAdUrl") or raw.get("jobAdUrl") or apply_url
                if not job_url and pid:
                    job_url = f"https://jobs.smartrecruiters.com/{token}/{pid}"
                if not job_url:
                    continue

                jobs.append({
                    "external_id": pid or None,
                    "source": "SMARTRECRUITERS",
                    "source_url": job_url,
                    "apply_url": apply_url or job_url,
                    "company_name_raw": source["employer_name"],
                    "source_type": source.get("source_type"),
                    "ats": "SMARTRECRUITERS",
                    "title": title,
                    "description": " ".join(x for x in desc_parts if x),
                    "location_raw": location,
                    "posted_at": published,
                    "source_published_at": published,
                    "source_updated_at": None,
                    "effective_posted_at": published,
                    "freshness_confidence": "HIGH" if published else "UNKNOWN",
                    "freshness_source": "SMARTRECRUITERS_RELEASED_DATE" if published else "UNKNOWN",
                })

            offset += len(content)
            if offset >= total:
                break

        return jobs
