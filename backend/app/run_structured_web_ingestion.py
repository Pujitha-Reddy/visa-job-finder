from __future__ import annotations

import argparse

from app.database import (
    get_connection,
)

from app.ingestion.providers.structured_web import (
    collect_structured_web,
)

from app.ingestion.repository import (
    save_observations,
)

from app.ingestion.runs import (
    start_run,
    finish_run,
    fail_run,
)


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--seed-id",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=25,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    clauses = [
        "enabled=1",
    ]

    params = []

    if args.seed_id:
        clauses.append(
            "id=?"
        )

        params.append(
            args.seed_id
        )

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM structured_web_seeds
            WHERE {
                ' AND '.join(
                    clauses
                )
            }
            ORDER BY
                last_run_at IS NULL DESC,
                confidence DESC,
                id
            LIMIT ?
            """,
            params + [
                args.limit
            ],
        ).fetchall()

    print(
        "STRUCTURED WEB TARGETS:",
        len(rows),
    )

    totals = {
        "seeds": len(rows),
        "observations": 0,
        "inserted": 0,
        "updated": 0,
        "errors": 0,
    }

    for row in rows:

        print()
        print("=" * 100)

        print(
            "SEED:",
            row["id"],
            "|",
            row["employer_name"],
        )

        print(
            "URL:",
            row["seed_url"],
        )

        run_id = start_run(
            provider="STRUCTURED_WEB",

            provider_source_id=(
                f"seed:{row['id']}"
            ),

            transport_type=(
                "JSON_LD_SITEMAP"
            ),

            metadata={
                "employer": (
                    row[
                        "employer_name"
                    ]
                ),
                "seed_url": (
                    row["seed_url"]
                ),
            },
        )

        try:
            result = (
                collect_structured_web(
                    employer_name=(
                        row[
                            "employer_name"
                        ]
                    ),

                    seed_url=(
                        row["seed_url"]
                    ),

                    provider_source_id=(
                        f"seed:{row['id']}"
                    ),

                    max_detail_pages=100,
                )
            )

            saved = save_observations(
                result.observations,
                ingestion_run_id=run_id,
            )

            totals[
                "observations"
            ] += len(
                result.observations
            )

            totals[
                "inserted"
            ] += saved[
                "inserted"
            ]

            totals[
                "updated"
            ] += saved[
                "updated"
            ]

            totals[
                "errors"
            ] += saved[
                "errors"
            ]

            finish_run(
                run_id,

                status=(
                    "SUCCESS"
                    if not result.errors
                    else "PARTIAL"
                ),

                raw_found=len(
                    result.observations
                ),

                inserted=saved[
                    "inserted"
                ],

                updated=saved[
                    "updated"
                ],

                failed=saved[
                    "errors"
                ],
            )

            with get_connection() as conn:
                conn.execute("""
                    UPDATE structured_web_seeds
                    SET
                        last_run_at=
                            CURRENT_TIMESTAMP,

                        last_job_count=?,

                        last_error=?,

                        updated_at=
                            CURRENT_TIMESTAMP

                    WHERE id=?
                """, (
                    len(
                        result.observations
                    ),

                    (
                        "\n".join(
                            result.errors[
                                :5
                            ]
                        )
                        if result.errors
                        else None
                    ),

                    row["id"],
                ))

                conn.commit()

            print(
                "OBSERVATIONS:",
                len(
                    result.observations
                ),
            )

            print(
                "PAGES:",
                result.pages_fetched,
            )

            print(
                "JSON-LD:",
                result.jsonld_jobs,
            )

            print(
                "SITEMAP JOB URLS:",
                result.sitemap_urls,
            )

            print(
                "DETAIL URLS:",
                result.detail_urls,
            )

            print(
                "ERRORS:",
                len(
                    result.errors
                ),
            )

        except Exception as exc:
            totals[
                "errors"
            ] += 1

            fail_run(
                run_id,
                exc,
            )

            with get_connection() as conn:
                conn.execute("""
                    UPDATE structured_web_seeds
                    SET
                        last_run_at=
                            CURRENT_TIMESTAMP,

                        last_error=?,

                        updated_at=
                            CURRENT_TIMESTAMP

                    WHERE id=?
                """, (
                    repr(exc),
                    row["id"],
                ))

                conn.commit()

            print(
                "[STRUCTURED WEB ERROR]",
                repr(exc),
            )

    print()
    print("=" * 100)
    print(
        "V104 STRUCTURED WEB SUMMARY"
    )
    print("=" * 100)
    print(totals)


if __name__ == "__main__":
    main()
