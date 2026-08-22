from __future__ import annotations

from .database import get_connection


DDL = """
DROP VIEW IF EXISTS sponsor_parent_discovery_queue;

CREATE VIEW sponsor_parent_discovery_queue AS

SELECT
    parent_key,
    display_name,

    total_filings,
    recent_filings,
    legal_entity_count,

    strongest_sponsor_strength,
    highest_priority_score,
    priority_band,

    matched_employer_id,
    already_in_registry,
    source_resolution_status,

    CASE
        WHEN priority_band='TIER_1'
            THEN 'IMMEDIATE'

        WHEN priority_band='TIER_2'
            THEN 'HIGH'

        ELSE 'NORMAL'
    END AS discovery_priority

FROM sponsor_parent_groups

WHERE already_in_registry=0
  AND priority_band IN (
      'TIER_1',
      'TIER_2'
  )
  AND source_resolution_status='UNRESOLVED';
"""


def main():
    with get_connection() as conn:
        conn.executescript(DDL)
        conn.commit()

    print(
        "V9.4 parent sponsor discovery queue created."
    )


if __name__ == "__main__":
    main()
