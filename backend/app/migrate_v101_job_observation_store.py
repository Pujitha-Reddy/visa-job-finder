from __future__ import annotations

from app.database import get_connection


OBSERVATION_COLUMNS = {
    "ingestion_run_id": "INTEGER",
    "provider_source_id": "TEXT",
    "employer_identity_id": "INTEGER",
    "employer_resolution_method": "TEXT",
    "employer_resolution_confidence": "REAL DEFAULT 0",
    "canonical_job_id": "INTEGER",
    "normalization_status": "TEXT DEFAULT 'PENDING'",
    "canonicalization_status": "TEXT DEFAULT 'PENDING'",
    "last_error": "TEXT",
}


def columns(conn, table):
    return {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }


def main():
    with get_connection() as conn:

        # ==================================================
        # INGESTION RUNS
        # ==================================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                provider TEXT NOT NULL,
                provider_source_id TEXT,

                transport_type TEXT,
                batch_name TEXT,

                status TEXT NOT NULL DEFAULT 'RUNNING',

                started_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                finished_at TEXT,

                raw_found INTEGER NOT NULL DEFAULT 0,
                observations_inserted INTEGER NOT NULL DEFAULT 0,
                observations_updated INTEGER NOT NULL DEFAULT 0,
                observations_failed INTEGER NOT NULL DEFAULT 0,

                employers_resolved INTEGER NOT NULL DEFAULT 0,
                employers_unresolved INTEGER NOT NULL DEFAULT 0,

                canonical_jobs_created INTEGER NOT NULL DEFAULT 0,
                canonical_jobs_updated INTEGER NOT NULL DEFAULT 0,

                error TEXT,
                metadata_json TEXT
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_ingestion_runs_provider
            ON ingestion_runs(provider)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_ingestion_runs_status
            ON ingestion_runs(status)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_ingestion_runs_started
            ON ingestion_runs(started_at)
        """)

        # ==================================================
        # JOB OBSERVATIONS
        # ==================================================

        existing = columns(
            conn,
            "job_observations",
        )

        if not existing:
            raise RuntimeError(
                "job_observations does not exist. "
                "Run V100 first."
            )

        added = []

        for name, ddl in OBSERVATION_COLUMNS.items():
            if name in existing:
                continue

            conn.execute(
                f"""
                ALTER TABLE job_observations
                ADD COLUMN "{name}" {ddl}
                """
            )

            added.append(name)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_observations_run
            ON job_observations(ingestion_run_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_observations_identity
            ON job_observations(employer_identity_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_observations_status
            ON job_observations(
                normalization_status,
                canonicalization_status
            )
        """)

        conn.commit()

    print("=" * 72)
    print("V101 JOB OBSERVATION STORE COMPLETE")
    print("=" * 72)
    print("ADDED OBSERVATION COLUMNS:", added)


if __name__ == "__main__":
    main()
