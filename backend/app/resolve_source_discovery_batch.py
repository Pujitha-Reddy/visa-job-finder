from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from app.database import get_connection


BATCH_NAME = "SPONSOR_EXPANSION_V1"


OFFICIAL_CAREERS = {
    "Intel": "https://www.intel.com/content/www/us/en/jobs/jobs-at-intel.html",
    "Qualcomm": "https://www.qualcomm.com/company/careers",
    "Deloitte": "https://apply.deloitte.com/careers/SearchJobs",
    "eBay": "https://jobs.ebayinc.com/us/en/",
    "EY": "https://www.ey.com/en_us/careers/job-search",
    "Expedia": "https://careers.expediagroup.com/jobs/",
    "HPE": "https://careers.hpe.com/us/en/",
    "Arm": "https://careers.arm.com/en/search-jobs",
    "Applied Materials": "https://careers.appliedmaterials.com/",
    "ByteDance": "https://jobs.bytedance.com/en/",
}


ATS_PATTERNS = {
    "WORKDAY": (
        "myworkdayjobs.com",
        "/wday/cxs/",
    ),
    "GREENHOUSE": (
        "greenhouse.io",
        "greenhouse.com",
    ),
    "ASHBY": (
        "ashbyhq.com",
    ),
    "LEVER": (
        "lever.co",
    ),
    "SMARTRECRUITERS": (
        "smartrecruiters.com",
    ),
    "EIGHTFOLD": (
        "eightfold.ai",
        "/api/pcsx/",
    ),
    "ORACLE_HCM": (
        "oraclecloud.com",
        "candidateexperience",
        "recruitingcejob",
    ),
}


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/150 Safari/537.36"
    )
}


def pending_batch(limit: int = 10):
    with get_connection() as conn:
        return [
            dict(r)
            for r in conn.execute(
                """
                SELECT *
                FROM source_discovery_batches
                WHERE batch_name=?
                  AND resolution_status='PENDING'
                ORDER BY
                    source_discovery_score DESC,
                    combined_sponsor_score DESC
                LIMIT ?
                """,
                (
                    BATCH_NAME,
                    limit,
                ),
            ).fetchall()
        ]


def detect_ats(text: str) -> list[str]:
    value = (text or "").lower()

    matches = []

    for ats, patterns in ATS_PATTERNS.items():
        if any(
            pattern.lower() in value
            for pattern in patterns
        ):
            matches.append(ats)

    return matches


def extract_urls(text: str) -> list[str]:
    if not text:
        return []

    urls = re.findall(
        r'https?://[^\s"\'<>]+',
        text,
        re.I,
    )

    # Preserve order, remove duplicates.
    return list(dict.fromkeys(urls))


def inspect_company(name: str):
    careers_url = OFFICIAL_CAREERS.get(name)

    if not careers_url:
        return {
            "name": name,
            "careers_url": None,
            "status": None,
            "final_url": None,
            "ats_candidates": [],
            "candidate_urls": [],
            "error": "NO_SEEDED_CAREERS_URL",
        }

    try:
        r = requests.get(
            careers_url,
            headers=HEADERS,
            timeout=25,
            allow_redirects=True,
        )

        body = r.text or ""

        combined = (
            r.url
            + "\n"
            + body
        )

        ats = detect_ats(
            combined
        )

        urls = extract_urls(
            body
        )

        candidate_urls = []

        for url in urls:
            url_lower = url.lower()

            if any(
                marker in url_lower
                for patterns in ATS_PATTERNS.values()
                for marker in patterns
            ):
                candidate_urls.append(url)

        candidate_urls = list(
            dict.fromkeys(candidate_urls)
        )

        return {
            "name": name,
            "careers_url": careers_url,
            "status": r.status_code,
            "final_url": r.url,
            "ats_candidates": ats,
            "candidate_urls": candidate_urls[:20],
            "error": None,
        }

    except Exception as exc:
        return {
            "name": name,
            "careers_url": careers_url,
            "status": None,
            "final_url": None,
            "ats_candidates": [],
            "candidate_urls": [],
            "error": str(exc),
        }

def mark_resolution(
    display_name: str,
    status: str,
    ats_type: str | None = None,
    source_url: str | None = None,
    notes: str | None = None,
):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE source_discovery_batches
            SET resolution_status = ?
            WHERE batch_name = ?
              AND display_name = ?
            """,
            (
                status,
                BATCH_NAME,
                display_name,
            ),
        )

        conn.commit()

    print(
        f"{display_name}: "
        f"{status}"
        + (
            f" | {ats_type}"
            if ats_type
            else ""
        )
        + (
            f" | {source_url}"
            if source_url
            else ""
        )
        + (
            f" | {notes}"
            if notes
            else ""
        )
    )

def main():
    targets = pending_batch(10)

    print(
        "=== SOURCE RESOLUTION TARGETS ==="
    )

    for i, row in enumerate(
        targets,
        1,
    ):
        print(
            f"{i:>2}. "
            f"{row['source_discovery_score']:>5.1f} | "
            f"{row['display_name']}"
        )

    print()
    print(
        "=== CAREERS / ATS PROBE ==="
    )

    for row in targets:
        name = row["display_name"]

        result = inspect_company(
            name
        )

        print()
        print("=" * 90)
        print("COMPANY:", name)
        print(
            "CAREERS:",
            result["careers_url"],
        )
        print(
            "STATUS:",
            result["status"],
        )
        print(
            "FINAL:",
            result["final_url"],
        )
        print(
            "ATS CANDIDATES:",
            result["ats_candidates"],
        )
        print(
            "ERROR:",
            result["error"],
        )

        if result["candidate_urls"]:
            print(
                "CANDIDATE URLS:"
            )

            for url in result[
                "candidate_urls"
            ]:
                print(
                    " ",
                    url,
                )


if __name__ == "__main__":
    main()