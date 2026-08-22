from __future__ import annotations

import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.registry.repository import conn


FINGERPRINTS = {
    "WORKDAY": (
        "myworkdayjobs.com",
        "/wday/cxs/",
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
    "GREENHOUSE": (
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "boards-api.greenhouse.io",
    ),
    "LEVER": (
        "jobs.lever.co",
        "api.lever.co",
    ),
    "ASHBY": (
        "jobs.ashbyhq.com",
        "api.ashbyhq.com",
    ),
    "SMARTRECRUITERS": (
        "jobs.smartrecruiters.com",
        "api.smartrecruiters.com",
    ),
    "WORKABLE": (
        "apply.workable.com",
    ),
}


def unresolved_direct_employers():
    with conn() as c:
        return c.execute("""
            SELECT
                e.id,
                e.display_name,
                e.careers_url
            FROM employers e
            LEFT JOIN employer_sources es
              ON es.employer_id=e.id
             AND es.enabled=1
             AND es.source_verified=1
            WHERE e.enabled=1
              AND e.source_type='DIRECT_EMPLOYER'
              AND es.id IS NULL
            ORDER BY LOWER(e.display_name)
        """).fetchall()


def collect_text(session, url):
    r = session.get(
        url,
        timeout=30,
        allow_redirects=True,
    )

    final = r.url
    html = r.text or ""

    parts = [
        final,
        html,
    ]

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(True):
        for attr in (
            "href",
            "src",
            "action",
            "data-url",
            "data-href",
        ):
            value = tag.get(attr)

            if not value:
                continue

            parts.append(
                urljoin(final, value)
            )

    return r.status_code, final, "\n".join(parts)


def classify(blob):
    low = blob.lower()

    matches = []

    for family, markers in FINGERPRINTS.items():
        if any(marker.lower() in low for marker in markers):
            matches.append(family)

    return matches


def extract_candidates(blob):
    urls = set()

    for m in re.findall(
        r'https?://[^"\'<>\s]+',
        blob,
        flags=re.I,
    ):
        cleaned = (
            m.replace("&amp;", "&")
             .replace("\\/", "/")
             .rstrip("),.;'\"")
        )

        urls.add(cleaned)

    return sorted(urls)


def main():
    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 "
            "(Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/150 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })

    rows = unresolved_direct_employers()

    print("DIRECT UNRESOLVED:", len(rows))

    for row in rows:
        company = row["display_name"]
        url = row["careers_url"]

        print("\n" + "=" * 100)
        print("COMPANY:", company)
        print("URL:", url or "")

        if not url:
            print("RESULT: NO_CAREERS_URL")
            continue

        try:
            status, final, blob = collect_text(
                session,
                url,
            )

            print("STATUS:", status)
            print("FINAL:", final)

            families = classify(blob)

            print(
                "FAMILIES:",
                ",".join(families)
                if families
                else "NONE",
            )

            if not families:
                print("RESULT: CUSTOM_OR_UNKNOWN")
                continue

            candidates = extract_candidates(blob)

            for family in families:
                print("CANDIDATES FOR:", family)

                markers = FINGERPRINTS[family]

                shown = 0

                for candidate in candidates:
                    low = candidate.lower()

                    if any(
                        marker.lower() in low
                        for marker in markers
                    ):
                        print("  ", candidate[:1000])

                        shown += 1

                        if shown >= 12:
                            break

            print("RESULT: ATS_CANDIDATE")

        except Exception as exc:
            print("ERROR:", repr(exc))
            print("RESULT: FETCH_ERROR")


if __name__ == "__main__":
    main()
