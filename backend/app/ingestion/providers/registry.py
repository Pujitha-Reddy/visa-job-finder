from __future__ import annotations

from dataclasses import dataclass

from urllib.parse import urlparse

from app.collectors.factory import get_collector
from app.ingestion.models import JobObservation, CollectionResult


CONFIDENCE_BY_ATS = {
    "GREENHOUSE": 95,
    "ASHBY": 95,
    "LEVER": 95,
    "SMARTRECRUITERS": 95,
    "WORKDAY": 95,
    "WORKABLE": 95,
    "EIGHTFOLD": 92,
    "RADANCY": 92,
    "RADANCY_SAS": 92,
    "ADP": 92,
    "ORACLE_HCM": 92,
    "AMAZON": 95,
    "GENERIC": 80,
}


def domain(url):
    if not url:
        return None

    try:
        return urlparse(url).hostname
    except Exception:
        return None


def raw_to_observation(
    source,
    raw,
):
    ats = (
        source.get("ats")
        or "UNKNOWN"
    ).upper()

    provider_job_id = (
        raw.get("external_id")
        or raw.get("job_id")
        or raw.get("id")
    )

    return JobObservation(
        provider=ats,

        provider_source_id=str(
            source.get("source_id")
            or ""
        ),

        provider_job_id=(
            str(provider_job_id)
            if provider_job_id is not None
            else None
        ),

        source_type=(
            raw.get("source_type")
            or "DIRECT_EMPLOYER"
        ),

        transport_type=ats,

        source_url=(
            raw.get("source_url")
            or raw.get("apply_url")
            or ""
        ),

        apply_url=raw.get(
            "apply_url"
        ),

        company_name_raw=(
            raw.get("company_name_raw")
            or source.get("employer_name")
            or ""
        ),

        company_domain=domain(
            raw.get("source_url")
            or source.get("careers_url")
        ),

        title_raw=(
            raw.get("title")
            or ""
        ),

        location_raw=raw.get(
            "location_raw"
        ),

        description_raw=raw.get(
            "description"
        ),

        posted_at=(
            raw.get("posted_at")
            or raw.get("source_published_at")
        ),

        source_confidence_score=(
            CONFIDENCE_BY_ATS.get(
                ats,
                75,
            )
        ),

        raw_payload=dict(raw),
    )



@dataclass
class CollectedSource:
    observations: list[JobObservation]

    snapshot_complete: bool = False

    records_scanned: int | None = None
    expected_total: int | None = None
    pages_completed: int | None = None
    termination_reason: str | None = None



def collect_source(
    source,
):
    collector = get_collector(
        source["ats"]
    )

    if not collector:
        raise RuntimeError(
            f"No collector for ATS "
            f"{source['ats']}"
        )

    raw_result = collector.fetch(
        source
    )

    # ------------------------------------------------------
    # Backwards compatibility
    #
    # Existing collectors still return list[dict].
    # They remain ingestible, but they are NOT trusted as
    # complete snapshots until explicitly migrated.
    # ------------------------------------------------------

    if isinstance(
        raw_result,
        CollectionResult,
    ):
        raw_jobs = raw_result.jobs

        snapshot_complete = (
            raw_result.snapshot_complete
        )

        records_scanned = (
            raw_result.records_scanned
        )

        expected_total = (
            raw_result.expected_total
        )

        pages_completed = (
            raw_result.pages_completed
        )

        termination_reason = (
            raw_result.termination_reason
        )

    else:
        raw_jobs = raw_result or []

        snapshot_complete = False

        records_scanned = len(
            raw_jobs
        )

        expected_total = None
        pages_completed = None

        termination_reason = (
            "LEGACY_COLLECTOR_UNDECLARED"
        )

    observations = []

    for raw in raw_jobs:
        observation = raw_to_observation(
            source,
            raw,
        )

        if (
            not observation.source_url
            or not observation.company_name_raw
            or not observation.title_raw
        ):
            continue

        observations.append(
            observation
        )

    return CollectedSource(
        observations=observations,

        snapshot_complete=(
            snapshot_complete
        ),

        records_scanned=(
            records_scanned
        ),

        expected_total=(
            expected_total
        ),

        pages_completed=(
            pages_completed
        ),

        termination_reason=(
            termination_reason
        ),
    )
