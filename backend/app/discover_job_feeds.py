from __future__ import annotations

import argparse

from app.database import (
    get_connection,
)

from app.ingestion.feed_discovery import (
    discover_feed_candidates,
)

from app.ingestion.feed_verifier import (
    verify_feed,
)


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--batch-name",
        default="SPONSOR_EXPANSION_V2",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=50,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                b.display_name,
                b.parent_key,

                COALESCE(
                    b.discovered_careers_url,
                    b.careers_candidate_url
                ) AS seed_url,

                i.id AS employer_identity_id

            FROM source_discovery_batches b

            LEFT JOIN employer_identities i
              ON i.sponsor_parent_key =
                 b.parent_key

            WHERE b.batch_name=?
              AND COALESCE(
                    b.discovered_careers_url,
                    b.careers_candidate_url
                  ) IS NOT NULL

            ORDER BY
                b.source_discovery_score DESC,
                b.display_name

            LIMIT ?
        """, (
            args.batch_name,
            args.limit,
        )).fetchall()

    print(
        "FEED DISCOVERY TARGETS:",
        len(rows),
    )

    totals = {
        "employers": len(rows),
        "candidates": 0,
        "verified": 0,
        "errors": 0,
    }

    for row in rows:

        print()
        print("=" * 100)

        print(
            "EMPLOYER:",
            row["display_name"],
        )

        print(
            "SEED:",
            row["seed_url"],
        )

        candidates, error = (
            discover_feed_candidates(
                row["seed_url"]
            )
        )

        if error:
            totals["errors"] += 1

            print(
                "DISCOVERY ERROR:",
                error,
            )

            continue

        totals[
            "candidates"
        ] += len(candidates)

        verified_count = 0

        for candidate in candidates:
            result = verify_feed(
                candidate.url,
                candidate.feed_type,
            )

            if not result[
                "verified"
            ]:
                continue

            verified_count += 1

            totals[
                "verified"
            ] += 1

            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO
                    discovered_job_feeds (
                        employer_identity_id,
                        employer_name,
                        seed_url,
                        feed_url,
                        feed_type,
                        confidence,
                        discovery_method,
                        verification_status
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?,
                        'VERIFIED'
                    )

                    ON CONFLICT(
                        employer_name,
                        feed_url
                    )
                    DO UPDATE SET
                        employer_identity_id=
                            excluded.employer_identity_id,

                        feed_type=
                            excluded.feed_type,

                        confidence=
                            MAX(
                                discovered_job_feeds.confidence,
                                excluded.confidence
                            ),

                        discovery_method=
                            excluded.discovery_method,

                        verification_status=
                            'VERIFIED',

                        updated_at=
                            CURRENT_TIMESTAMP
                """, (
                    row[
                        "employer_identity_id"
                    ],

                    row[
                        "display_name"
                    ],

                    row[
                        "seed_url"
                    ],

                    candidate.url,

                    result[
                        "feed_type"
                    ],

                    candidate.confidence,

                    candidate.method,
                ))

                conn.commit()

            print(
                "VERIFIED:",
                result[
                    "feed_type"
                ],
                "|",
                candidate.url,
                "| JOB-LIKE:",
                result[
                    "job_like_records"
                ],
            )

        print(
            "CANDIDATES:",
            len(candidates),
            "| VERIFIED:",
            verified_count,
        )

    print()
    print("=" * 100)
    print(
        "V105 FEED DISCOVERY SUMMARY"
    )
    print("=" * 100)
    print(totals)


if __name__ == "__main__":
    main()
