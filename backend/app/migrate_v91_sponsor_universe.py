from __future__ import annotations

from .database import get_connection


DDL = """
CREATE TABLE IF NOT EXISTS sponsor_employer_universe (
    normalized_name TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,

    latest_year INTEGER,
    total_filings INTEGER NOT NULL DEFAULT 0,
    recent_filings INTEGER NOT NULL DEFAULT 0,

    approved_count INTEGER NOT NULL DEFAULT 0,
    denied_count INTEGER NOT NULL DEFAULT 0,

    sponsor_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

    dol_present INTEGER NOT NULL DEFAULT 0,
    uscis_present INTEGER NOT NULL DEFAULT 0,

    matched_employer_id INTEGER,
    already_in_registry INTEGER NOT NULL DEFAULT 0,

    careers_url TEXT,
    careers_url_status TEXT NOT NULL DEFAULT 'UNKNOWN',

    ats_candidate TEXT,
    source_resolution_status TEXT NOT NULL DEFAULT 'UNRESOLVED',

    priority_score REAL NOT NULL DEFAULT 0,
    priority_band TEXT NOT NULL DEFAULT 'LOW',

    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_ranked_at TEXT,

    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_sponsor_universe_priority
    ON sponsor_employer_universe(priority_score DESC);

CREATE INDEX IF NOT EXISTS idx_sponsor_universe_strength
    ON sponsor_employer_universe(sponsor_strength);

CREATE INDEX IF NOT EXISTS idx_sponsor_universe_registry
    ON sponsor_employer_universe(already_in_registry);

CREATE INDEX IF NOT EXISTS idx_sponsor_universe_resolution
    ON sponsor_employer_universe(source_resolution_status);
"""


def main():
    with get_connection() as conn:
        conn.executescript(DDL)
        conn.commit()

    print("V9.1 sponsor employer universe migration complete.")


if __name__ == "__main__":
    main()
