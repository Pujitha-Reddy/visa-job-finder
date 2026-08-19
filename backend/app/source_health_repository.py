from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .postgres_repository import pg_conn


def make_source_key(source: dict) -> str:
    """
    Stable operational identity for a configured collection source.

    We intentionally do not depend on the local SQLite source_id because
    CI environments may rebuild the registry.
    """
    parts = [
        str(source.get("employer_name") or "").strip().lower(),
        str(source.get("ats") or "").strip().upper(),
        str(source.get("token") or "").strip().lower(),
        str(source.get("careers_url") or "").strip().lower(),
    ]

    raw = "|".join(parts)

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()[:32]


def _metadata(source: dict):
    return {
        "source_key": make_source_key(source),
        "employer_name": source.get("employer_name") or "",
        "source_type": source.get("source_type"),
        "ats": (source.get("ats") or "").upper(),
        "token": source.get("token"),
        "careers_url": source.get("careers_url"),
    }


def ensure_source(source: dict):
    m = _metadata(source)

    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO source_health (
                source_key,
                employer_name,
                source_type,
                ats,
                token,
                careers_url,
                enabled,
                source_verified,
                updated_at
            )
            VALUES (
                %(source_key)s,
                %(employer_name)s,
                %(source_type)s,
                %(ats)s,
                %(token)s,
                %(careers_url)s,
                TRUE,
                TRUE,
                NOW()
            )
            ON CONFLICT (source_key)
            DO UPDATE SET
                employer_name=EXCLUDED.employer_name,
                source_type=EXCLUDED.source_type,
                ats=EXCLUDED.ats,
                token=EXCLUDED.token,
                careers_url=EXCLUDED.careers_url,
                enabled=TRUE,
                source_verified=TRUE,
                updated_at=NOW()
            """,
            m,
        )

        conn.commit()

    return m["source_key"]


def record_source_success(
    source: dict,
    *,
    raw_jobs: int,
    eligible_jobs: int,
    excluded_jobs: int,
    added_jobs: int,
    updated_jobs: int,
    disappeared_jobs: int = 0,
    started_at=None,
    duration_ms: int | None = None,
):
    source_key = ensure_source(source)

    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE source_health
            SET last_attempt_at=NOW(),
                last_success_at=NOW(),

                last_raw_jobs=%s,
                last_eligible_jobs=%s,
                last_excluded_jobs=%s,
                last_added_jobs=%s,
                last_updated_jobs=%s,
                last_disappeared_jobs=%s,

                consecutive_failures=0,
                last_error=NULL,

                source_verified=TRUE,
                updated_at=NOW()
            WHERE source_key=%s
            """,
            (
                raw_jobs,
                eligible_jobs,
                excluded_jobs,
                added_jobs,
                updated_jobs,
                disappeared_jobs,
                source_key,
            ),
        )

        cur.execute(
            """
            INSERT INTO source_run_history (
                source_key,
                started_at,
                completed_at,
                success,
                raw_jobs,
                eligible_jobs,
                excluded_jobs,
                added_jobs,
                updated_jobs,
                disappeared_jobs,
                duration_ms
            )
            VALUES (
                %s,
                COALESCE(%s, NOW()),
                NOW(),
                TRUE,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                source_key,
                started_at,
                raw_jobs,
                eligible_jobs,
                excluded_jobs,
                added_jobs,
                updated_jobs,
                disappeared_jobs,
                duration_ms,
            ),
        )

        conn.commit()


def record_source_failure(
    source: dict,
    *,
    error: str,
    started_at=None,
    duration_ms: int | None = None,
):
    source_key = ensure_source(source)

    error = str(error or "")[:4000]

    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE source_health
            SET last_attempt_at=NOW(),
                last_failure_at=NOW(),
                consecutive_failures=consecutive_failures + 1,
                last_error=%s,
                updated_at=NOW()
            WHERE source_key=%s
            """,
            (
                error,
                source_key,
            ),
        )

        cur.execute(
            """
            INSERT INTO source_run_history (
                source_key,
                started_at,
                completed_at,
                success,
                error_message,
                duration_ms
            )
            VALUES (
                %s,
                COALESCE(%s, NOW()),
                NOW(),
                FALSE,
                %s,
                %s
            )
            """,
            (
                source_key,
                started_at,
                error,
                duration_ms,
            ),
        )

        conn.commit()


