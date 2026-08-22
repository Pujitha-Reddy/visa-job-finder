from __future__ import annotations

import requests
from bs4 import BeautifulSoup
from .base import BaseCollector
from .common import title_matches
from app.ingestion.models import CollectionResult

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
            raise RuntimeError(
                "SMARTRECRUITERS requires a company token."
            )

        jobs = []
        offset = 0
        limit = 100

        scanned = 0
        pages = 0
        expected_total = None
        termination_reason = None

        seen_page_signatures = set()

        while True:
            data = self._get(
                f"{self.BASE}/{token}/postings",
                {"offset":offset,"limit":limit,"destination":"PUBLIC"},
            )
            content = data.get("content") or []
            pages += 1

            reported_total = data.get("totalFound")

            if expected_total is None:
                try:
                    parsed_total = int(
                        reported_total
                    )
                except (TypeError, ValueError):
                    parsed_total = 0

                if parsed_total > 0:
                    expected_total = parsed_total

            if not content:
                termination_reason = "EMPTY_PAGE"
                break

            page_signature = tuple(
                str(
                    raw.get("id")
                    or raw.get("uuid")
                    or raw.get("jobAdUrl")
                    or ""
                )
                for raw in content
            )

            if (
                page_signature
                and page_signature
                in seen_page_signatures
            ):
                termination_reason = "REPEATED_PAGE"

                print(
                    f"[SMARTRECRUITERS PARTIAL] "
                    f"{source.get('employer_name')} "
                    f"| repeated page at offset={offset}"
                )

                break

            seen_page_signatures.add(
                page_signature
            )

            scanned += len(content)

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

            if len(content) < limit:
                termination_reason = "SHORT_FINAL_PAGE"
                break

            if (
                expected_total is not None
                and offset >= expected_total
            ):
                termination_reason = (
                    "EXPECTED_TOTAL_REACHED"
                )
                break

        snapshot_complete = (
            termination_reason
            in {
                "EMPTY_PAGE",
                "SHORT_FINAL_PAGE",
                "EXPECTED_TOTAL_REACHED",
            }
        )

        return CollectionResult(
            jobs=jobs,
            snapshot_complete=snapshot_complete,
            records_scanned=scanned,
            expected_total=expected_total,
            pages_completed=pages,
            termination_reason=termination_reason,
        )
