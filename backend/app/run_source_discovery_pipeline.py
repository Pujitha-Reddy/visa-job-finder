from __future__ import annotations

import argparse

from collections import Counter

from app.database import get_connection
from app.source_discovery_engine import (
    SourceDiscoveryEngine,
)



def parse_args():
    parser = argparse.ArgumentParser(
        description="Run this pipeline for a specific source-discovery batch."
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
                id,
                display_name,
                careers_discovery_status,
                careers_candidate_url,
                careers_discovery_score,
                source_discovery_score
            FROM source_discovery_batches
            WHERE batch_name=?
              AND resolution_status='PENDING'
              AND careers_candidate_url IS NOT NULL
              AND careers_discovery_status IN (
                    'VERIFIED',
                    'DISCOVERED_UNVERIFIED'
              )
            ORDER BY
                source_discovery_score DESC,
                display_name
        """, (args.batch_name,)).fetchall()

    print(
        "SOURCE DISCOVERY TARGETS:",
        len(rows),
    )

    summaries = []

    for row in rows:
        name = row["display_name"]
        careers_url = (
            row["careers_candidate_url"]
        )

        print()
        print("=" * 110)
        print("EMPLOYER:", name)
        print(
            "CAREERS STATUS:",
            row[
                "careers_discovery_status"
            ],
        )
        print(
            "CAREERS SCORE:",
            row[
                "careers_discovery_score"
            ],
        )
        print(
            "CAREERS:",
            careers_url,
        )

        candidates = engine.discover(
            name,
            careers_url,
        )

        if not candidates:
            print(
                "SOURCE RESULT: NONE"
            )

            summaries.append({
                "name": name,
                "ats": None,
                "confidence": 0,
                "url": careers_url,
                "type": "NONE",
            })

            continue

        print()
        print("=== SOURCE CANDIDATES ===")

        for candidate in candidates[:10]:
            print(
                f"{candidate.confidence:>3} | "
                f"{candidate.source_type:<18} | "
                f"{candidate.ats or '-':<16} | "
                f"{candidate.careers_url}"
            )

            print(
                "    ",
                candidate.evidence,
            )

        best = candidates[0]

        summaries.append({
            "name": name,
            "ats": best.ats,
            "confidence":
                best.confidence,
            "url":
                best.careers_url,
            "type":
                best.source_type,
        })

    print()
    print("=" * 110)
    print("SOURCE DISCOVERY SUMMARY")
    print("=" * 110)

    counts = Counter()

    for item in summaries:
        key = (
            item["ats"]
            or item["type"]
        )

        counts[key] += 1

        print(
            f"{item['name']:<42} | "
            f"{item['confidence']:>3} | "
            f"{item['ats'] or '-':<16} | "
            f"{item['type']:<18} | "
            f"{item['url']}"
        )

    print()
    print("=== SOURCE FAMILY COUNTS ===")

    for key, count in (
        counts.most_common()
    ):
        print(
            f"{key:<20}",
            count,
        )


if __name__ == "__main__":
    main()