from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches

SEARCH_URLS = [
    "https://www.randstadusa.com/jobs/q-software-engineer/remote/",
    "https://www.randstadusa.com/jobs/remote/",
]

JOB_LINK_RE = re.compile(r"/jobs/\d+/\d+/[^\"?#]+", re.I)

class RandstadCollector(BaseCollector):
    ats_name = "RANDSTAD"

    def _detail(self, url: str) -> dict:
        r = requests.get(url, timeout=30, headers={"User-Agent":"visa-job-finder/1.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else ""

        text = soup.get_text("\n", strip=True)
        lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines() if x.strip()]

        posted = None
        location = ""
        raw_type = None

        for line in lines[:80]:
            low = line.lower()
            if low.startswith("posted "):
                posted = line
            if low in {"contract","permanent","temporary"}:
                raw_type = line
            if not location and any(state in low for state in (
                "remote","alabama","alaska","arizona","arkansas","california","colorado",
                "connecticut","delaware","florida","georgia","illinois","indiana","iowa",
                "kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan",
                "minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire",
                "new jersey","new mexico","new york","north carolina","north dakota","ohio",
                "oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota",
                "tennessee","texas","utah","vermont","virginia","washington","west virginia",
                "wisconsin","wyoming"
            )):
                location = line

        reference = None
        m = re.search(r"\breference\s+(\d+)\b", text, re.I)
        if m:
            reference = m.group(1)

        return {
            "title": title,
            "description": text,
            "location": location,
            "raw_type": raw_type,
            "posted": posted,
            "reference": reference,
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

            for href in JOB_LINK_RE.findall(r.text):
                urls.add(urljoin(search_url, href))

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
                "external_id": detail["reference"] or url,
                "source": "RANDSTAD",
                "source_url": url,
                "apply_url": url,
                "company_name_raw": source["employer_name"],
                "source_type": "STAFFING_AGENCY",
                "ats": "RANDSTAD",
                "title": title,
                "description": detail["description"],
                "location_raw": detail["location"] or "Remote",
                "posted_at": None,
                "raw_employment_type": detail["raw_type"],
                "raw_workplace_type": "remote",
                "agency_name": "Randstad Digital",
                "end_client": None,
            })
        return jobs
