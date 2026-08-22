from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlsplit, urlunsplit

from app.ingestion.models import JobObservation


def clean_text(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def normalize_url(value):
    value = clean_text(value)

    if not value:
        return ""

    try:
        parsed = urlsplit(value)

        return urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path,
                parsed.query,
                "",
            )
        )

    except Exception:
        return value


def payload_hash(payload):
    if not payload:
        return None

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def observation_key(
    observation: JobObservation,
):
    provider = clean_text(
        observation.provider
    ).lower()

    provider_job_id = clean_text(
        observation.provider_job_id
    )

    if provider_job_id:
        value = (
            f"{provider}:id:{provider_job_id}"
        )

    else:
        source_url = normalize_url(
            observation.source_url
        )

        value = (
            f"{provider}:url:{source_url}"
        )

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()
