from __future__ import annotations

from app.database import get_connection


def _columns(conn, table):
    return {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({table})"
        ).fetchall()
    }


def main():
    with get_connection() as conn:

        # ==================================================
        # Raw job observations
        #
        # Every provider writes here FIRST.
        # No eligibility filtering happens at ingestion.
        # ==================================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                observation_key TEXT NOT NULL UNIQUE,

                provider TEXT NOT NULL,
                provider_job_id TEXT,

                source_type TEXT NOT NULL,
                transport_type TEXT,

                source_url TEXT NOT NULL,
                apply_url TEXT,

                company_name_raw TEXT NOT NULL,
                company_domain TEXT,

                title_raw TEXT NOT NULL,
                location_raw TEXT,
                description_raw TEXT,

                posted_at TEXT,

                raw_payload_json TEXT,
                payload_hash TEXT,

                sponsor_parent_key TEXT,
                sponsor_match_confidence REAL DEFAULT 0,

                canonical_job_id INTEGER,

                source_confidence_score REAL DEFAULT 0,

                first_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                last_seen_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_observations_company
            ON job_observations(company_name_raw)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_observations_sponsor
            ON job_observations(sponsor_parent_key)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_observations_provider
            ON job_observations(provider)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_observations_canonical
            ON job_observations(canonical_job_id)
        """)

        # ==================================================
        # Employer identity aliases
        #
        # Legal sponsor name
        # brand name
        # parent company
        # raw job-board company name
        # all resolve to one sponsor parent_key
        # ==================================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS employer_identity_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                parent_key TEXT NOT NULL,

                alias_name TEXT NOT NULL,
                normalized_alias TEXT NOT NULL,

                alias_type TEXT NOT NULL
                    DEFAULT 'SPONSOR_NAME',

                domain TEXT,

                confidence REAL NOT NULL DEFAULT 1.0,

                source TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(parent_key, normalized_alias)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_employer_alias_normalized
            ON employer_identity_aliases(normalized_alias)
        """)

        # ==================================================
        # Source transport registry
        #
        # Important:
        # sources are PLATFORM/TRANSPORT records,
        # not necessarily company-specific collectors.
        # ==================================================

        conn.execute("""
            CREATE TABLE IF NOT EXISTS job_transports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                transport_key TEXT NOT NULL UNIQUE,

                employer_parent_key TEXT,

                provider TEXT NOT NULL,
                transport_type TEXT NOT NULL,

                base_url TEXT,
                token TEXT,

                confidence REAL DEFAULT 0,

                enabled INTEGER NOT NULL DEFAULT 1,

                last_success_at TEXT,
                last_failure_at TEXT,
                last_error TEXT,

                created_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_transports_parent
            ON job_transports(employer_parent_key)
        """)

        conn.commit()

    print("V100 UNIVERSAL INGESTION MIGRATION COMPLETE")


if __name__ == "__main__":
    main()
