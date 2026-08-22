from __future__ import annotations

import html
import json
import re
from urllib.parse import urljoin, urlparse

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


SEEDS = {
    "Qualcomm": "https://www.qualcomm.com/company/careers",
    "Deloitte": "https://apply.deloitte.com/careers/SearchJobs",
    "eBay": "https://jobs.ebayinc.com/us/en/",
    "EY": "https://www.ey.com/en_us/careers/job-search",
    "HPE": "https://careers.hpe.com/us/en/",
    "Arm": "https://careers.arm.com/en/search-jobs",
    "ByteDance": "https://joinbytedance.com/",
    "MathWorks": "https://www.mathworks.com/company/jobs/opportunities.html",
    "TikTok Inc.": "https://lifeattiktok.com/search",
    "Mphasis Corporation": "https://careers.mphasis.com/",
    "TECH MAHINDRA (AMERICAS), INC": "https://careers.techmahindra.com/",
    "ADP": "https://jobs.adp.com/en/",
    "Lucid USA, Inc.": "https://lucidmotors.com/careers",
    "Micron Technology, Inc.": "https://careers.micron.com/careers",
    "Netflix": "https://jobs.netflix.com/",
    "SAP": "https://jobs.sap.com/",
    "Synopsys, Inc.": "https://careers.synopsys.com/",
    "CGI Technologies and Solutions Inc.": "https://cgi.njoyn.com/",
    "ASML": "https://www.asml.com/en/careers/find-your-job",
    "Snap": "https://careers.snap.com/jobs",
}


ATS_MARKERS = {
    "WORKDAY": [
        "myworkdayjobs.com",
        "/wday/cxs/",
    ],
    "EIGHTFOLD": [
        "eightfold.ai",
        "/api/pcsx/",
    ],
    "GREENHOUSE": [
        "job-boards.greenhouse.io",
        "boards.greenhouse.io",
        "boards-api.greenhouse.io",
    ],
    "LEVER": [
        "jobs.lever.co",
        "api.lever.co",
    ],
    "ASHBY": [
        "jobs.ashbyhq.com",
        "api.ashbyhq.com",
    ],
    "SMARTRECRUITERS": [
        "jobs.smartrecruiters.com",
        "api.smartrecruiters.com",
    ],
    "ORACLE_HCM": [
        "oraclecloud.com",
        "recruitingcejob",
        "candidateexperience",
    ],
}


