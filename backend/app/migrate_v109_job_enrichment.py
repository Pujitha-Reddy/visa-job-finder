from __future__ import annotations

from app.database import get_connection


def main():
    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS canonical_job_enrichment (
                canonical_job_id INTEGER PRIMARY KEY,

                -- ------------------------------------------
                -- Software-role classification
                -- ------------------------------------------
                is_software_role INTEGER,
                software_role_family TEXT,
                software_role_score REAL,
                software_role_reason TEXT,

                -- ------------------------------------------
                -- Location
                -- ------------------------------------------
                country_code TEXT,
                state_code TEXT,
                city TEXT,

                work_arrangement TEXT,

                is_us_job INTEGER,
                is_us_remote INTEGER,

                location_confidence REAL,
                location_reason TEXT,

                -- ------------------------------------------
                -- Experience
                -- ------------------------------------------
                min_experience_years REAL,
                max_experience_years REAL,

                seniority_band TEXT,
                experience_confidence REAL,
                experience_reason TEXT,

                -- ------------------------------------------
                -- Sponsorship
                -- ------------------------------------------
                sponsor_parent_key TEXT,

                sponsor_history_strength TEXT,
                sponsor_recent_filings INTEGER,
                sponsor_recent_approvals INTEGER,

                visa_language_status TEXT,
                visa_language_evidence TEXT,

                sponsorship_score REAL,
                sponsorship_reason TEXT,

                -- ------------------------------------------
                -- Eligibility
                -- ------------------------------------------
                is_eligible INTEGER,

                eligibility_reason TEXT,
                location_eligibility TEXT,
                experience_eligibility TEXT,
                sponsorship_eligibility TEXT,

                -- ------------------------------------------
                -- Ranking
                -- ------------------------------------------
                relevance_score REAL,
                freshness_score REAL,
                source_quality_score REAL,
                overall_score REAL,

                -- ------------------------------------------
                -- Processing
                -- ------------------------------------------
                enrichment_version TEXT NOT NULL
                    DEFAULT 'V109',

                enriched_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY(canonical_job_id)
                    REFERENCES canonical_jobs(id)
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_enrichment_software
            ON canonical_job_enrichment(
                is_software_role
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_enrichment_eligible
            ON canonical_job_enrichment(
                is_eligible
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_enrichment_score
            ON canonical_job_enrichment(
                overall_score DESC
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_job_enrichment_sponsor
            ON canonical_job_enrichment(
                sponsor_parent_key
            )
        """)

        conn.commit()

    print("=" * 80)
    print("V109 JOB ENRICHMENT MIGRATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
