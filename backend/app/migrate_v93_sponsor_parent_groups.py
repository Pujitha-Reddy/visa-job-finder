from __future__ import annotations

from .database import get_connection


DDL = """
CREATE TABLE IF NOT EXISTS sponsor_parent_groups (
    parent_key TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,

    total_filings INTEGER NOT NULL DEFAULT 0,
    recent_filings INTEGER NOT NULL DEFAULT 0,

    legal_entity_count INTEGER NOT NULL DEFAULT 0,

    strongest_sponsor_strength TEXT NOT NULL DEFAULT 'UNKNOWN',
    highest_priority_score REAL NOT NULL DEFAULT 0,
    priority_band TEXT NOT NULL DEFAULT 'LOW',

    already_in_registry INTEGER NOT NULL DEFAULT 0,
    matched_employer_id INTEGER,

    source_resolution_status TEXT NOT NULL DEFAULT 'UNRESOLVED',

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sponsor_parent_members (
    parent_key TEXT NOT NULL,
    normalized_name TEXT NOT NULL,

    PRIMARY KEY (
        parent_key,
        normalized_name
    )
);

CREATE INDEX IF NOT EXISTS idx_sponsor_parent_priority
    ON sponsor_parent_groups(
        priority_score DESC
    );
"""


def main():
    with get_connection() as conn:
        # SQLite does not support invalid identifier above
        # if priority_score isn't a column. Create tables first.
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sponsor_parent_groups (
            parent_key TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,

            total_filings INTEGER NOT NULL DEFAULT 0,
            recent_filings INTEGER NOT NULL DEFAULT 0,

            legal_entity_count INTEGER NOT NULL DEFAULT 0,

            strongest_sponsor_strength TEXT NOT NULL DEFAULT 'UNKNOWN',
            highest_priority_score REAL NOT NULL DEFAULT 0,
            priority_band TEXT NOT NULL DEFAULT 'LOW',

            already_in_registry INTEGER NOT NULL DEFAULT 0,
            matched_employer_id INTEGER,

            source_resolution_status TEXT NOT NULL DEFAULT 'UNRESOLVED',

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sponsor_parent_members (
            parent_key TEXT NOT NULL,
            normalized_name TEXT NOT NULL,

            PRIMARY KEY (
                parent_key,
                normalized_name
            )
        );

        CREATE INDEX IF NOT EXISTS idx_sponsor_parent_priority
            ON sponsor_parent_groups(
                highest_priority_score DESC
            );
        """)

        conn.commit()

    print(
        "V9.3 sponsor parent-group migration complete."
    )


if __name__ == "__main__":
    main()
