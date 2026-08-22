from __future__ import annotations

from .database import get_connection


def main():
    with get_connection() as conn:
        # We currently only have FY2026 and still possess the raw source
        # file, so rebuild cleanly rather than carrying forward a
        # potentially lossy uniqueness constraint.

        conn.execute("DROP TABLE IF EXISTS uscis_h1b_employer_history")

        conn.execute("""
            CREATE TABLE uscis_h1b_employer_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                normalized_name TEXT NOT NULL,
                display_name TEXT NOT NULL,
                fiscal_year INTEGER NOT NULL,

                employer_city TEXT,
                employer_state TEXT,
                employer_zip TEXT,

                tax_id TEXT,
                naics_code TEXT,

                new_employment_approvals INTEGER NOT NULL DEFAULT 0,
                new_employment_denials INTEGER NOT NULL DEFAULT 0,

                continuation_approvals INTEGER NOT NULL DEFAULT 0,
                continuation_denials INTEGER NOT NULL DEFAULT 0,

                same_employer_approvals INTEGER NOT NULL DEFAULT 0,
                same_employer_denials INTEGER NOT NULL DEFAULT 0,

                new_concurrent_approvals INTEGER NOT NULL DEFAULT 0,
                new_concurrent_denials INTEGER NOT NULL DEFAULT 0,

                change_employer_approvals INTEGER NOT NULL DEFAULT 0,
                change_employer_denials INTEGER NOT NULL DEFAULT 0,

                amended_approvals INTEGER NOT NULL DEFAULT 0,
                amended_denials INTEGER NOT NULL DEFAULT 0,

                initial_approvals INTEGER NOT NULL DEFAULT 0,
                initial_denials INTEGER NOT NULL DEFAULT 0,

                continuing_approvals INTEGER NOT NULL DEFAULT 0,
                continuing_denials INTEGER NOT NULL DEFAULT 0,

                total_approvals INTEGER NOT NULL DEFAULT 0,
                total_denials INTEGER NOT NULL DEFAULT 0,

                source TEXT NOT NULL
                    DEFAULT 'USCIS_H1B_EMPLOYER_DATA_HUB',

                source_file TEXT,
                source_row_number INTEGER,

                row_fingerprint TEXT NOT NULL UNIQUE,

                imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX idx_uscis_history_name
            ON uscis_h1b_employer_history(normalized_name)
        """)

        conn.execute("""
            CREATE INDEX idx_uscis_history_year
            ON uscis_h1b_employer_history(fiscal_year)
        """)

        conn.commit()

    print("V9.7 USCIS fingerprint schema complete.")


if __name__ == "__main__":
    main()
