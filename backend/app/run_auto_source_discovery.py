from __future__ import annotations

import argparse

from app.database import get_connection
from app.source_discovery_engine import (
    SourceDiscoveryEngine,
)



def parse_args():
    parser = argparse.ArgumentParser(
        description="Run automatic ATS/source discovery."
    )

    parser.add_argument(
        "--batch-name",
        default="SPONSOR_EXPANSION_V1",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    engine = SourceDiscoveryEngine()

    with get_connection() as c:
        rows = c.execute("""
            SELECT
                display_name,
                discovered_careers_url,
                resolution_status,
                source_discovery_score
            FROM source_discovery_batches
            WHERE batch_name=?
              AND resolution_status='PENDING'
            ORDER BY
                source_discovery_score DESC,
                display_name
        """, (
            args.batch_name,
        )).fetchall()

    print(
        "PENDING:",
        len(rows),
    )

    for row in rows:
        name = row["display_name"]

        # For now use existing seed from your prior discovery logic.
        # If none exists, we'll add domain discovery in the next step.
        seed = row[
            "discovered_careers_url"
        ]

        if not seed:
            print()
            print("=" * 100)
            print("COMPANY:", name)
            print("NO SEED URL")
            continue

        print()
        print("=" * 100)
        print("COMPANY:", name)
        print("SEED:", seed)

        candidates = engine.discover(
            name,
            seed,
        )

        for candidate in candidates[:10]:
            print(
                f"{candidate.confidence:>3} | "
                f"{candidate.source_type:<18} | "
                f"{candidate.ats or '-':<15} | "
                f"{candidate.careers_url}"
            )
            print(
                "    ",
                candidate.evidence,
            )


if __name__ == "__main__":
    main()