from __future__ import annotations

from app.database import get_connection


def main():
    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS transport_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                employer_identity_id INTEGER,
                employer_name TEXT NOT NULL,

                seed_url TEXT NOT NULL,

                transport_type TEXT NOT NULL,
                transport_url TEXT,

                confidence REAL NOT NULL DEFAULT 0,

                discovery_method TEXT,
                evidence TEXT,

                verification_status TEXT NOT NULL
                    DEFAULT 'UNVERIFIED',

                enabled INTEGER NOT NULL DEFAULT 1,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(
                    employer_name,
                    transport_type,
                    transport_url
                )
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_transport_candidates_type
            ON transport_candidates(
                transport_type
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_transport_candidates_identity
            ON transport_candidates(
                employer_identity_id
            )
        """)

        conn.commit()

    print(
        "V105B TRANSPORT DISCOVERY MIGRATION COMPLETE"
    )


if __name__ == "__main__":
    main()
