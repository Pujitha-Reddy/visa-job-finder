from __future__ import annotations

import argparse

from app.database import get_connection
from app.ingestion.employer_resolver import (
    resolve_observation,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Resolve raw job observations "
            "to canonical employer identities."
        )
    )

    parser.add_argument(
        "--run-id",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--force",
        action="store_true",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    clauses = []

    params = []

    if not args.force:
        clauses.append(
            "employer_identity_id "
            "IS NULL"
        )

    if args.run_id is not None:
        clauses.append(
            "ingestion_run_id=?"
        )
        params.append(
            args.run_id
        )

    where_sql = ""

    if clauses:
        where_sql = (
            "WHERE "
            + " AND ".join(
                clauses
            )
        )

    limit_sql = ""

    if args.limit:
        limit_sql = (
            f"LIMIT {int(args.limit)}"
        )

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM job_observations
            {where_sql}
            ORDER BY id
            {limit_sql}
            """,
            params,
        ).fetchall()

    print(
        "OBSERVATIONS TO RESOLVE:",
        len(rows),
    )

    totals = {
        "resolved": 0,
        "unresolved": 0,
        "errors": 0,
    }

    method_counts = {}

    for row in rows:
        try:
            result = (
                resolve_observation(
                    row
                )
            )

            method = result[
                "method"
            ]

            method_counts[
                method
            ] = (
                method_counts.get(
                    method,
                    0,
                )
                + 1
            )

            resolved = (
                result[
                    "employer_identity_id"
                ]
                is not None
            )

            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE job_observations
                    SET
                        employer_identity_id=?,
                        employer_resolution_method=?,
                        employer_resolution_confidence=?,
                        normalization_status=
                            CASE
                                WHEN ?
                                THEN 'EMPLOYER_RESOLVED'
                                ELSE 'EMPLOYER_UNRESOLVED'
                            END,
                        last_error=NULL
                    WHERE id=?
                    """,
                    (
                        result[
                            "employer_identity_id"
                        ],
                        method,
                        result[
                            "confidence"
                        ],
                        1 if resolved else 0,
                        row["id"],
                    ),
                )

                conn.commit()

            if resolved:
                totals[
                    "resolved"
                ] += 1
            else:
                totals[
                    "unresolved"
                ] += 1

        except Exception as exc:
            totals["errors"] += 1

            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE job_observations
                    SET
                        normalization_status='ERROR',
                        last_error=?
                    WHERE id=?
                    """,
                    (
                        repr(exc),
                        row["id"],
                    ),
                )

                conn.commit()

            print(
                "[RESOLUTION ERROR]",
                row["id"],
                repr(exc),
            )

    # Update matching ingestion-run metrics.
    if args.run_id is not None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE ingestion_runs
                SET
                    employers_resolved=?,
                    employers_unresolved=?
                WHERE id=?
                """,
                (
                    totals[
                        "resolved"
                    ],
                    totals[
                        "unresolved"
                    ],
                    args.run_id,
                ),
            )

            conn.commit()

    print()
    print("=" * 80)
    print(
        "EMPLOYER RESOLUTION SUMMARY"
    )
    print("=" * 80)
    print(totals)

    print()
    print("=== METHODS ===")

    for method, count in sorted(
        method_counts.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print(
            f"{count:>6} | {method}"
        )


if __name__ == "__main__":
    main()
