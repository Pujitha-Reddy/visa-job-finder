from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.registry.repository import conn


ATS_MARKERS = {
    "WORKDAY": (
        "myworkdayjobs.com",
        "/wday/cxs/",
    ),
    "EIGHTFOLD": (
        "eightfold.ai",
        "/api/pcsx/",
        "pcsxpwa",
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

API_MARKERS = (
    "/api/",
    "/jobs/search",
    "/search/jobs",
    "/search-jobs",
    "/jobs?",
    "/careers/api",
    "graphql",
    "jobsearch",
    "job-search",
    "requisitions",
)


def unresolved():
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


def same_host(a, b):
    try:
        return (
            urlparse(a).netloc.lower()
            ==
            urlparse(b).netloc.lower()
        )
    except Exception:
        return False


def ats_matches(text):
    low = text.lower()
    return [
        family
        for family, markers in ATS_MARKERS.items()
        if any(x in low for x in markers)
    ]


def interesting_strings(text):
    found = set()

    for m in re.findall(
        r'https?://[^"\'<>\s]+',
        text,
        flags=re.I,
    ):
        m = (
            m.replace("\\/", "/")
             .replace("&amp;", "&")
             .rstrip("),.;'\"")
        )

        low = m.lower()

        if (
            any(
                marker in low
                for markers in ATS_MARKERS.values()
                for marker in markers
            )
            or any(x in low for x in API_MARKERS)
        ):
            found.add(m)

    return sorted(found)


def fetch(session, url):
    return session.get(
        url,
        timeout=25,
        allow_redirects=True,
    )


def main():
    s = requests.Session()

    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })

    rows = unresolved()

    print("UNRESOLVED DIRECT:", len(rows))

    for row in rows:
        company = row["display_name"]
        url = row["careers_url"]

        print("\n" + "=" * 100)
        print("COMPANY:", company)
        print("URL:", url or "")

        if not url:
            print("RESULT: NO_URL")
            continue

        try:
            r = fetch(s, url)
        except Exception as exc:
            print("RESULT: FETCH_ERROR")
            print("ERROR:", repr(exc))
            continue

        print("STATUS:", r.status_code)
        print("FINAL:", r.url)

        html = r.text or ""
        combined = [html, r.url]

        soup = BeautifulSoup(html, "html.parser")

        # -------------------------------------------------
        # Search/careers links
        # -------------------------------------------------

        candidate_pages = []

        for a in soup.find_all("a", href=True):
            href = urljoin(r.url, a["href"])

            low = href.lower()

            if any(
                x in low
                for x in (
                    "search",
                    "jobs",
                    "careers",
                    "opportunities",
                )
            ):
                candidate_pages.append(href)

        # Keep bounded.
        candidate_pages = list(
            dict.fromkeys(candidate_pages)
        )[:5]

        for candidate in candidate_pages:
            if candidate == r.url:
                continue

            try:
                cr = fetch(s, candidate)

                print(
                    "PAGE:",
                    cr.status_code,
                    cr.url,
                )

                combined.append(cr.text or "")
                combined.append(cr.url)

            except Exception:
                pass

        # -------------------------------------------------
        # JS asset inspection
        # -------------------------------------------------

        scripts = []

        for script in soup.find_all(
            "script",
            src=True,
        ):
            src = urljoin(
                r.url,
                script["src"],
            )

            # Prefer first-party JS.
            if same_host(src, r.url):
                scripts.append(src)

        scripts = list(
            dict.fromkeys(scripts)
        )[:8]

        for src in scripts:
            try:
                jr = fetch(s, src)

                # Bound memory/output. We only need strings.
                if (
                    jr.status_code == 200
                    and len(jr.content) <= 4_000_000
                ):
                    combined.append(
                        jr.text or ""
                    )

            except Exception:
                pass

        blob = "\n".join(combined)

        families = ats_matches(blob)

        print(
            "FAMILIES:",
            ",".join(families)
            if families
            else "NONE",
        )

        strings = interesting_strings(blob)

        for item in strings[:20]:
            print("DISCOVERED:", item[:1200])

        if families:
            print("RESULT: ATS_CANDIDATE")
        elif strings:
            print("RESULT: CUSTOM_API_CANDIDATE")
        else:
            print("RESULT: CUSTOM_OR_BLOCKED")


if __name__ == "__main__":
    main()
