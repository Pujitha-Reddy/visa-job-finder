from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import (
    urljoin,
    urlparse,
)

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; VisaJobFinder/1.0)"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/json,*/*"
    ),
}


@dataclass
class TransportCandidate:
    transport_type: str
    transport_url: str
    confidence: float
    method: str
    evidence: str


HOST_PATTERNS = (
    (
        "WORKDAY",
        (
            "myworkdayjobs.com",
        ),
        0.99,
    ),
    (
        "ASHBY",
        (
            "jobs.ashbyhq.com",
            "api.ashbyhq.com",
        ),
        0.99,
    ),
    (
        "ICIMS",
        (
            "icims.com",
            "careers.icims.com",
        ),
        0.99,
    ),
    (
        "GREENHOUSE",
        (
            "boards.greenhouse.io",
            "job-boards.greenhouse.io",
            "api.greenhouse.io",
        ),
        0.99,
    ),
    (
        "LEVER",
        (
            "jobs.lever.co",
            "api.lever.co",
        ),
        0.99,
    ),
    (
        "SMARTRECRUITERS",
        (
            "jobs.smartrecruiters.com",
            "api.smartrecruiters.com",
        ),
        0.99,
    ),
    (
        "EIGHTFOLD",
        (
            "eightfold.ai",
            "eightfold",
        ),
        0.95,
    ),
    (
        "PHENOM",
        (
            "phenompeople.com",
            "phenom.com",
        ),
        0.95,
    ),
    (
        "ORACLE_HCM",
        (
            "oraclecloud.com",
        ),
        0.92,
    ),
    (
        "RADANCY",
        (
            "radancy",
            "jobs2web",
        ),
        0.92,
    ),
    (
        "SUCCESSFACTORS",
        (
            "successfactors.com",
            "successfactors.eu",
        ),
        0.95,
    ),
    (
        "TALEO",
        (
            "taleo.net",
        ),
        0.95,
    ),
)


TEXT_PATTERNS = (
    (
        "WORKDAY",
        (
            r"myworkdayjobs\.com",
            r"/wday/cxs/",
        ),
        0.95,
    ),
    (
        "ASHBY",
        (
            r"ashbyhq\.com",
            r"api\.ashbyhq\.com",
        ),
        0.95,
    ),
    (
        "ICIMS",
        (
            r"\bicims\b",
            r"icims\.com",
        ),
        0.95,
    ),
    (
        "PHENOM",
        (
            r"\bphenom\b",
            r"phenompeople",
            r"phApp",
            r"ph-common",
        ),
        0.93,
    ),
    (
        "GREENHOUSE",
        (
            r"greenhouse\.io",
            r"boards-api\.greenhouse",
        ),
        0.95,
    ),
    (
        "LEVER",
        (
            r"lever\.co",
            r"api\.lever\.co",
        ),
        0.95,
    ),
    (
        "SMARTRECRUITERS",
        (
            r"smartrecruiters\.com",
        ),
        0.95,
    ),
    (
        "EIGHTFOLD",
        (
            r"\beightfold\b",
            r"eightfold\.ai",
        ),
        0.92,
    ),
    (
        "RADANCY",
        (
            r"\bradancy\b",
            r"search-jobs/results",
            r"resultspost",
        ),
        0.90,
    ),
    (
        "ORACLE_HCM",
        (
            r"oraclecloud\.com",
            r"/hcmRestApi/",
        ),
        0.92,
    ),
    (
        "SUCCESSFACTORS",
        (
            r"successfactors",
        ),
        0.92,
    ),
    (
        "TALEO",
        (
            r"taleo\.net",
            r"careersection",
        ),
        0.92,
    ),
)


API_PATTERNS = (
    r'https?://[^"\'\s<>]+/api/[^"\'\s<>]+',
    r'https?://[^"\'\s<>]+/graphql[^"\'\s<>]*',
    r'https?://[^"\'\s<>]+/wday/cxs/[^"\'\s<>]+',
    r'https?://[^"\'\s<>]+/hcmRestApi/[^"\'\s<>]+',
    r'https?://[^"\'\s<>]+/search-jobs/[^"\'\s<>]+',
)


def host(value):
    try:
        return (
            urlparse(value)
            .hostname
            or ""
        ).lower()
    except Exception:
        return ""


def add_candidate(
    bucket,
    candidate,
):
    key = (
        candidate.transport_type,
        candidate.transport_url,
    )

    existing = bucket.get(key)

    if (
        existing is None
        or candidate.confidence
        > existing.confidence
    ):
        bucket[key] = candidate


