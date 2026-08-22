from __future__ import annotations

import json

from app.database import get_connection
from app.ingestion.models import JobObservation
from app.ingestion.normalize import (
    observation_key,
    payload_hash,
)


def save_observation(
    observation: JobObservation,
    *,
    ingestion_run_id=None,
):
    key = observation_key(
        observation
    )

    raw_json = None

    if observation.raw_payload is not None:
        raw_json = json.dumps(
            observation.raw_payload,
            ensure_ascii=False,
            default=str,
        )

    raw_hash = payload_hash(
        observation.raw_payload
    )

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM job_observations
            WHERE observation_key=?
            """,
            (key,),
        ).fetchone()

        values = (
            ingestion_run_id,
            observation.provider_source_id,
            observation.provider_job_id,

            observation.source_type,
            observation.transport_type,

            observation.source_url,
            observation.apply_url,

            observation.company_name_raw,
            observation.company_domain,

            observation.title_raw,
            observation.location_raw,
            observation.description_raw,

            observation.posted_at,

            raw_json,
            raw_hash,

            observation.source_confidence_score,
        )

        if existing:
            conn.execute(
                """
                UPDATE job_observations
                SET
                    ingestion_run_id=?,
                    provider_source_id=?,
                    provider_job_id=?,

                    source_type=?,
                    transport_type=?,

                    source_url=?,
                    apply_url=?,

                    company_name_raw=?,
                    company_domain=?,

                    title_raw=?,
                    location_raw=?,
                    description_raw=?,

                    posted_at=?,

                    raw_payload_json=?,
                    payload_hash=?,

                    source_confidence_score=?,

                    last_seen_at=CURRENT_TIMESTAMP,
                    is_active=1,
                    last_error=NULL

                WHERE id=?
                """,
                values + (
                    existing["id"],
                ),
            )

            conn.commit()

            return {
                "id": existing["id"],
                "action": "UPDATED",
            }

        cur = conn.execute(
            """
            INSERT INTO job_observations (
                observation_key,

                ingestion_run_id,

                provider,
                provider_source_id,
                provider_job_id,

                source_type,
                transport_type,

                source_url,
                apply_url,

                company_name_raw,
                company_domain,

                title_raw,
                location_raw,
                description_raw,

                posted_at,

                raw_payload_json,
                payload_hash,

                source_confidence_score
            )
            VALUES (
                ?,
                ?,
                ?, ?, ?,
                ?, ?,
                ?, ?,
                ?, ?,
                ?, ?, ?,
                ?,
                ?, ?,
                ?
            )
            """,
            (
                key,
                ingestion_run_id,

                observation.provider,
                observation.provider_source_id,
                observation.provider_job_id,

                observation.source_type,
                observation.transport_type,

                observation.source_url,
                observation.apply_url,

                observation.company_name_raw,
                observation.company_domain,

                observation.title_raw,
                observation.location_raw,
                observation.description_raw,

                observation.posted_at,

                raw_json,
                raw_hash,

                observation.source_confidence_score,
            ),
        )

        conn.commit()

        return {
            "id": cur.lastrowid,
            "action": "INSERTED",
        }


def save_observations(
    observations,
    *,
    ingestion_run_id=None,
):
    totals = {
        "seen": 0,
        "inserted": 0,
        "updated": 0,
        "errors": 0,
    }

    for observation in observations:
        totals["seen"] += 1

        try:
            result = save_observation(
                observation,
                ingestion_run_id=(
                    ingestion_run_id
                ),
            )

            if result["action"] == "INSERTED":
                totals["inserted"] += 1
            else:
                totals["updated"] += 1

        except Exception as exc:
            totals["errors"] += 1

            print(
                "[OBSERVATION SAVE ERROR]",
                observation.provider,
                "/",
                observation.company_name_raw,
                "/",
                observation.title_raw,
                ":",
                repr(exc),
            )

    return totals
