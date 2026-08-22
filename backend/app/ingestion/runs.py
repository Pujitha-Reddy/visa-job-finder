from __future__ import annotations

import json

from app.database import get_connection


def start_run(
    *,
    provider,
    provider_source_id=None,
    transport_type=None,
    batch_name=None,
    metadata=None,
):
    metadata_json = None

    if metadata is not None:
        metadata_json = json.dumps(
            metadata,
            ensure_ascii=False,
            default=str,
        )

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO ingestion_runs (
                provider,
                provider_source_id,
                transport_type,
                batch_name,
                status,
                metadata_json
            )
            VALUES (?, ?, ?, ?, 'RUNNING', ?)
            """,
            (
                provider,
                provider_source_id,
                transport_type,
                batch_name,
                metadata_json,
            ),
        )

        conn.commit()

        return cur.lastrowid


def finish_run(
    run_id,
    *,
    status="SUCCESS",
    raw_found=0,
    inserted=0,
    updated=0,
    failed=0,
    employers_resolved=0,
    employers_unresolved=0,
    canonical_created=0,
    canonical_updated=0,
    error=None,
):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE ingestion_runs
            SET
                status=?,
                finished_at=CURRENT_TIMESTAMP,

                raw_found=?,
                observations_inserted=?,
                observations_updated=?,
                observations_failed=?,

                employers_resolved=?,
                employers_unresolved=?,

                canonical_jobs_created=?,
                canonical_jobs_updated=?,

                error=?

            WHERE id=?
            """,
            (
                status,
                raw_found,
                inserted,
                updated,
                failed,
                employers_resolved,
                employers_unresolved,
                canonical_created,
                canonical_updated,
                error,
                run_id,
            ),
        )

        conn.commit()


def fail_run(
    run_id,
    error,
):
    finish_run(
        run_id,
        status="FAILED",
        error=str(error),
    )