def _status(row: dict, stale_after_hours: int = 24):
    if not row.get("enabled"):
        return "DISABLED", "Source disabled"

    if not row.get("source_verified"):
        return "UNVERIFIED", "Source not verified"

    failures = int(
        row.get("consecutive_failures") or 0
    )

    if failures >= 3:
        return (
            "FAILING",
            f"{failures} consecutive collection failures",
        )

    if failures > 0:
        return (
            "DEGRADED",
            f"{failures} recent collection failure(s)",
        )

    if (
        row.get("last_success_at")
        and int(row.get("last_raw_jobs") or 0) == 0
    ):
        return (
            "ZERO_RESULTS",
            "Last successful collection returned zero jobs",
        )

    age = row.get("success_age_hours")

    if (
        age is not None
        and float(age) > stale_after_hours
    ):
        return (
            "STALE",
            f"Last success was {float(age):.1f} hours ago",
        )

    if not row.get("last_success_at"):
        return (
            "NEVER_RUN",
            "No successful collection recorded yet",
        )

    return "HEALTHY", "Source operating normally"


def fetch_source_health(
    *,
    stale_after_hours: int = 24,
):
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                sh.*,

                CASE
                    WHEN sh.last_success_at IS NULL THEN NULL
                    ELSE EXTRACT(
                        EPOCH FROM (
                            NOW() - sh.last_success_at
                        )
                    ) / 3600.0
                END AS success_age_hours,

                (
                    SELECT COUNT(*)
                    FROM source_run_history sr
                    WHERE sr.source_key=sh.source_key
                      AND sr.completed_at >= NOW() - INTERVAL '24 hours'
                ) AS runs_24h,

                (
                    SELECT COUNT(*)
                    FROM source_run_history sr
                    WHERE sr.source_key=sh.source_key
                      AND sr.success=FALSE
                      AND sr.completed_at >= NOW() - INTERVAL '24 hours'
                ) AS failures_24h

            FROM source_health sh

            ORDER BY
                LOWER(sh.employer_name),
                sh.ats
            """
        )

        rows = cur.fetchall()

    output = []

    for raw in rows:
        row = dict(raw)

        # Tokens are collector configuration and should never be
        # exposed through the admin HTTP API.
        row.pop("token", None)

        status, reason = _status(
            row,
            stale_after_hours,
        )

        row["health_status"] = status
        row["health_reason"] = reason

        output.append(row)

    return output


def fetch_source_health_summary(
    *,
    stale_after_hours: int = 24,
):
    rows = fetch_source_health(
        stale_after_hours=stale_after_hours,
    )

    statuses = {}

    for row in rows:
        key = row["health_status"]

        statuses[key] = (
            statuses.get(key, 0)
            + 1
        )

    latest_success = None

    for row in rows:
        value = row.get("last_success_at")

        if value is None:
            continue

        if (
            latest_success is None
            or value > latest_success
        ):
            latest_success = value

    return {
        "sources": len(rows),
        "verified_sources": sum(
            1
            for x in rows
            if x.get("source_verified")
        ),
        "enabled_sources": sum(
            1
            for x in rows
            if x.get("enabled")
        ),
        "healthy": statuses.get("HEALTHY", 0),
        "degraded": statuses.get("DEGRADED", 0),
        "failing": statuses.get("FAILING", 0),
        "zero_results": statuses.get("ZERO_RESULTS", 0),
        "stale": statuses.get("STALE", 0),
        "never_run": statuses.get("NEVER_RUN", 0),
        "disabled": statuses.get("DISABLED", 0),
        "unverified": statuses.get("UNVERIFIED", 0),
        "latest_success_at": latest_success,
    }


def fetch_source_runs(
    source_key: str,
    limit: int = 20,
):
    limit = max(
        1,
        min(int(limit), 100),
    )

    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT *
            FROM source_run_history
            WHERE source_key=%s
            ORDER BY completed_at DESC
            LIMIT %s
            """,
            (
                source_key,
                limit,
            ),
        )

        return cur.fetchall()
