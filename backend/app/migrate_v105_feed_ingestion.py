from __future__ import annotations

from app.database import get_connection


def main():
    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS discovered_job_feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                employer_identity_id INTEGER,
                employer_name TEXT NOT NULL,

                seed_url TEXT,
                feed_url TEXT NOT NULL,

                feed_type TEXT NOT NULL,

                confidence REAL NOT NULL
                    DEFAULT 0,

                discovery_method TEXT,

                enabled INTEGER NOT NULL
                    DEFAULT 1,

                verification_status TEXT NOT NULL
                    DEFAULT 'UNVERIFIED',

                last_run_at TEXT,
                last_job_count INTEGER NOT NULL
                    DEFAULT 0,

                last_error TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(
                    employer_name,
                    feed_url
                )
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_discovered_job_feeds_identity
            ON discovered_job_feeds(
                employer_identity_id
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_discovered_job_feeds_type
            ON discovered_job_feeds(
                feed_type
            )
        """)

        conn.commit()

    print(
        "V105 FEED INGESTION MIGRATION COMPLETE"
    )


if __name__ == "__main__":
    main()
