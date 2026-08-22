from __future__ import annotations

import html
import json
import re
from urllib.parse import urlparse

import requests


TARGETS = {
    "AT&T": "https://www.att.jobs/",
    "Bank of America": "https://careers.bankofamerica.com/en-us",
    "Boeing": "https://jobs.boeing.com/",
    "Capital One": "https://www.capitalonecareers.com/",
    "Centene": "https://jobs.centene.com/us/en/",
    "Cigna": "https://jobs.thecignagroup.com/us/en",
    "Citi": "https://jobs.citi.com/",
    "Comcast": "https://jobs.comcast.com/",
    "Elevance Health": "https://careers.elevancehealth.com/",
    "Evernorth": "https://jobs.thecignagroup.com/us/en",
    "Home Depot": "https://careers.homedepot.com/",
    "Mastercard": "https://careers.mastercard.com/us/en",
    "Palo Alto Networks": "https://jobs.paloaltonetworks.com/en",
    "T-Mobile": "https://careers.t-mobile.com/",
    "Target": "https://corporate.target.com/careers",
    "U.S. Bank": "https://careers.usbank.com/global/en",
}


WORKDAY_RE = re.compile(
    r"""https?:
        (?:\\?/\\?/)?
        [A-Za-z0-9._-]+
        \.(?:wd\d+\.)?
        myworkdayjobs\.com
        (?:
            (?:\\?/)[A-Za-z0-9._~!$&'()*+,;=:@%/-]+
        )?
    """,
    re.I | re.X,
)


def clean_url(value: str) -> str:
    value = html.unescape(value)

    value = (
        value
        .replace("\\/", "/")
        .replace("\\u002F", "/")
        .replace("\\u003A", ":")
        .replace("\\u0026", "&")
    )

    value = value.strip(
        "\"'()[]{}<> ,;"
    )

    return value


def canonical_workday_url(url: str) -> str | None:
    try:
        p = urlparse(url)

        host = p.netloc.lower()

        if "myworkdayjobs.com" not in host:
            return None

        parts = [
            x
            for x in p.path.split("/")
            if x
        ]

        if not parts:
            return None

        site = parts[0]

        return f"https://{host}/{site}"

    except Exception:
        return None


def discover_candidates(
    session: requests.Session,
    careers_url: str,
) -> tuple[str | None, int | None, set[str]]:

    response = session.get(
        careers_url,
        timeout=30,
        allow_redirects=True,
    )

    status = response.status_code
    final_url = response.url

    text = response.text or ""

    # Decode common escaped JSON/JS forms.
    searchable = (
        text
        .replace("\\/", "/")
        .replace("\\u002F", "/")
        .replace("\\u003A", ":")
    )

    candidates = set()

    # Redirect itself might already be Workday.
    final_candidate = canonical_workday_url(
        final_url
    )

    if final_candidate:
        candidates.add(final_candidate)

    for match in WORKDAY_RE.finditer(searchable):
        cleaned = clean_url(
            match.group(0)
        )

        candidate = canonical_workday_url(
            cleaned
        )

        if candidate:
            candidates.add(candidate)

    # Extra permissive search for protocol-relative / escaped references.
    loose = re.findall(
        r"""(?:https?:)?//[
            A-Za-z0-9._-]+
            (?:\.wd\d+)?\.myworkdayjobs\.com
            /[A-Za-z0-9._~!$&'()*+,;=:@%/-]+
        """,
        searchable,
        flags=re.I | re.X,
    )

    for value in loose:
        value = clean_url(value)

        if value.startswith("//"):
            value = "https:" + value

        candidate = canonical_workday_url(
            value
        )

        if candidate:
            candidates.add(candidate)

    return final_url, status, candidates


def workday_parts(careers_url: str):
    p = urlparse(careers_url)

    host = p.netloc

    parts = [
        x
        for x in p.path.split("/")
        if x
    ]

    if not host or not parts:
        raise ValueError(
            f"Invalid Workday URL: {careers_url}"
        )

    site = parts[0]
    tenant = host.split(".")[0]

    return host, tenant, site


def verify_candidate(
    session: requests.Session,
    careers_url: str,
) -> dict:

    host, tenant, site = workday_parts(
        careers_url
    )

    api = (
        f"https://{host}"
        f"/wday/cxs/{tenant}/{site}/jobs"
    )

    try:
        response = session.post(
            api,
            json={
                "appliedFacets": {},
                "limit": 20,
                "offset": 0,
                "searchText": "software engineer",
            },
            timeout=30,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

        result = {
            "careers_url": careers_url,
            "api": api,
            "status": response.status_code,
            "valid": False,
            "total": None,
            "software_page_jobs": None,
            "error": None,
        }

        if response.status_code != 200:
            result["error"] = (
                f"HTTP {response.status_code}"
            )
            return result

        data = response.json()

        postings = (
            data.get("jobPostings")
            or []
        )

        total = data.get("total")

        # Valid Workday CXS response.
        if isinstance(postings, list):
            result["valid"] = True
            result["total"] = total
            result["software_page_jobs"] = len(
                postings
            )

        return result

    except Exception as exc:
        return {
            "careers_url": careers_url,
            "api": api,
            "status": None,
            "valid": False,
            "total": None,
            "software_page_jobs": None,
            "error": str(exc),
        }


def main():
    session = requests.Session()

    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 "
            "(Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 "
            "Chrome/150 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    })

    summary = {
        "verified": 0,
        "no_candidate": 0,
        "candidate_invalid": 0,
        "errors": 0,
    }

    for company, marketing_url in TARGETS.items():

        print("\n" + "=" * 100)
        print("COMPANY:", company)
        print("MARKETING URL:", marketing_url)

        try:
            final_url, status, candidates = (
                discover_candidates(
                    session,
                    marketing_url,
                )
            )
        except Exception as exc:
            print("DISCOVERY ERROR:", exc)

            summary["errors"] += 1
            continue

        print("PAGE STATUS:", status)
        print("FINAL URL:", final_url)
        print(
            "WORKDAY CANDIDATES:",
            len(candidates),
        )

        if not candidates:
            print(
                "RESULT: NO_WORKDAY_URL_FOUND"
            )

            summary["no_candidate"] += 1
            continue

        verified = []

        for candidate in sorted(candidates):

            print("\nCANDIDATE:", candidate)

            result = verify_candidate(
                session,
                candidate,
            )

            print(
                "CXS STATUS:",
                result["status"],
            )

            print(
                "VALID:",
                result["valid"],
            )

            print(
                "TOTAL:",
                result["total"],
            )

            print(
                "SOFTWARE PAGE:",
                result[
                    "software_page_jobs"
                ],
            )

            if result["error"]:
                print(
                    "ERROR:",
                    result["error"],
                )

            if result["valid"]:
                verified.append(result)

        if verified:
            # Prefer candidate with largest matching result set.
            verified.sort(
                key=lambda x: (
                    x["total"] or 0
                ),
                reverse=True,
            )

            best = verified[0]

            print()
            print("RESULT: VERIFIED")
            print(
                "VERIFIED WORKDAY URL:",
                best["careers_url"],
            )
            print(
                "VERIFIED CXS API:",
                best["api"],
            )
            print(
                "TOTAL MATCHES:",
                best["total"],
            )

            summary["verified"] += 1

        else:
            print()
            print(
                "RESULT: CANDIDATES_INVALID"
            )

            summary[
                "candidate_invalid"
            ] += 1

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)

    print(json.dumps(
        summary,
        indent=2,
    ))


if __name__ == "__main__":
    main()
