from __future__ import annotations

from .database import get_connection


DDL = """
DROP VIEW IF EXISTS combined_sponsor_discovery_queue;

CREATE VIEW combined_sponsor_discovery_queue AS

SELECT
    parent_key,
    display_name,

    dol_present,
    uscis_present,

    dol_recent_filings,
    dol_total_filings,

    uscis_active_years,
    uscis_2025_approvals,
    uscis_2026_approvals,

    uscis_total_approvals,
    uscis_total_denials,

    dol_strength,
    uscis_strength,

    combined_sponsor_score,
    combined_priority_band,

    CASE
        WHEN combined_sponsor_score >= 80
            THEN 'IMMEDIATE'

        WHEN combined_sponsor_score >= 60
            THEN 'HIGH'

        WHEN combined_sponsor_score >= 40
            THEN 'NORMAL'

        ELSE 'LOW'
    END AS discovery_priority,

    source_resolution_status

FROM combined_sponsor_universe

WHERE already_in_registry=0
  AND combined_sponsor_score >= 60
  AND source_resolution_status='UNRESOLVED';
"""


def main():
    with get_connection() as conn:
        conn.executescript(DDL)
        conn.commit()

    print(
        "V9.8 combined sponsor discovery queue created."
    )


if __name__ == "__main__":
    main()
