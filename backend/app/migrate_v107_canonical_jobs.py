from __future__ import annotations

from app.database import get_connection


def main():
    with get_connection() as conn:

        # ==================================================
        # Canonical job
        #
        # One real-world posting regardless of how many
        # providers observed it.
        # ==================================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS canonical_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                canonical_key TEXT NOT NULL UNIQUE,

                employer_identity_id INTEGER NOT NULL,

                canonical_title TEXT NOT NULL,
                canonical_location TEXT,

                description TEXT,

                preferred_source_url TEXT,
                preferred_apply_url TEXT,

                external_id TEXT,

                posted_at TEXT,

                first_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                last_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                is_active INTEGER NOT NULL DEFAULT 1,

                source_count INTEGER NOT NULL DEFAULT 1,

                best_source_confidence REAL
                    NOT NULL DEFAULT 0,

                canonicalization_confidence REAL
                    NOT NULL DEFAULT 0,

                freshness_status TEXT
                    NOT NULL DEFAULT 'CURRENT',

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_canonical_jobs_employer
            ON canonical_jobs(
                employer_identity_id
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_canonical_jobs_active
            ON canonical_jobs(
                is_active
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_canonical_jobs_posted
            ON canonical_jobs(
                posted_at
            )
        """)

        # ==================================================
        # Observation → canonical-job edges
        # ==================================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS
            canonical_job_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                canonical_job_id INTEGER NOT NULL,
                observation_id INTEGER NOT NULL UNIQUE,

                provider TEXT NOT NULL,

                source_confidence REAL
                    NOT NULL DEFAULT 0,

                match_method TEXT NOT NULL,

                match_confidence REAL
                    NOT NULL DEFAULT 0,

                first_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                last_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                is_active INTEGER NOT NULL DEFAULT 1,

                FOREIGN KEY(
                    canonical_job_id
                )
                REFERENCES canonical_jobs(id),

                FOREIGN KEY(
                    observation_id
                )
                REFERENCES job_observations(id)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_canonical_job_sources_job
            ON canonical_job_sources(
                canonical_job_id
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_canonical_job_sources_provider
            ON canonical_job_sources(
                provider
            )
        """)

        conn.commit()

    print(
        "V107 CANONICAL JOB MIGRATION COMPLETE"
    )


if __name__ == "__main__":
    main()
