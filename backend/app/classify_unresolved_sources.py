from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from .registry.repository import conn


ATS_SIGNATURES = [
    ("GREENHOUSE", (
        "boards.greenhouse.io",
        "boards-api.greenhouse.io",
        "greenhouse.io",
    )),
    ("LEVER", (
        "jobs.lever.co",
        "api.lever.co",
        "lever.co",
    )),
    ("ASHBY", (
        "jobs.ashbyhq.com",
        "api.ashbyhq.com",
        "ashbyhq.com",
    )),
    ("SMARTRECRUITERS", (
        "jobs.smartrecruiters.com",
        "api.smartrecruiters.com",
        "smartrecruiters.com",
    )),
    ("WORKABLE", (
        "apply.workable.com",
        "workable.com",
    )),
    ("WORKDAY", (
        "myworkdayjobs.com",
        "wd1.myworkdayjobs.com",
        "wd5.myworkdayjobs.com",
    )),
    ("EIGHTFOLD", (
        "eightfold.ai",
    )),
    ("ORACLE_HCM", (
        "oraclecloud.com/hcmui/candidateexperience",
        "hcmrestapi/resources",
    )),
]


STATE_MARKERS = (
    "__next_data__",
    "__initial_state__",
    "__apollo_state__",
    "window.__data__",
    "window.__initial",
    "jobdetails",
    "jobsdata",
    "searchresults",
    "hydration",
    "preloadedstate",
)


API_MARKERS = (
    "/api/",
    "/api/v1/",
    "graphql",
    "jobdetails",
    "searchresults",
    "requisition",
    "positions",
)


JOB_LINK_PATTERNS = (
    "/jobs/",
    "/job/",
    "/details/",
    "/positions/",
    "/careers/job",
    "/job-search/",
)


def classify_ats(text: str) -> str | None:
    low = text.lower()

    for ats, signatures in ATS_SIGNATURES:
        if any(sig in low for sig in signatures):
            return ats

    return None


def detect_strategy(html: str, final_url: str) -> dict:
    low = html.lower()

    ats = classify_ats(final_url + "\n" + html)

    if ats:
        return {
            "classification": "KNOWN_ATS",
            "detected_ats": ats,
        }

    has_embedded_state = any(
        marker in low
        for marker in STATE_MARKERS
    )

    has_api_signal = any(
        marker in low
        for marker in API_MARKERS
    )

    has_job_links = any(
        pattern in low
        for pattern in JOB_LINK_PATTERNS
    )

    if has_embedded_state and has_api_signal:
        classification = "HYBRID_EMBEDDED_STATE"
    elif has_api_signal:
        classification = "HYBRID_JSON_API"
    elif has_job_links:
        classification = "HYBRID_HTML"
    else:
        classification = "BROWSER_REQUIRED"

    return {
        "classification": classification,
        "detected_ats": None,
    }


def probe_source(name: str, url: str | None) -> dict:
    if not url:
        return {
            "company": name,
            "classification": "NO_CAREERS_URL",
            "detected_ats": None,
            "status": None,
            "final_url": None,
            "size": 0,
            "notes": "Employer has no careers_url.",
        }

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })

    try:
        r = session.get(
            url,
            timeout=25,
            allow_redirects=True,
        )
    except Exception as exc:
        return {
            "company": name,
            "classification": "UNREACHABLE",
            "detected_ats": None,
            "status": None,
            "final_url": None,
            "size": 0,
            "notes": str(exc),
        }

    final_url = r.url
    status = r.status_code
    html = r.text or ""

    if status in {404, 410}:
        return {
            "company": name,
            "classification": "STALE_URL",
            "detected_ats": None,
            "status": status,
            "final_url": final_url,
            "size": len(html),
            "notes": "Careers URL returned not found/gone.",
        }

    if status in {401, 403, 429, 436}:
        return {
            "company": name,
            "classification": "BROWSER_REQUIRED",
            "detected_ats": classify_ats(final_url + "\n" + html),
            "status": status,
            "final_url": final_url,
            "size": len(html),
            "notes": f"Protected response HTTP {status}.",
        }

    if status >= 500:
        return {
            "company": name,
            "classification": "TEMPORARY_ERROR",
            "detected_ats": None,
            "status": status,
            "final_url": final_url,
            "size": len(html),
            "notes": f"Server error HTTP {status}.",
        }

    detected = detect_strategy(
        html=html,
        final_url=final_url,
    )

    return {
        "company": name,
        "classification": detected["classification"],
        "detected_ats": detected["detected_ats"],
        "status": status,
        "final_url": final_url,
        "size": len(html),
        "notes": "",
    }


def main():
    with conn() as c:
        rows = c.execute("""
            SELECT
                e.id,
                e.display_name,
                e.source_type,
                e.careers_url
            FROM employers e
            WHERE e.enabled=1
              AND NOT EXISTS (
                  SELECT 1
                  FROM employer_sources es
                  WHERE es.employer_id=e.id
                    AND es.enabled=1
              )
            ORDER BY
                CASE e.source_type
                    WHEN 'DIRECT_EMPLOYER' THEN 1
                    WHEN 'STARTUP' THEN 2
                    WHEN 'CONSULTING' THEN 3
                    WHEN 'STAFFING_AGENCY' THEN 4
                    ELSE 5
                END,
                e.display_name
        """).fetchall()

    print("UNRESOLVED EMPLOYERS:", len(rows))
    print()

    counts = {}

    for row in rows:
        d = dict(row)

        result = probe_source(
            d["display_name"],
            d["careers_url"],
        )

        cls = result["classification"]
        counts[cls] = counts.get(cls, 0) + 1

        print("=" * 100)
        print("COMPANY:", d["display_name"])
        print("SOURCE TYPE:", d["source_type"])
        print("ORIGINAL URL:", d["careers_url"])
        print("STATUS:", result["status"])
        print("FINAL URL:", result["final_url"])
        print("SIZE:", result["size"])
        print("CLASSIFICATION:", result["classification"])
        print("DETECTED ATS:", result["detected_ats"])
        print("NOTES:", result["notes"])

    print()
    print("=== SUMMARY ===")

    for key in sorted(counts):
        print(key, counts[key])


if __name__ == "__main__":
    main()
