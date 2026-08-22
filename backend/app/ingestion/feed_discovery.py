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
    "Accept": "*/*",
}


FEED_PATTERNS = (
    r'https?://[^"\'\s<>]+\.xml(?:\?[^"\'\s<>]*)?',
    r'https?://[^"\'\s<>]+\.json(?:\?[^"\'\s<>]*)?',
    r'https?://[^"\'\s<>]+/api/[^"\'\s<>]+',
    r'https?://[^"\'\s<>]+/jobs/api[^"\'\s<>]*',
    r'https?://[^"\'\s<>]+/api/jobs[^"\'\s<>]*',
    r'https?://[^"\'\s<>]+/jobs/feed[^"\'\s<>]*',
    r'https?://[^"\'\s<>]+/jobs\.xml[^"\'\s<>]*',
)


COMMON_PATHS = (
    "/jobs.xml",
    "/jobs.json",
    "/jobs/feed",
    "/feed/jobs",
    "/api/jobs",
    "/jobs/api",
    "/careers/jobs.json",
    "/careers/jobs.xml",
)


@dataclass
class FeedCandidate:
    url: str
    feed_type: str
    confidence: float
    method: str


def classify_url(url):
    lower = (
        url
        or ""
    ).lower()

    if (
        ".xml" in lower
        or "/feed" in lower
        or "rss" in lower
        or "atom" in lower
    ):
        return "XML"

    if (
        ".json" in lower
        or "/api/" in lower
        or "/api/jobs" in lower
    ):
        return "JSON"

    return "UNKNOWN"


def root_url(value):
    parsed = urlparse(
        value
    )

    if not (
        parsed.scheme
        and parsed.netloc
    ):
        return None

    return (
        f"{parsed.scheme}://"
        f"{parsed.netloc}"
    )


def discover_feed_candidates(
    seed_url,
):
    session = requests.Session()
    session.headers.update(
        HEADERS
    )

    found = {}

    try:
        r = session.get(
            seed_url,
            timeout=20,
        )

        r.raise_for_status()

    except Exception as exc:
        return [], repr(exc)

    final_url = r.url

    soup = BeautifulSoup(
        r.text,
        "html.parser",
    )

    # ======================================================
    # HTML alternate links
    # ======================================================

    for link in soup.find_all(
        "link",
        href=True,
    ):
        rel = " ".join(
            link.get(
                "rel",
                [],
            )
        ).lower()

        content_type = (
            link.get("type")
            or ""
        ).lower()

        if (
            "alternate" not in rel
            and "rss" not in content_type
            and "atom" not in content_type
            and "json" not in content_type
        ):
            continue

        url = urljoin(
            final_url,
            link["href"],
        )

        feed_type = classify_url(
            url
        )

        if (
            "rss" in content_type
            or "atom" in content_type
        ):
            feed_type = "XML"

        found[url] = FeedCandidate(
            url=url,
            feed_type=feed_type,
            confidence=0.90,
            method="HTML_ALTERNATE",
        )

    # ======================================================
    # Raw HTML / script endpoint extraction
    # ======================================================

    body = r.text

    for pattern in FEED_PATTERNS:
        for match in re.findall(
            pattern,
            body,
            flags=re.IGNORECASE,
        ):
            url = match.replace(
                "\\/",
                "/",
            )

            found[url] = FeedCandidate(
                url=url,
                feed_type=classify_url(
                    url
                ),
                confidence=0.75,
                method="HTML_ENDPOINT",
            )

    # ======================================================
    # Common machine-readable endpoints
    #
    # Candidates only. Verification happens separately.
    # ======================================================

    root = root_url(
        final_url
    )

    if root:
        for path in COMMON_PATHS:
            url = urljoin(
                root,
                path,
            )

            if url in found:
                continue

            found[url] = FeedCandidate(
                url=url,
                feed_type=classify_url(
                    url
                ),
                confidence=0.35,
                method="COMMON_PATH",
            )

    return list(
        found.values()
    ), None
