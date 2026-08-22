from __future__ import annotations

import argparse

from app.database import (
    get_connection,
)

from app.ingestion.canonical_repository import (
    canonicalize_observation,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Canonicalize employer-resolved "
            "job observations."
        )
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

    clauses = [
        "employer_identity_id IS NOT NULL",
    ]

    if not args.force:
        clauses.append(
            "canonical_job_id IS NULL"
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
            WHERE {
                ' AND '.join(
                    clauses
                )
            }
            ORDER BY id
            {limit_sql}
            """
        ).fetchall()

    print(
        "OBSERVATIONS TO CANONICALIZE:",
        len(rows),
    )

    totals = {
        "inserted": 0,
        "updated": 0,
        "errors": 0,
    }

    methods = {}

    for row in rows:
        try:
            result = (
                canonicalize_observation(
                    row
                )
            )

            action = result[
                "action"
            ]

            if action == "INSERTED":
                totals[
                    "inserted"
                ] += 1
            else:
                totals[
                    "updated"
                ] += 1

            method = result[
                "match_method"
            ]

            methods[
                method
            ] = (
                methods.get(
                    method,
                    0,
                )
                + 1
            )

        except Exception as exc:
            totals[
                "errors"
            ] += 1

            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE job_observations
                    SET
                        canonicalization_status=
                            'ERROR',

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
                "[CANONICALIZATION ERROR]",
                row["id"],
                repr(exc),
            )

    print()
    print("=" * 80)
    print(
        "V107 CANONICALIZATION SUMMARY"
    )
    print("=" * 80)
    print(totals)

    print()
    print("=== MATCH METHODS ===")

    for method, n in sorted(
        methods.items(),
        key=lambda x: (
            -x[1],
            x[0],
        ),
    ):
        print(
            f"{n:>7} | {method}"
        )


if __name__ == "__main__":
    main()
