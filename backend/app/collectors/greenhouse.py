from __future__ import annotations

import requests

from .common import clean_html, iso_from_string, title_matches

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"


def fetch_greenhouse_jobs(
    board_token: str,
    company_name: str,
    timeout: int = 30,
    target_titles_only: bool = True,
) -> list[dict]:
    """
    Fetch public jobs from a Greenhouse board.

    Greenhouse exposes published jobs through its public Job Board API.
    `content=true` asks for job-description content when available.
    """
    url = BASE_URL.format(board_token=board_token)
    response = requests.get(url, params={"content": "true"}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()

    jobs = []
    for raw in payload.get("jobs", []):
        title = (raw.get("title") or "").strip()
        if target_titles_only and not title_matches(title):
            continue

        location = raw.get("location") or {}
        offices = raw.get("offices") or []
        departments = raw.get("departments") or []

        jobs.append({
            "external_id": str(raw.get("id")) if raw.get("id") is not None else None,
            "source": "GREENHOUSE",
            "source_url": raw.get("absolute_url"),
            "apply_url": raw.get("absolute_url"),
            "company_name_raw": company_name,
            "title": title,
            "description": clean_html(raw.get("content")),
            "location_raw": location.get("name") if isinstance(location, dict) else str(location or ""),
            "posted_at": iso_from_string(raw.get("updated_at")),
            "metadata": {
                "greenhouse_board_token": board_token,
                "offices": [o.get("name") for o in offices if isinstance(o, dict)],
                "departments": [d.get("name") for d in departments if isinstance(d, dict)],
            },
        })

    return jobs
