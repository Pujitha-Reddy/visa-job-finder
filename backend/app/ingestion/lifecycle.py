from __future__ import annotations

from app.database import get_connection


def finalize_source_snapshot(
    *,
    provider,
    provider_source_id,
    ingestion_run_id,
):
    """
    Finalize ONE successful provider/source snapshot.

    IMPORTANT:
    Call this only after a successful collection run.

    Jobs observed in the current run remain active.

    Older observations from this exact provider/source
    that were not seen in the current run become inactive.

    A failed provider run must never call this function.
    """

    provider = (
        provider
        or ""
    ).upper()

    provider_source_id = str(
        provider_source_id
        or ""
    )

    with get_connection() as conn:

        # --------------------------------------------------
        # Current snapshot = verified active
        # --------------------------------------------------

        conn.execute(
            """
            UPDATE job_observations
            SET
                is_active=1,
                disappeared_at=NULL,
                last_verified_at=
                    CURRENT_TIMESTAMP
            WHERE provider=?
              AND provider_source_id=?
              AND ingestion_run_id=?
            """,
            (
                provider,
                provider_source_id,
                ingestion_run_id,
            ),
        )

        # --------------------------------------------------
        # Previous observations not present in the
        # successful current snapshot disappear.
        # --------------------------------------------------

        cur = conn.execute(
            """
            UPDATE job_observations
            SET
                is_active=0,

                disappeared_at=
                    COALESCE(
                        disappeared_at,
                        CURRENT_TIMESTAMP
                    ),

                last_verified_at=
                    CURRENT_TIMESTAMP

            WHERE provider=?
              AND provider_source_id=?
              AND (
                    ingestion_run_id IS NULL
                    OR ingestion_run_id <> ?
                  )
              AND COALESCE(
                    is_active,
                    1
                  ) = 1
            """,
            (
                provider,
                provider_source_id,
                ingestion_run_id,
            ),
        )

        disappeared = (
            cur.rowcount
            if cur.rowcount
            and cur.rowcount > 0
            else 0
        )

        conn.commit()

    return {
        "observations_deactivated": (
            disappeared
        ),
    }


def refresh_canonical_lifecycle(
    canonical_job_ids=None,
):
    """
    Rebuild canonical lifecycle from observation lifecycle.

    Canonical job is active if at least one linked
    observation remains active.
    """

    with get_connection() as conn:

        if canonical_job_ids:
            ids = sorted({
                int(value)
                for value
                in canonical_job_ids
                if value is not None
            })

            if not ids:
                return {
                    "canonical_jobs_checked": 0,
                    "canonical_jobs_deactivated": 0,
                    "canonical_jobs_reactivated": 0,
                }

            placeholders = ",".join(
                "?"
                for _ in ids
            )

            rows = conn.execute(
                f"""
                SELECT *
                FROM canonical_jobs
                WHERE id IN (
                    {placeholders}
                )
                """,
                ids,
            ).fetchall()

        else:
            rows = conn.execute(
                """
                SELECT *
                FROM canonical_jobs
                ORDER BY id
                """
            ).fetchall()

        deactivated = 0
        reactivated = 0

        for job in rows:
            canonical_id = job[
                "id"
            ]

            aggregate = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_sources,

                    SUM(
                        CASE
                            WHEN COALESCE(
                                o.is_active,
                                1
                            ) = 1
                            THEN 1
                            ELSE 0
                        END
                    ) AS active_sources,

                    MAX(
                        o.last_seen_at
                    ) AS latest_seen,

                    MAX(
                        o.last_verified_at
                    ) AS latest_verified

                FROM canonical_job_sources s

                JOIN job_observations o
                  ON o.id =
                     s.observation_id

                WHERE s.canonical_job_id=?
                """,
                (
                    canonical_id,
                ),
            ).fetchone()

            active_sources = int(
                aggregate[
                    "active_sources"
                ]
                or 0
            )

            currently_active = int(
                job[
                    "is_active"
                ]
                or 0
            )

            new_active = (
                1
                if active_sources > 0
                else 0
            )

            if (
                currently_active == 1
                and new_active == 0
            ):
                deactivated += 1

            elif (
                currently_active == 0
                and new_active == 1
            ):
                reactivated += 1

            conn.execute(
                """
                UPDATE canonical_jobs
                SET
                    is_active=?,

                    active_source_count=?,

                    source_count=(
                        SELECT COUNT(*)
                        FROM canonical_job_sources
                        WHERE canonical_job_id=?
                    ),

                    last_seen_at=
                        COALESCE(
                            ?,
                            last_seen_at
                        ),

                    last_verified_at=
                        COALESCE(
                            ?,
                            last_verified_at
                        ),

                    disappeared_at=
                        CASE
                            WHEN ?=1
                            THEN NULL

                            ELSE COALESCE(
                                disappeared_at,
                                CURRENT_TIMESTAMP
                            )
                        END,

                    freshness_status=
                        CASE
                            WHEN ?=1
                            THEN 'CURRENT'
                            ELSE 'INACTIVE'
                        END,

                    updated_at=
                        CURRENT_TIMESTAMP

                WHERE id=?
                """,
                (
                    new_active,
                    active_sources,
                    canonical_id,

                    aggregate[
                        "latest_seen"
                    ],

                    aggregate[
                        "latest_verified"
                    ],

                    new_active,
                    new_active,

                    canonical_id,
                ),
            )

            # Keep edge lifecycle synchronized with
            # its underlying observation.
            conn.execute(
                """
                UPDATE canonical_job_sources
                SET
                    is_active=(
                        SELECT
                            COALESCE(
                                o.is_active,
                                1
                            )
                        FROM job_observations o
                        WHERE o.id=
                              canonical_job_sources.observation_id
                    ),

                    last_seen_at=(
                        SELECT
                            o.last_seen_at
                        FROM job_observations o
                        WHERE o.id=
                              canonical_job_sources.observation_id
                    )

                WHERE canonical_job_id=?
                """,
                (
                    canonical_id,
                ),
            )

        conn.commit()

    return {
        "canonical_jobs_checked": (
            len(rows)
        ),
        "canonical_jobs_deactivated": (
            deactivated
        ),
        "canonical_jobs_reactivated": (
            reactivated
        ),
    }


def refresh_source_canonical_lifecycle(
    *,
    provider,
    provider_source_id,
):
    """
    Refresh only canonical jobs touched by one provider source.
    """

    provider = (
        provider
        or ""
    ).upper()

    provider_source_id = str(
        provider_source_id
        or ""
    )

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT
                canonical_job_id
            FROM job_observations
            WHERE provider=?
              AND provider_source_id=?
              AND canonical_job_id
                  IS NOT NULL
            """,
            (
                provider,
                provider_source_id,
            ),
        ).fetchall()

    ids = [
        row[
            "canonical_job_id"
        ]
        for row in rows
    ]

    return refresh_canonical_lifecycle(
        ids
    )
