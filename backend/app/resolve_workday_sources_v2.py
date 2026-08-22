from __future__ import annotations

import html
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


TARGETS = {
    "AT&T":
        "https://www.att.jobs/",

    "Bank of America":
        "https://careers.bankofamerica.com/en-us",

    "Boeing":
        "https://jobs.boeing.com/",

    "Citi":
        "https://jobs.citi.com/",

    "Comcast":
        "https://jobs.comcast.com/",

    "Palo Alto Networks":
        "https://jobs.paloaltonetworks.com/en",
}


LOCALE_SEGMENT = re.compile(
    r"^[a-z]{2}(?:[-_][A-Za-z]{2})?$",
    re.I,
)


def clean_text(value: str) -> str:
    return (
        html.unescape(value or "")
        .replace("\\/", "/")
        .replace("\\u002F", "/")
        .replace("\\u003A", ":")
        .replace("\\u0026", "&")
    )


def normalize_workday_candidate(
    value: str,
) -> str | None:
    """
    Convert variants such as:

        https://foo.wd1.myworkdayjobs.com/en-US/External
        https://foo.wd1.myworkdayjobs.com/External
        //foo.wd1.myworkdayjobs.com/en-US/External

    into:

        https://foo.wd1.myworkdayjobs.com/External
    """

    value = clean_text(value).strip(
        "\"'()[]{}<> ,;"
    )

    if value.startswith("//"):
        value = "https:" + value

    if not value.startswith("http"):
        return None

    try:
        p = urlparse(value)
    except Exception:
        return None

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

    # Drop locale prefix like en-US.
    while (
        parts
        and LOCALE_SEGMENT.match(parts[0])
    ):
        parts.pop(0)

    if not parts:
        return None

    site = parts[0]

    # Avoid obvious non-site routes.
    if site.lower() in {
        "job",
        "jobs",
        "search",
        "home",
        "career",
        "careers",
    }:
        return None

    return (
        f"https://{host}/{site}"
    )


def verify_workday(
    session: requests.Session,
    careers_url: str,
) -> dict:

    p = urlparse(careers_url)

    host = p.netloc

    parts = [
        x
        for x in p.path.split("/")
        if x
    ]

    if not host or not parts:
        return {
            "valid": False,
            "status": None,
            "total": None,
            "api": None,
            "error": "invalid candidate",
        }

    site = parts[0]
    tenant = host.split(".")[0]

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

        if response.status_code != 200:
            return {
                "valid": False,
                "status": response.status_code,
                "total": None,
                "api": api,
                "error": (
                    f"HTTP {response.status_code}"
                ),
            }

        payload = response.json()

        postings = (
            payload.get("jobPostings")
            or []
        )

        # A valid Workday CXS search response contains
        # jobPostings, even when zero jobs match.
        valid = isinstance(
            postings,
            list,
        )

        return {
            "valid": valid,
            "status": response.status_code,
            "total": payload.get("total"),
            "api": api,
            "error": None,
        }

    except Exception as exc:
        return {
            "valid": False,
            "status": None,
            "total": None,
            "api": api,
            "error": str(exc),
        }


def extract_candidates_from_text(
    text: str,
) -> set[str]:

    text = clean_text(text)

    candidates = set()

    # -----------------------------------------------------
    # 1. Direct Workday CXS endpoints.
    #
    # Strongest signal:
    #
    # /wday/cxs/<tenant>/<site>/jobs
    # -----------------------------------------------------

    cxs_patterns = [
        re.compile(
            r"""https?://
                ([A-Za-z0-9._-]+\.myworkdayjobs\.com)
                /wday/cxs/
                ([A-Za-z0-9._-]+)/
                ([A-Za-z0-9._~-]+)/
                jobs
            """,
            re.I | re.X,
        ),

        re.compile(
            r"""/wday/cxs/
                ([A-Za-z0-9._-]+)/
                ([A-Za-z0-9._~-]+)/
                jobs
            """,
            re.I | re.X,
        ),
    ]

    for match in cxs_patterns[0].finditer(text):
        host = match.group(1)
        site = match.group(3)

        candidates.add(
            f"https://{host}/{site}"
        )

    # -----------------------------------------------------
    # 2. Full myworkdayjobs URLs.
    # -----------------------------------------------------

    url_pattern = re.compile(
        r"""https?://
            [A-Za-z0-9._-]+
            \.(?:wd\d+\.)?
            myworkdayjobs\.com
            /[A-Za-z0-9._~!$&'()*+,;=:@%/?#-]+
        """,
        re.I | re.X,
    )

    for match in url_pattern.finditer(text):
        candidate = normalize_workday_candidate(
            match.group(0)
        )

        if candidate:
            candidates.add(candidate)

    return candidates


