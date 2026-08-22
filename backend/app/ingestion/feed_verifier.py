from __future__ import annotations

import json

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(compatible; VisaJobFinder/1.0)"
    ),
    "Accept": (
        "application/json,"
        "application/xml,"
        "text/xml,"
        "application/rss+xml,"
        "*/*"
    ),
}


JOB_KEYS = {
    "title",
    "jobtitle",
    "job_title",

    "location",
    "locations",

    "description",
    "jobdescription",

    "url",
    "applyurl",
    "apply_url",

    "id",
    "jobid",
    "job_id",
}


def score_dict(value):
    if not isinstance(
        value,
        dict,
    ):
        return 0

    keys = {
        str(k).lower()
        for k in value.keys()
    }

    return len(
        keys
        & JOB_KEYS
    )


def walk_json(value):
    if isinstance(
        value,
        dict,
    ):
        yield value

        for item in value.values():
            yield from walk_json(
                item
            )

    elif isinstance(
        value,
        list,
    ):
        for item in value:
            yield from walk_json(
                item
            )


def verify_json(response):
    try:
        data = response.json()
    except Exception:
        return {
            "verified": False,
            "job_like_records": 0,
        }

    job_like = 0

    for obj in walk_json(
        data
    ):
        if score_dict(
            obj
        ) >= 3:
            job_like += 1

            if job_like >= 3:
                break

    return {
        "verified": (
            job_like >= 1
        ),
        "job_like_records": (
            job_like
        ),
    }


def verify_xml(response):
    try:
        soup = BeautifulSoup(
            response.text,
            "xml",
        )
    except Exception:
        return {
            "verified": False,
            "job_like_records": 0,
        }

    candidates = []

    for name in (
        "job",
        "item",
        "entry",
        "position",
        "vacancy",
    ):
        candidates.extend(
            soup.find_all(name)
        )

    job_like = 0

    for item in candidates[
        :100
    ]:
        text = item.get_text(
            " ",
            strip=True,
        ).lower()

        if (
            "title" in text
            or item.find("title")
        ):
            job_like += 1

    return {
        "verified": (
            job_like >= 1
        ),
        "job_like_records": (
            job_like
        ),
    }


def verify_feed(
    url,
    expected_type=None,
):
    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    try:
        r = session.get(
            url,
            timeout=20,
        )

        r.raise_for_status()

    except Exception as exc:
        return {
            "verified": False,
            "feed_type": (
                expected_type
                or "UNKNOWN"
            ),
            "job_like_records": 0,
            "error": repr(exc),
        }

    content_type = (
        r.headers.get(
            "content-type"
        )
        or ""
    ).lower()

    feed_type = (
        expected_type
        or "UNKNOWN"
    )

    if (
        "json"
        in content_type
    ):
        feed_type = "JSON"

    elif (
        "xml"
        in content_type
        or "rss"
        in content_type
        or "atom"
        in content_type
    ):
        feed_type = "XML"

    if feed_type == "JSON":
        result = verify_json(
            r
        )

    elif feed_type == "XML":
        result = verify_xml(
            r
        )

    else:
        # Try JSON first, then XML.
        result = verify_json(
            r
        )

        if not result[
            "verified"
        ]:
            result = verify_xml(
                r
            )

            if result[
                "verified"
            ]:
                feed_type = "XML"
        else:
            feed_type = "JSON"

    return {
        "verified": result[
            "verified"
        ],

        "feed_type": (
            feed_type
        ),

        "job_like_records": (
            result[
                "job_like_records"
            ]
        ),

        "error": None,
    }
