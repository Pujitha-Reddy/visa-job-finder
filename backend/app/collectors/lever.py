from __future__ import annotations

import requests

from .common import clean_html, iso_from_millis, title_matches

BASE_URL = "https://api.lever.co/v0/postings/{site}"


def fetch_lever_jobs(
    site: str,
    company_name: str,
    timeout: int = 30,
    target_titles_only: bool = True,
) -> list[dict]:
    """
    Fetch public job postings from Lever's public Postings API.
    """
    url = BASE_URL.format(site=site)
    response = requests.get(url, params={"mode": "json"}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    jobs = []
    for raw in payload:
        title = (raw.get("text") or "").strip()
        if target_titles_only and not title_matches(title):
            continue

        categories = raw.get("categories") or {}
        description_parts = [
            raw.get("descriptionPlain") or raw.get("description"),
            raw.get("additionalPlain") or raw.get("additional"),
        ]
        description = clean_html(" ".join(part for part in description_parts if part))

        jobs.append({
            "external_id": str(raw.get("id")) if raw.get("id") is not None else None,
            "source": "LEVER",
            "source_url": raw.get("hostedUrl"),
            "apply_url": raw.get("applyUrl") or raw.get("hostedUrl"),
            "company_name_raw": company_name,
            "title": title,
            "description": description,
            "location_raw": categories.get("location") or "",
            "posted_at": iso_from_millis(raw.get("createdAt")),
            "metadata": {
                "lever_site": site,
                "team": categories.get("team"),
                "department": categories.get("department"),
                "commitment": categories.get("commitment"),
            },
        })

    return jobs
