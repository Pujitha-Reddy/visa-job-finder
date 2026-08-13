from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches

SEARCH_URLS = [
    "https://www.roberthalf.com/us/en/jobs/all/software-engineer?remote=Yes",
    "https://www.roberthalf.com/us/en/jobs/all/remote-software-engineer",
]

DETAIL_PATTERNS = (
    "/us/en/job/",
    "/us/en/jobs/",
)

class RobertHalfCollector(BaseCollector):
    ats_name = "ROBERT_HALF"

    def _extract_candidate_links(self, html: str, base: str) -> set[str]:
        soup = BeautifulSoup(html, "html.parser")
        out = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href") or ""
            label = a.get_text(" ", strip=True)

            if not label or not title_matches(label):
                continue

            if any(p in href for p in DETAIL_PATTERNS):
                absolute = urljoin(base, href)
                if "remote-software-engineer" not in absolute and "software-engineer?remote" not in absolute:
                    out.add(absolute)

        return out

    def _detail(self, url: str) -> dict:
        r = requests.get(url, timeout=30, headers={"User-Agent":"visa-job-finder/1.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else ""

        text = soup.get_text("\n", strip=True)
        compact = "\n".join(
            re.sub(r"\s+", " ", x).strip()
            for x in text.splitlines()
            if x.strip()
        )

        raw_type = None
        for value in (
            "Permanent / Full Time",
            "Temporary / Contract",
            "Long Term Contract",
            "Contract",
            "Permanent",
        ):
            if value.lower() in compact.lower():
                raw_type = value
                break

        location = "Remote" if re.search(r"\bremote\b", compact, re.I) else ""

        return {
            "title": title,
            "description": compact,
            "location": location,
            "raw_type": raw_type,
        }

    def fetch(self, source: dict) -> list[dict]:
        urls = set()

        for search_url in SEARCH_URLS:
            r = requests.get(
                search_url,
                timeout=30,
                headers={"User-Agent":"visa-job-finder/1.0"},
            )
            r.raise_for_status()
            urls |= self._extract_candidate_links(r.text, search_url)

        jobs = []
        for url in sorted(urls):
            try:
                detail = self._detail(url)
            except Exception:
                continue

            title = detail["title"]
            if not title_matches(title):
                continue

            jobs.append({
                "external_id": url,
                "source": "ROBERT_HALF",
                "source_url": url,
                "apply_url": url,
                "company_name_raw": source["employer_name"],
                "source_type": "STAFFING_AGENCY",
                "ats": "ROBERT_HALF",
                "title": title,
                "description": detail["description"],
                "location_raw": detail["location"] or "Needs Review",
                "posted_at": None,
                "raw_employment_type": detail["raw_type"],
                "raw_workplace_type": "remote" if detail["location"] == "Remote" else None,
                "agency_name": "Robert Half",
                "end_client": None,
            })
        return jobs
