from __future__ import annotations

import argparse

from .database import get_connection


EXCLUDED_BANDS = {
    "UNIVERSITY_RESEARCH",
}



def parse_args():
    parser = argparse.ArgumentParser(
        description="Create a sponsor source-discovery batch."
    )

    parser.add_argument(
        "--batch-name",
        default="SPONSOR_EXPANSION_V1",
        help="Unique source-discovery batch name.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum employers to select.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_discovery_batches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                batch_name TEXT NOT NULL,

                parent_key TEXT NOT NULL,
                display_name TEXT NOT NULL,

                combined_sponsor_score REAL NOT NULL,
                employer_relevance_band TEXT,
                source_discovery_score REAL NOT NULL,

                dol_recent_filings INTEGER NOT NULL DEFAULT 0,
                uscis_2025_approvals INTEGER NOT NULL DEFAULT 0,
                uscis_2026_approvals INTEGER NOT NULL DEFAULT 0,

                resolution_status TEXT NOT NULL DEFAULT 'PENDING',

                discovered_careers_url TEXT,
                discovered_ats TEXT,
                discovered_token TEXT,

                verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',

                notes TEXT,

                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(batch_name, parent_key)
            )
        """)

        candidates = [
            dict(r)
            for r in conn.execute("""
                SELECT
                    parent_key,
                    display_name,
                    combined_sponsor_score,
                    employer_relevance_band,
                    source_discovery_score,
                    dol_recent_filings,
                    uscis_2025_approvals,
                    uscis_2026_approvals
                FROM combined_sponsor_universe AS u
                WHERE u.already_in_registry=0
                  AND u.combined_sponsor_score >= 60
                  AND u.source_resolution_status='UNRESOLVED'

                  -- Never put the same sponsor parent into
                  -- another discovery batch.
                  AND NOT EXISTS (
                      SELECT 1
                      FROM source_discovery_batches AS b
                      WHERE b.parent_key = u.parent_key
                  )

                ORDER BY
                    source_discovery_score DESC,
                    combined_sponsor_score DESC,
                    uscis_2025_approvals DESC,
                    dol_recent_filings DESC
            """).fetchall()
        ]

        selected = []

        for row in candidates:
            if row["employer_relevance_band"] in EXCLUDED_BANDS:
                continue

            selected.append(row)

            if len(selected) >= args.limit:
                break

        batch_name = args.batch_name

        for row in selected:
            conn.execute("""
                INSERT OR IGNORE INTO source_discovery_batches (
                    batch_name,
                    parent_key,
                    display_name,

                    combined_sponsor_score,
                    employer_relevance_band,
                    source_discovery_score,

                    dol_recent_filings,
                    uscis_2025_approvals,
                    uscis_2026_approvals
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                batch_name,
                row["parent_key"],
                row["display_name"],

                row["combined_sponsor_score"],
                row["employer_relevance_band"],
                row["source_discovery_score"],

                row["dol_recent_filings"],
                row["uscis_2025_approvals"],
                row["uscis_2026_approvals"],
            ))

        conn.commit()

    print("BATCH:", batch_name)
    print("SELECTED:", len(selected))

    print()
    print("=== SOURCE DISCOVERY BATCH ===")

    for i, row in enumerate(selected, 1):
        print(
            f"{i:>2}. "
            f"{row['source_discovery_score']:>5.1f} | "
            f"{row['employer_relevance_band']:<18} | "
            f"{row['display_name']}"
        )


if __name__ == "__main__":
    main()