def pending():
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
                """,
                (BATCH_NAME,),
            ).fetchall()
        ]


def clean_url(value: str) -> str:
    value = html.unescape(value or "")

    value = value.replace(
        "\\/",
        "/",
    )

    value = value.replace(
        "\\u002F",
        "/",
    )

    value = value.replace(
        "\\u003A",
        ":",
    )

    value = value.rstrip(
        "\\\"',);]}<>"
    )

    return value


def extract_absolute_urls(text: str):
    text = html.unescape(
        text or ""
    )

    patterns = [
        r'https?://[^\s"\'<>]+',
        r'https?:\\?/\\?/[^\s"\'<>]+',
    ]

    out = []

    for pattern in patterns:
        for raw in re.findall(
            pattern,
            text,
            re.I,
        ):
            url = clean_url(raw)

            if (
                url.startswith("http")
                and url not in out
            ):
                out.append(url)

    return out


def detect_ats(value: str):
    low = (
        value or ""
    ).lower()

    found = []

    for ats, markers in ATS_MARKERS.items():
        if any(
            marker.lower() in low
            for marker in markers
        ):
            found.append(ats)

    return found


def inspect_script(
    session: requests.Session,
    script_url: str,
):
    try:
        r = session.get(
            script_url,
            timeout=20,
        )

        if not r.ok:
            return ""

        content_type = (
            r.headers.get(
                "content-type",
                "",
            ).lower()
        )

        if (
            "javascript" not in content_type
            and "json" not in content_type
            and "text" not in content_type
        ):
            return ""

        # Avoid unexpectedly enormous assets.
        if len(r.content) > 5_000_000:
            return ""

        return r.text or ""

    except Exception:
        return ""


def inspect_company(
    name: str,
    seed: str,
):
    session = requests.Session()
    session.headers.update(
        HEADERS
    )

    result = {
        "name": name,
        "seed": seed,
        "status": None,
        "final": None,
        "ats": set(),
        "ats_urls": [],
        "scripts_checked": 0,
        "error": None,
    }

    try:
        r = session.get(
            seed,
            timeout=30,
            allow_redirects=True,
        )

    except Exception as exc:
        result["error"] = str(exc)
        return result

    result["status"] = r.status_code
    result["final"] = r.url

    page = r.text or ""

    # ------------------------------------------------------
    # Inspect main HTML
    # ------------------------------------------------------

    for ats in detect_ats(
        r.url + "\n" + page
    ):
        result["ats"].add(ats)

    urls = extract_absolute_urls(
        page
    )

    for url in urls:
        ats_values = detect_ats(url)

        if ats_values:
            result["ats"].update(
                ats_values
            )

            if url not in result["ats_urls"]:
                result["ats_urls"].append(
                    url
                )

    # ------------------------------------------------------
    # Inspect linked JavaScript
    # ------------------------------------------------------

    script_srcs = re.findall(
        r'<script[^>]+src=["\']([^"\']+)["\']',
        page,
        re.I,
    )

    for src in script_srcs[:40]:
        script_url = urljoin(
            r.url,
            html.unescape(src),
        )

        body = inspect_script(
            session,
            script_url,
        )

        if not body:
            continue

        result["scripts_checked"] += 1

        ats_values = detect_ats(
            body
        )

        result["ats"].update(
            ats_values
        )

        for url in extract_absolute_urls(
            body
        ):
            url_ats = detect_ats(
                url
            )

            if url_ats:
                result["ats"].update(
                    url_ats
                )

                if url not in result["ats_urls"]:
                    result["ats_urls"].append(
                        url
                    )

    result["ats"] = sorted(
        result["ats"]
    )

    return result


def canonical_candidate(
    ats: str,
    urls: list[str],
):
    if ats == "WORKDAY":
        for url in urls:
            if "myworkdayjobs.com" not in url.lower():
                continue

            p = urlparse(url)

            parts = [
                x
                for x in p.path.split("/")
                if x
            ]

            if not parts:
                continue

            return (
                f"https://{p.netloc}/"
                f"{parts[0]}"
            )

    if ats == "EIGHTFOLD":
        for url in urls:
            if "eightfold.ai" not in url.lower():
                continue

            p = urlparse(url)

            if not p.netloc:
                continue

            return (
                f"https://{p.netloc}/careers"
            )

    if ats == "LEVER":
        for url in urls:
            if "jobs.lever.co" in url.lower():
                p = urlparse(url)

                parts = [
                    x
                    for x in p.path.split("/")
                    if x
                ]

                if parts:
                    return (
                        f"https://jobs.lever.co/"
                        f"{parts[0]}"
                    )

    if ats == "GREENHOUSE":
        for url in urls:
            low = url.lower()
            p = urlparse(url)

            # Public branded Greenhouse board.
            if (
                "job-boards.greenhouse.io" in low
                or "boards.greenhouse.io" in low
            ):
                parts = [
                    x
                    for x in p.path.split("/")
                    if x
                ]

                if parts:
                    return (
                        f"https://job-boards.greenhouse.io/"
                        f"{parts[0]}"
                    )

            # Greenhouse boards API:
            # /v1/boards/<token>/...
            if "boards-api.greenhouse.io" in low:
                parts = [
                    x
                    for x in p.path.split("/")
                    if x
                ]

                try:
                    board_index = parts.index("boards")
                    token = parts[board_index + 1]
                except (ValueError, IndexError):
                    continue

                return (
                    f"https://job-boards.greenhouse.io/"
                    f"{token}"
                )

    if ats == "ASHBY":
        for url in urls:
            if "jobs.ashbyhq.com" in url.lower():
                p = urlparse(url)

                parts = [
                    x
                    for x in p.path.split("/")
                    if x
                ]

                if parts:
                    return (
                        f"https://jobs.ashbyhq.com/"
                        f"{parts[0]}"
                    )

    if ats == "SMARTRECRUITERS":
        for url in urls:
            if "smartrecruiters.com" in url.lower():
                return url

    if ats == "ORACLE_HCM":
        for url in urls:
            if "oraclecloud.com" in url.lower():
                return url

    return None


def persist_candidate(
    row,
    result,
):
    ats_values = result["ats"]

    # Only auto-stage a unique ATS family.
    if len(ats_values) != 1:
        return False

    ats = ats_values[0]

    candidate = canonical_candidate(
        ats,
        result["ats_urls"],
    )

    if not candidate:
        return False

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE source_discovery_batches
            SET
                resolution_status='ATS_CANDIDATE',
                discovered_ats=?,
                discovered_careers_url=?,
                notes=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
              AND resolution_status='PENDING'
            """,
            (
                ats,
                candidate,
                (
                    "Deep automatic ATS discovery. "
                    f"Seed={result['seed']}; "
                    f"HTTP={result['status']}; "
                    f"final={result['final']}; "
                    f"scripts_checked="
                    f"{result['scripts_checked']}."
                ),
                row["id"],
            ),
        )

        conn.commit()

    return True


def main():
    rows = pending()

    print(
        "PENDING:",
        len(rows),
    )

    for row in rows:
        name = row[
            "display_name"
        ]

        seed = SEEDS.get(
            name
        )

        print()
        print("=" * 100)
        print(
            "COMPANY:",
            name,
        )

        if not seed:
            print(
                "NO SEED URL"
            )
            continue

        result = inspect_company(
            name,
            seed,
        )

        print(
            "SEED:",
            seed,
        )
        print(
            "STATUS:",
            result["status"],
        )
        print(
            "FINAL:",
            result["final"],
        )
        print(
            "SCRIPTS:",
            result["scripts_checked"],
        )
        print(
            "ATS:",
            result["ats"],
        )
        print(
            "ERROR:",
            result["error"],
        )

        if result["ats_urls"]:
            print(
                "ATS URLS:"
            )

            for url in result[
                "ats_urls"
            ][:20]:
                print(
                    " ",
                    url,
                )

        staged = persist_candidate(
            row,
            result,
        )

        print(
            "STAGED:",
            staged,
        )


if __name__ == "__main__":
    main()