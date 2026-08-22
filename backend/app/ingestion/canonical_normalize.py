from __future__ import annotations

import hashlib
import re
from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)


TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "source",
    "src",
    "ref",
    "referrer",
}


def clean_text(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def normalize_title(value):
    value = clean_text(
        value
    ).lower()

    value = value.replace(
        "&",
        " and ",
    )

    value = re.sub(
        r"[^a-z0-9+#./]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def normalize_location(value):
    value = clean_text(
        value
    ).lower()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def normalize_external_id(value):
    value = clean_text(
        value
    )

    if not value:
        return ""

    return value.lower()


def normalize_job_url(value):
    value = clean_text(
        value
    )

    if not value:
        return ""

    try:
        parsed = urlsplit(
            value
        )

        query = [
            (k, v)
            for k, v in parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
            if k.lower()
            not in TRACKING_PARAMS
        ]

        return urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path.rstrip("/"),
                urlencode(query),
                "",
            )
        )

    except Exception:
        return value


def hash_key(value):
    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


def canonical_key_for_observation(
    observation,
):
    employer_id = observation[
        "employer_identity_id"
    ]

    external_id = (
        normalize_external_id(
            observation[
                "provider_job_id"
            ]
        )
    )

    # ==================================================
    # Strongest:
    # resolved employer + provider's stable job ID.
    #
    # Provider name is intentionally NOT included.
    # This lets identical external IDs from two
    # observations potentially converge.
    # ==================================================

    if external_id:
        raw = (
            f"EMP:{employer_id}"
            f"|EXT:{external_id}"
        )

        return (
            hash_key(raw),
            "EMPLOYER_EXTERNAL_ID",
            1.0,
        )

    # ==================================================
    # Employer + normalized apply/source URL
    # ==================================================

    url = normalize_job_url(
        observation["apply_url"]
        or observation["source_url"]
    )

    if url:
        raw = (
            f"EMP:{employer_id}"
            f"|URL:{url}"
        )

        return (
            hash_key(raw),
            "EMPLOYER_JOB_URL",
            0.98,
        )

    # ==================================================
    # Fallback:
    # employer + title + location
    #
    # Less confident because employers may have multiple
    # openings sharing a title/location.
    # ==================================================

    title = normalize_title(
        observation["title_raw"]
    )

    location = normalize_location(
        observation["location_raw"]
    )

    raw = (
        f"EMP:{employer_id}"
        f"|TITLE:{title}"
        f"|LOCATION:{location}"
    )

    return (
        hash_key(raw),
        "EMPLOYER_TITLE_LOCATION",
        0.80,
    )
