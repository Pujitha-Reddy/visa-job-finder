from __future__ import annotations

import html
import re
from urllib.parse import urlparse

import requests

from app.database import get_connection


BATCH_NAME = "SPONSOR_EXPANSION_V1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
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


SEEDED_CAREERS = {
    "Intel": "https://www.intel.com/content/www/us/en/jobs/jobs-at-intel.html",
    "Qualcomm": "https://www.qualcomm.com/company/careers",
    "Deloitte": "https://apply.deloitte.com/careers/SearchJobs",
    "eBay": "https://jobs.ebayinc.com/us/en/",
    "EY": "https://www.ey.com/en_us/careers/job-search",
    "HPE": "https://careers.hpe.com/us/en/",
    "Arm": "https://careers.arm.com/en/search-jobs",
    "ByteDance": "https://joinbytedance.com",
    "MathWorks": "https://www.mathworks.com/company/jobs/opportunities.html",
    "TikTok Inc.": "https://lifeattiktok.com/search",
    "Mphasis Corporation": "https://careers.mphasis.com/",
    "TECH MAHINDRA (AMERICAS), INC": "https://careers.techmahindra.com/",
    "ADP": "https://jobs.adp.com/",
    "Lucid USA, Inc.": "https://lucidmotors.com/careers",
    "Micron Technology, Inc.": "https://careers.micron.com/",
    "Netflix": "https://jobs.netflix.com/",
    "SAP": "https://jobs.sap.com/",
    "Cadence Design Systems, Inc.": "https://cadence.wd1.myworkdayjobs.com/External_Careers",
    "Synopsys, Inc.": "https://careers.synopsys.com/",
    "Zoox": "https://jobs.lever.co/zoox",
    "CGI Technologies and Solutions Inc.": "https://cgi.njoyn.com/",
    "ASML": "https://www.asml.com/en/careers/find-your-job",
    "Snap": "https://careers.snap.com/jobs",
}


def pending_rows():
    with get_connection() as c:
        return [
            dict(r)
            for r in c.execute(
                """
                SELECT *
                FROM source_discovery_batches
                WHERE batch_name=?
                  AND resolution_status='PENDING'
                ORDER BY
                    source_discovery_score DESC,
                    combined_sponsor_score DESC
                """,
                (BATCH_NAME,),
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

    text = html.unescape(text)

    urls = re.findall(
        r'https?://[^\s"\'<>]+',
        text,
        re.I,
    )

    cleaned = []

    for url in urls:
        url = url.rstrip(
            "\"',);]}"
        )

        if url not in cleaned:
            cleaned.append(url)

    return cleaned


def candidate_urls(body: str):
    out = []

    for url in extract_urls(body):
        lower = url.lower()

        if any(
            marker.lower() in lower
            for patterns in ATS_PATTERNS.values()
            for marker in patterns
        ):
            out.append(url)

    return out


def inspect(name: str, careers_url: str):
    session = requests.Session()
    session.headers.update(HEADERS)

    result = {
        "display_name": name,
        "seed_url": careers_url,
        "status": None,
        "final_url": None,
        "ats_candidates": [],
        "candidate_urls": [],
        "error": None,
    }

    try:
        r = session.get(
            careers_url,
            timeout=30,
            allow_redirects=True,
        )

        result["status"] = r.status_code
        result["final_url"] = r.url

        combined = (
            r.url
            + "\n"
            + (r.text or "")
        )

        result["ats_candidates"] = detect_ats(
            combined
        )

        result["candidate_urls"] = candidate_urls(
            r.text
        )[:20]

    except Exception as exc:
        result["error"] = str(exc)

    return result


def choose_candidate(result):
    ats = result["ats_candidates"]

    if len(ats) != 1:
        return None, None

    selected_ats = ats[0]

    matching_urls = []

    for url in result["candidate_urls"]:
        if selected_ats in detect_ats(url):
            matching_urls.append(url)

    if matching_urls:
        return selected_ats, matching_urls[0]

    final_url = result["final_url"]

    if (
        final_url
        and selected_ats in detect_ats(final_url)
    ):
        return selected_ats, final_url

    return selected_ats, None


def persist_candidate(
    row,
    result,
    ats,
    candidate_url,
):
    if not ats:
        return

    with get_connection() as c:
        c.execute(
            """
            UPDATE source_discovery_batches
            SET
                resolution_status='ATS_CANDIDATE',
                discovered_careers_url=?,
                discovered_ats=?,
                notes=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
              AND resolution_status='PENDING'
            """,
            (
                candidate_url or result["final_url"],
                ats,
                (
                    f"Automatic ATS candidate discovery. "
                    f"Seed={result['seed_url']}; "
                    f"HTTP={result['status']}; "
                    f"final={result['final_url']}."
                ),
                row["id"],
            ),
        )

        c.commit()


def main():
    rows = pending_rows()

    print(
        "PENDING:",
        len(rows),
    )

    for row in rows:
        name = row["display_name"]

        seed = SEEDED_CAREERS.get(name)

        print()
        print("=" * 100)
        print("COMPANY:", name)

        if not seed:
            print("NO SEEDED CAREERS URL")
            continue

        result = inspect(
            name,
            seed,
        )

        print("SEED:", seed)
        print("STATUS:", result["status"])
        print("FINAL:", result["final_url"])
        print(
            "ATS CANDIDATES:",
            result["ats_candidates"],
        )
        print(
            "ERROR:",
            result["error"],
        )

        if result["candidate_urls"]:
            print("CANDIDATE URLS:")

            for url in result["candidate_urls"]:
                print(" ", url)

        ats, candidate_url = choose_candidate(
            result
        )

        if ats:
            print(
                "SELECTED ATS:",
                ats,
            )
            print(
                "SELECTED URL:",
                candidate_url,
            )

            persist_candidate(
                row,
                result,
                ats,
                candidate_url,
            )


if __name__ == "__main__":
    main()