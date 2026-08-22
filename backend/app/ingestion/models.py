from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class JobObservation:
    provider: str
    source_type: str
    transport_type: str

    source_url: str
    company_name_raw: str
    title_raw: str

    provider_source_id: str | None = None
    provider_job_id: str | None = None

    apply_url: str | None = None
    company_domain: str | None = None

    location_raw: str | None = None
    description_raw: str | None = None

    posted_at: str | None = None

    source_confidence_score: float = 0

    raw_payload: dict[str, Any] | None = None



@dataclass
class CollectionResult:
    """
    Provider collection result.

    jobs:
        Raw provider job dictionaries.

    snapshot_complete:
        True only when the collector can prove it enumerated
        the complete source snapshot exposed by that transport.

    A partial collection may still safely add/update jobs, but
    it must never deactivate jobs that were not observed.
    """

    jobs: list[dict[str, Any]]

    snapshot_complete: bool = False

    records_scanned: int | None = None
    expected_total: int | None = None
    pages_completed: int | None = None
    termination_reason: str | None = None