def page_and_script_candidates(
    session: requests.Session,
    marketing_url: str,
) -> tuple[int, str, set[str]]:

    response = session.get(
        marketing_url,
        timeout=30,
        allow_redirects=True,
    )

    response.raise_for_status()

    final_url = response.url
    html_text = response.text or ""

    candidates = extract_candidates_from_text(
        html_text
    )

    # Final redirect itself may be Workday.
    candidate = normalize_workday_candidate(
        final_url
    )

    if candidate:
        candidates.add(candidate)

    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    # -----------------------------------------------------
    # Extract raw href/action/data URLs.
    # -----------------------------------------------------

    attrs = (
        "href",
        "src",
        "action",
        "data-url",
        "data-href",
    )

    for tag in soup.find_all(True):
        for attr in attrs:
            value = tag.get(attr)

            if not value:
                continue

            absolute = urljoin(
                final_url,
                value,
            )

            candidate = normalize_workday_candidate(
                absolute
            )

            if candidate:
                candidates.add(candidate)

    # -----------------------------------------------------
    # Search a bounded number of JS bundles.
    #
    # Some branded careers sites only expose the Workday
    # site name inside JavaScript.
    # -----------------------------------------------------

    scripts = []

    for tag in soup.find_all(
        "script",
        src=True,
    ):
        src = urljoin(
            final_url,
            tag.get("src"),
        )

        if src not in scripts:
            scripts.append(src)

    # Keep this bounded.
    for script_url in scripts[:20]:
        try:
            r = session.get(
                script_url,
                timeout=20,
            )

            if r.status_code != 200:
                continue

            if len(r.text) > 5_000_000:
                continue

            candidates.update(
                extract_candidates_from_text(
                    r.text
                )
            )

        except Exception:
            pass

    return (
        response.status_code,
        final_url,
        candidates,
    )


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
        "Accept-Language":
            "en-US,en;q=0.9",
    })

    verified_count = 0

    for company, marketing_url in TARGETS.items():

        print("\n" + "=" * 100)
        print("COMPANY:", company)
        print(
            "MARKETING URL:",
            marketing_url,
        )

        try:
            (
                status,
                final_url,
                candidates,
            ) = page_and_script_candidates(
                session,
                marketing_url,
            )

        except Exception as exc:
            print(
                "DISCOVERY ERROR:",
                exc,
            )
            continue

        print("PAGE STATUS:", status)
        print("FINAL URL:", final_url)

        print(
            "CANDIDATES:",
            len(candidates),
        )

        if not candidates:
            print(
                "RESULT: NO_CANDIDATE"
            )
            continue

        verified = []

        for candidate in sorted(
            candidates
        ):
            print()
            print(
                "CANDIDATE:",
                candidate,
            )

            result = verify_workday(
                session,
                candidate,
            )

            print(
                "STATUS:",
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

            if result["error"]:
                print(
                    "ERROR:",
                    result["error"],
                )

            if result["valid"]:
                verified.append(
                    (
                        candidate,
                        result,
                    )
                )

        if verified:
            # Prefer candidate with largest matching result.
            verified.sort(
                key=lambda item: (
                    item[1]["total"] or 0
                ),
                reverse=True,
            )

            best_url, best = (
                verified[0]
            )

            print()
            print(
                "RESULT: VERIFIED"
            )

            print(
                "VERIFIED WORKDAY URL:",
                best_url,
            )

            print(
                "VERIFIED API:",
                best["api"],
            )

            print(
                "TOTAL MATCHES:",
                best["total"],
            )

            verified_count += 1

        else:
            print()
            print(
                "RESULT: NO_VALID_CXS"
            )

    print()
    print("=" * 100)
    print(
        "VERIFIED:",
        verified_count,
        "/",
        len(TARGETS),
    )


if __name__ == "__main__":
    main()
