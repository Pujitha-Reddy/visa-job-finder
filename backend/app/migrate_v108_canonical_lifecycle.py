from __future__ import annotations

from app.database import get_connection


def cols(conn, table):
    return {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }


def add_column(
    conn,
    table,
    name,
    ddl,
):
    existing = cols(
        conn,
        table,
    )

    if name in existing:
        return False

    conn.execute(
        f"""
        ALTER TABLE {table}
        ADD COLUMN "{name}" {ddl}
        """
    )

    return True


def main():
    added = []

    with get_connection() as conn:

        # ==================================================
        # Observation lifecycle
        # ==================================================

        for name, ddl in {
            "disappeared_at": "TEXT",
            "last_verified_at": "TEXT",
        }.items():
            if add_column(
                conn,
                "job_observations",
                name,
                ddl,
            ):
                added.append(
                    f"job_observations.{name}"
                )

        # ==================================================
        # Canonical lifecycle
        # ==================================================

        for name, ddl in {
            "active_source_count": (
                "INTEGER NOT NULL DEFAULT 1"
            ),
            "last_verified_at": "TEXT",
            "disappeared_at": "TEXT",
        }.items():
            if add_column(
                conn,
                "canonical_jobs",
                name,
                ddl,
            ):
                added.append(
                    f"canonical_jobs.{name}"
                )

        # ==================================================
        # Run lifecycle statistics
        # ==================================================

        for name, ddl in {
            "observations_deactivated": (
                "INTEGER NOT NULL DEFAULT 0"
            ),
            "canonical_jobs_deactivated": (
                "INTEGER NOT NULL DEFAULT 0"
            ),
        }.items():
            if add_column(
                conn,
                "ingestion_runs",
                name,
                ddl,
            ):
                added.append(
                    f"ingestion_runs.{name}"
                )

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_observations_provider_source_active
            ON job_observations(
                provider,
                provider_source_id,
                is_active
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_canonical_active_sources
            ON canonical_jobs(
                is_active,
                active_source_count
            )
        """)

        conn.commit()

    print("=" * 80)
    print(
        "V108 CANONICAL LIFECYCLE MIGRATION COMPLETE"
    )
    print("=" * 80)
    print(
        "ADDED:",
        added,
    )


if __name__ == "__main__":
    main()
