from __future__ import annotations

import argparse

from app.database import (
    get_connection,
)

from app.ingestion.dynamic_transport_discovery import (
    discover_dynamic_transports,
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
        default=100,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                b.id AS batch_id,
                b.display_name,
                b.parent_key,

                COALESCE(
                    b.discovered_careers_url,
                    b.careers_candidate_url
                ) AS seed_url,

                b.discovered_ats,

                i.id AS employer_identity_id

            FROM source_discovery_batches b

            LEFT JOIN employer_identities i
              ON i.sponsor_parent_key =
                 b.parent_key

            WHERE b.batch_name=?

              AND b.resolution_status
                  <> 'PROMOTED'

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
        "DYNAMIC TRANSPORT TARGETS:",
        len(rows),
    )

    totals = {
        "employers": len(rows),
        "candidates": 0,
        "platforms_found": 0,
        "fetch_errors": 0,
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

        candidates, errors = (
            discover_dynamic_transports(
                seed_url=row["seed_url"],
                prior_ats=(
                    row["discovered_ats"]
                ),
            )
        )

        if errors:
            totals[
                "fetch_errors"
            ] += len(errors)

            print(
                "FETCH ERROR:",
                errors[0],
            )

        if candidates:
            totals[
                "platforms_found"
            ] += 1

        totals[
            "candidates"
        ] += len(candidates)

        for candidate in candidates:

            with get_connection() as conn:
                conn.execute("""
                    INSERT INTO
                    transport_candidates (
                        employer_identity_id,
                        employer_name,

                        seed_url,

                        transport_type,
                        transport_url,

                        confidence,

                        discovery_method,
                        evidence
                    )

                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?
                    )

                    ON CONFLICT(
                        employer_name,
                        transport_type,
                        transport_url
                    )

                    DO UPDATE SET
                        employer_identity_id=
                            excluded.employer_identity_id,

                        confidence=
                            MAX(
                                transport_candidates.confidence,
                                excluded.confidence
                            ),

                        discovery_method=
                            excluded.discovery_method,

                        evidence=
                            excluded.evidence,

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

                    candidate.transport_type,

                    candidate.transport_url,

                    candidate.confidence,

                    candidate.method,

                    candidate.evidence,
                ))

                conn.commit()

            print(
                f"{candidate.confidence:.2f}",
                "|",
                candidate.transport_type,
                "|",
                candidate.method,
                "|",
                candidate.transport_url,
            )

    print()
    print("=" * 100)

    print(
        "V105B DYNAMIC TRANSPORT SUMMARY"
    )

    print("=" * 100)

    print(totals)


if __name__ == "__main__":
    main()
