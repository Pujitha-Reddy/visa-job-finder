from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from .base import BaseCollector
from .common import title_matches

class WorkdayCollector(BaseCollector):
    ats_name = "WORKDAY"

    @staticmethod
    def _site_parts(careers_url: str):
        p = urlparse(careers_url or "")
        host = p.netloc
        site = p.path.strip("/").split("/")[0] if p.path.strip("/") else ""
        if not host or "myworkdayjobs.com" not in host or not site:
            raise RuntimeError("WORKDAY requires a verified myworkdayjobs.com careers_url.")
        tenant = host.split(".")[0]
        return p.scheme or "https", host, tenant, site

    @staticmethod
    def _text(v):
        return BeautifulSoup(str(v or ""), "html.parser").get_text(" ", strip=True)

    @staticmethod
    def _parse_source_date(value):
        if not value:
            return None, "UNKNOWN", "UNKNOWN"
        raw = str(value).strip()
        low = raw.lower()
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat(), "HIGH", "WORKDAY_SOURCE_DATE"
        except Exception:
            pass
        for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
                return dt.isoformat(), "HIGH", "WORKDAY_SOURCE_DATE"
            except ValueError:
                pass
        now = datetime.now(timezone.utc)
        if "posted today" in low or low == "today":
            dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return dt.isoformat(), "MEDIUM", "WORKDAY_RELATIVE_POSTED_DATE"
        if "posted yesterday" in low or low == "yesterday":
            dt = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            return dt.isoformat(), "MEDIUM", "WORKDAY_RELATIVE_POSTED_DATE"
        # Workday commonly emits "Posted 30+ Days Ago".
        m = re.search(r"(\d+)\+\s*days?\s+ago", low)
        if m:
            dt = (
                now - timedelta(days=int(m.group(1)))
            ).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            return (
                dt.isoformat(),
                "MEDIUM",
                "WORKDAY_RELATIVE_POSTED_DATE",
            )

        m = re.search(r"(\d+)\s+days?\s+ago", low)
        if m:
            dt = (
                now - timedelta(days=int(m.group(1)))
            ).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            return (
                dt.isoformat(),
                "MEDIUM",
                "WORKDAY_RELATIVE_POSTED_DATE",
            )

        return None, "UNKNOWN", "UNKNOWN"

    def _request_json(self, method, url, **kwargs):
        r = requests.request(method, url, timeout=30, headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "visa-job-finder/1.0",
        }, **kwargs)
        r.raise_for_status()
        return r.json()

    def fetch(self, source):
        careers_url = source.get("careers_url")
        if not careers_url:
            return []
        scheme, host, tenant, site = self._site_parts(careers_url)
        origin = f"{scheme}://{host}"
        search_url = f"{origin}/wday/cxs/{tenant}/{site}/jobs"
        limit, offset, jobs = 20, 0, []
        while True:
            payload = self._request_json("POST", search_url, json={
                "appliedFacets": {}, "limit": limit, "offset": offset,
                "searchText": "software engineer",
            })
            postings = payload.get("jobPostings") or []
            total = int(payload.get("total") or len(postings))
            if not postings:
                break
            for raw in postings:
                title = (raw.get("title") or "").strip()
                if not title_matches(title):
                    continue
                external_path = raw.get("externalPath") or ""
                if not external_path:
                    continue
                public_url = urljoin(careers_url.rstrip("/") + "/", external_path.lstrip("/"))
                detail_url = f"{origin}/wday/cxs/{tenant}/{site}{external_path}"
                detail = {}
                try:
                    detail = self._request_json("GET", detail_url)
                except Exception as exc:
                    print(f"[WORKDAY DETAIL WARNING] {source.get('employer_name')} / {title}: {exc}")
                info = detail.get("jobPostingInfo") or detail or {}
                raw_date = info.get("startDate") or info.get("postedOn") or raw.get("postedOn")
                published, confidence, freshness_source = self._parse_source_date(raw_date)
                location = info.get("location") or info.get("locationsText") or raw.get("locationsText") or ""
                description = self._text(info.get("jobDescription") or info.get("description") or "")
                bullet = raw.get("bulletFields") or []
                external_id = str(info.get("jobReqId") or info.get("jobRequisitionId") or (bullet[0] if bullet else external_path))
                jobs.append({
                    "external_id": external_id,
                    "source": "WORKDAY",
                    "source_url": public_url,
                    "apply_url": public_url,
                    "company_name_raw": source["employer_name"],
                    "source_type": source.get("source_type"),
                    "ats": "WORKDAY",
                    "title": title,
                    "description": description,
                    "location_raw": location,
                    "posted_at": published,
                    "source_published_at": published,
                    "source_updated_at": None,
                    "effective_posted_at": published,
                    "freshness_confidence": confidence,
                    "freshness_source": freshness_source,
                })
            offset += len(postings)
            if offset >= total:
                break
        return jobs
