from __future__ import annotations

import json
import re

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


TARGETS = [
    {
        "company": "eBay",
        "family": "PHENOM",
        "url": "https://jobs.ebayinc.com/us/en/jobs",
    },
    {
        "company": "HPE",
        "family": "PHENOM",
        "url": "https://careers.hpe.com/us/en/jobs",
    },
    {
        "company": "Arm",
        "family": "RADANCY",
        "url": "https://careers.arm.com/en/search-jobs/results",
    },
    {
        "company": "Synopsys, Inc.",
        "family": "RADANCY",
        "url": "https://careers.synopsys.com/search-jobs",
    },
    {
        "company": "ByteDance",
        "family": "BYTEDANCE",
        "url": "https://joinbytedance.com/search/job/posts",
    },
    {
        "company": "TikTok Inc.",
        "family": "BYTEDANCE",
        "url": "https://lifeattiktok.com/search/job/posts",
    },
    {
        "company": "ADP",
        "family": "ADP_CUSTOM",
        "url": "https://jobs.adp.com/en/jobs/?pagesize=20&page=1",
    },
]


def get(session, url):
    try:
        r = session.get(
            url,
            timeout=30,
            allow_redirects=True,
        )
        return r
    except Exception as exc:
        print("REQUEST ERROR:", repr(exc))
        return None


def looks_like_job(text):
    low = (text or "").lower()

    signals = [
        "software engineer",
        "software developer",
        "job title",
        "jobtitle",
        "job-title",
        "job location",
        "location",
        "requisition",
        "jobid",
        "job id",
    ]

    return any(
        signal in low
        for signal in signals
    )


def inspect_json(obj, depth=0):
    """
    Print useful structural hints without dumping
    a potentially enormous response.
    """
    if depth > 3:
        return

    if isinstance(obj, dict):
        print(
            "  " * depth,
            "DICT KEYS:",
            list(obj.keys())[:30],
        )

        for key, value in list(obj.items())[:15]:
            if isinstance(value, (dict, list)):
                print(
                    "  " * depth,
                    "->",
                    key,
                    type(value).__name__,
                )
                inspect_json(
                    value,
                    depth + 1,
                )

    elif isinstance(obj, list):
        print(
            "  " * depth,
            "LIST LEN:",
            len(obj),
        )

        if obj:
            inspect_json(
                obj[0],
                depth + 1,
            )


def extract_html_jobs(text):
    soup = BeautifulSoup(
        text,
        "html.parser",
    )

    candidates = []

    selectors = [
        "a[href*='/job/']",
        "a[href*='/jobs/']",
        "a[href*='jobdetail']",
        "a[href*='job-detail']",
        "[data-job-id]",
        "[data-jobid]",
        ".job",
        ".job-item",
        ".job-result",
        ".job-card",
        ".search-result",
    ]

    seen = set()

    for selector in selectors:
        try:
            nodes = soup.select(selector)
        except Exception:
            continue

        for node in nodes[:50]:
            title = " ".join(
                node.stripped_strings
            ).strip()

            href = None

            if node.name == "a":
                href = node.get("href")
            else:
                link = node.find("a")
                if link:
                    href = link.get("href")

            key = (
                title[:200],
                href,
            )

            if key in seen:
                continue

            seen.add(key)

            if title or href:
                candidates.append(
                    {
                        "title": title[:250],
                        "href": href,
                    }
                )

    return candidates


def probe(target):
    session = requests.Session()
    session.headers.update(HEADERS)

    print()
    print("=" * 100)
    print("COMPANY:", target["company"])
    print("FAMILY:", target["family"])
    print("URL:", target["url"])

    r = get(
        session,
        target["url"],
    )

    if r is None:
        return

    print("STATUS:", r.status_code)
    print("FINAL:", r.url)
    print(
        "CONTENT-TYPE:",
        r.headers.get(
            "content-type"
        ),
    )
    print(
        "BYTES:",
        len(r.content),
    )

    text = r.text or ""

    print(
        "JOB SIGNAL:",
        looks_like_job(text),
    )

    # --------------------------------------------------
    # JSON
    # --------------------------------------------------

    try:
        payload = r.json()

        print("JSON: YES")
        inspect_json(payload)

        compact = json.dumps(
            payload,
            ensure_ascii=False,
        )

        print(
            "JSON SOFTWARE SIGNAL:",
            "software" in compact.lower(),
        )

        return

    except Exception:
        print("JSON: NO")

    # --------------------------------------------------
    # HTML
    # --------------------------------------------------

    jobs = extract_html_jobs(text)

    print(
        "HTML JOB CANDIDATES:",
        len(jobs),
    )

    for job in jobs[:10]:
        print(
            " ",
            job["title"][:120],
            "|",
            job["href"],
        )

    # --------------------------------------------------
    # Useful embedded strings
    # --------------------------------------------------

    patterns = [
        r'https?://[^"\'\s<>]+',
        r'["\']([^"\']*(?:api|jobs|search)[^"\']*)["\']',
    ]

    interesting = []

    for pattern in patterns:
        for value in re.findall(
            pattern,
            text,
            flags=re.I,
        ):
            value = (
                value
                .replace("\\/", "/")
                .strip()
            )

            low = value.lower()

            if not any(
                word in low
                for word in (
                    "job",
                    "api",
                    "search",
                    "position",
                    "requisition",
                )
            ):
                continue

            if value not in interesting:
                interesting.append(value)

    print(
        "INTERESTING STRINGS:",
        len(interesting),
    )

    for value in interesting[:20]:
        print(
            " ",
            value[:300],
        )


def main():
    for target in TARGETS:
        probe(target)


if __name__ == "__main__":
    main()