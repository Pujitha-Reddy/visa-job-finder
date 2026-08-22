from __future__ import annotations

from .database import get_connection


DDL = """
CREATE TABLE IF NOT EXISTS uscis_h1b_employer_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    normalized_name TEXT NOT NULL,
    display_name TEXT NOT NULL,

    fiscal_year INTEGER NOT NULL,

    employer_city TEXT,
    employer_state TEXT,
    employer_zip TEXT,

    initial_approvals INTEGER NOT NULL DEFAULT 0,
    initial_denials INTEGER NOT NULL DEFAULT 0,

    continuing_approvals INTEGER NOT NULL DEFAULT 0,
    continuing_denials INTEGER NOT NULL DEFAULT 0,

    total_approvals INTEGER NOT NULL DEFAULT 0,
    total_denials INTEGER NOT NULL DEFAULT 0,

    source TEXT NOT NULL DEFAULT 'USCIS_H1B_EMPLOYER_DATA_HUB',
    source_file TEXT,

    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (
        normalized_name,
        fiscal_year,
        employer_city,
        employer_state,
        employer_zip
    )
);


CREATE TABLE IF NOT EXISTS uscis_h1b_rollup (
    normalized_name TEXT PRIMARY KEY,

    display_name TEXT NOT NULL,

    latest_year INTEGER,

    initial_approvals INTEGER NOT NULL DEFAULT 0,
    initial_denials INTEGER NOT NULL DEFAULT 0,

    continuing_approvals INTEGER NOT NULL DEFAULT 0,
    continuing_denials INTEGER NOT NULL DEFAULT 0,

    total_approvals INTEGER NOT NULL DEFAULT 0,
    total_denials INTEGER NOT NULL DEFAULT 0,

    recent_approvals INTEGER NOT NULL DEFAULT 0,

    approval_rate REAL,

    uscis_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

    last_verified_at TEXT DEFAULT CURRENT_TIMESTAMP
);


CREATE INDEX IF NOT EXISTS idx_uscis_history_name
    ON uscis_h1b_employer_history(normalized_name);

CREATE INDEX IF NOT EXISTS idx_uscis_history_year
    ON uscis_h1b_employer_history(fiscal_year);

CREATE INDEX IF NOT EXISTS idx_uscis_rollup_approvals
    ON uscis_h1b_rollup(total_approvals DESC);

CREATE INDEX IF NOT EXISTS idx_uscis_rollup_recent
    ON uscis_h1b_rollup(recent_approvals DESC);
"""


def main():
    with get_connection() as conn:
        conn.executescript(DDL)
        conn.commit()

    print("V9.5 USCIS H-1B schema complete.")


if __name__ == "__main__":
    main()
