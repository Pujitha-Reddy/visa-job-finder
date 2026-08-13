from __future__ import annotations

from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches

class CustomHTMLCollector(BaseCollector):
    ats_name = "CUSTOM_HTML"

    def fetch(self, source: dict) -> list[dict]:
        url = source.get("careers_url")
        if not url:
            return []

        selectors = source.get("selectors") or {}
        card_sel = selectors.get("card")
        title_sel = selectors.get("title")
        link_sel = selectors.get("link")
        location_sel = selectors.get("location")
        description_sel = selectors.get("description")

        if not card_sel or not title_sel or not link_sel:
            raise RuntimeError("CUSTOM_HTML requires card/title/link selectors.")

        r = requests.get(url, timeout=30, headers={"User-Agent":"visa-job-finder/1.0"})
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        jobs = []

        for card in soup.select(card_sel):
            title_node = card.select_one(title_sel)
            link_node = card.select_one(link_sel)
            if not title_node or not link_node:
                continue

            title = title_node.get_text(" ", strip=True)
            if not title_matches(title):
                continue

            href = link_node.get("href")
            job_url = urljoin(url, href) if href else url
            loc_node = card.select_one(location_sel) if location_sel else None
            desc_node = card.select_one(description_sel) if description_sel else None

            jobs.append({
                "external_id": job_url,
                "source": source.get("ats") or "CUSTOM_HTML",
                "source_url": job_url,
                "apply_url": job_url,
                "company_name_raw": source["employer_name"],
                "source_type": source.get("source_type"),
                "ats": source.get("ats") or "CUSTOM_HTML",
                "title": title,
                "description": desc_node.get_text(" ", strip=True) if desc_node else "",
                "location_raw": loc_node.get_text(" ", strip=True) if loc_node else "",
                "posted_at": None,
            })
        return jobs
