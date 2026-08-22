from __future__ import annotations

from .database import get_connection


DDL = """
DROP VIEW IF EXISTS sponsor_source_discovery_queue;

CREATE VIEW sponsor_source_discovery_queue AS

SELECT
    normalized_name,
    display_name,

    latest_year,
    total_filings,
    recent_filings,
    approved_count,
    denied_count,
    sponsor_strength,

    priority_score,
    priority_band,

    careers_url,
    careers_url_status,
    ats_candidate,
    source_resolution_status,

    CASE
        WHEN priority_band='TIER_1'
            THEN 'IMMEDIATE'
        WHEN priority_band='TIER_2'
            THEN 'HIGH'
        ELSE 'NORMAL'
    END AS discovery_priority

FROM sponsor_employer_universe

WHERE already_in_registry=0
  AND priority_band IN ('TIER_1', 'TIER_2')
  AND source_resolution_status='UNRESOLVED';
"""


def main():
    with get_connection() as conn:
        conn.executescript(DDL)
        conn.commit()

    print("V9.2 sponsor source discovery queue created.")


if __name__ == "__main__":
    main()