def classify_url(
    url,
    *,
    method="URL_HOST",
):
    hostname = host(url)

    results = []

    full_lower = (
        url
        or ""
    ).lower()

    for (
        transport,
        patterns,
        confidence,
    ) in HOST_PATTERNS:

        for pattern in patterns:
            if (
                pattern in hostname
                or pattern in full_lower
            ):
                results.append(
                    TransportCandidate(
                        transport_type=transport,
                        transport_url=url,
                        confidence=confidence,
                        method=method,
                        evidence=(
                            f"URL matched "
                            f"{transport}: {pattern}"
                        ),
                    )
                )

                break

    return results


def extract_urls(
    html,
    base_url,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    urls = set()

    for tag in soup.find_all(
        ["a", "script", "iframe", "link"],
    ):
        value = (
            tag.get("href")
            or tag.get("src")
        )

        if not value:
            continue

        try:
            urls.add(
                urljoin(
                    base_url,
                    value,
                )
            )
        except Exception:
            pass

    for pattern in API_PATTERNS:
        for value in re.findall(
            pattern,
            html,
            flags=re.IGNORECASE,
        ):
            urls.add(
                value.replace(
                    "\\/",
                    "/",
                )
            )

    return urls


def discover_dynamic_transports(
    *,
    seed_url,
    prior_ats=None,
):
    candidates = {}

    errors = []

    # ==================================================
    # 1. Prior verified/detected ATS evidence
    # ==================================================

    if prior_ats:
        add_candidate(
            candidates,
            TransportCandidate(
                transport_type=(
                    prior_ats.upper()
                ),
                transport_url=seed_url,
                confidence=0.98,
                method="PRIOR_ATS_EVIDENCE",
                evidence=(
                    "Previously detected ATS "
                    f"{prior_ats}"
                ),
            ),
        )

    # ==================================================
    # 2. Seed URL itself
    # ==================================================

    for candidate in classify_url(
        seed_url,
        method="SEED_URL",
    ):
        add_candidate(
            candidates,
            candidate,
        )

    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    try:
        r = session.get(
            seed_url,
            timeout=20,
            allow_redirects=True,
        )

        r.raise_for_status()

    except Exception as exc:
        errors.append(
            repr(exc)
        )

        return (
            list(
                candidates.values()
            ),
            errors,
        )

    final_url = r.url

    # ==================================================
    # 3. Redirect/final URL
    # ==================================================

    for candidate in classify_url(
        final_url,
        method="FINAL_URL",
    ):
        add_candidate(
            candidates,
            candidate,
        )

    html = r.text

    # ==================================================
    # 4. ATS fingerprints in HTML/JS
    # ==================================================

    for (
        transport,
        patterns,
        confidence,
    ) in TEXT_PATTERNS:

        for pattern in patterns:
            if re.search(
                pattern,
                html,
                flags=re.IGNORECASE,
            ):
                add_candidate(
                    candidates,
                    TransportCandidate(
                        transport_type=transport,
                        transport_url=final_url,
                        confidence=confidence,
                        method="HTML_FINGERPRINT",
                        evidence=(
                            f"HTML matched "
                            f"{transport}: {pattern}"
                        ),
                    ),
                )

                break

    # ==================================================
    # 5. Links, scripts, iframe and API URLs
    # ==================================================

    discovered_urls = (
        extract_urls(
            html,
            final_url,
        )
    )

    for url in discovered_urls:
        for candidate in classify_url(
            url,
            method="DISCOVERED_URL",
        ):
            add_candidate(
                candidates,
                candidate,
            )

    # ==================================================
    # 6. Unknown API candidates
    #
    # These are transport clues only.
    # They are NOT considered verified job APIs yet.
    # ==================================================

    for url in discovered_urls:
        lower = url.lower()

        if not (
            "/api/" in lower
            or "/graphql" in lower
            or "/wday/cxs/" in lower
            or "/hcmrestapi/" in lower
            or "/search-jobs/" in lower
        ):
            continue

        recognized = (
            classify_url(
                url,
                method="API_URL",
            )
        )

        if recognized:
            continue

        add_candidate(
            candidates,
            TransportCandidate(
                transport_type="CUSTOM_API",
                transport_url=url,
                confidence=0.55,
                method="API_URL",
                evidence=(
                    "Unclassified API-like "
                    f"endpoint: {url}"
                ),
            ),
        )

    return (
        sorted(
            candidates.values(),
            key=lambda c: (
                -c.confidence,
                c.transport_type,
                c.transport_url,
            ),
        ),
        errors,
    )
