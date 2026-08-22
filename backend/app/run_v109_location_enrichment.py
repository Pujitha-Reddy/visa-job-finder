from __future__ import annotations

from collections import Counter

from app.database import get_connection
from app.enrichment_location import (
    classify_location,
)


def main():
    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                j.id,
                j.canonical_title,
                j.canonical_location,
                j.description

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1
              AND e.is_software_role=1

            ORDER BY j.id
        """).fetchall()

        arrangements = Counter()
        countries = Counter()
        states = Counter()

        for row in rows:

            result = classify_location(
                title=row[
                    "canonical_title"
                ],

                location=row[
                    "canonical_location"
                ],

                description=row[
                    "description"
                ],
            )

            conn.execute("""
                UPDATE canonical_job_enrichment
                SET
                    country_code=?,
                    state_code=?,
                    city=?,

                    work_arrangement=?,

                    is_us_job=?,
                    is_us_remote=?,

                    location_confidence=?,
                    location_reason=?,

                    updated_at=
                        CURRENT_TIMESTAMP

                WHERE canonical_job_id=?
            """, (
                result[
                    "country_code"
                ],

                result[
                    "state_code"
                ],

                result[
                    "city"
                ],

                result[
                    "work_arrangement"
                ],

                result[
                    "is_us_job"
                ],

                result[
                    "is_us_remote"
                ],

                result[
                    "location_confidence"
                ],

                result[
                    "location_reason"
                ],

                row["id"],
            ))

            arrangements[
                result[
                    "work_arrangement"
                ]
            ] += 1

            country_key = (
                "US"
                if result[
                    "is_us_job"
                ] == 1
                else "NON_US"
                if result[
                    "is_us_job"
                ] == 0
                else "UNKNOWN"
            )

            countries[
                country_key
            ] += 1

            if result[
                "state_code"
            ]:
                states[
                    result[
                        "state_code"
                    ]
                ] += 1

        conn.commit()

    print("=" * 80)
    print(
        "V109B LOCATION ENRICHMENT COMPLETE"
    )
    print("=" * 80)

    print(
        "SOFTWARE JOBS PROCESSED:",
        len(rows),
    )

    print()
    print(
        "=== WORK ARRANGEMENT ==="
    )

    for key, value in (
        arrangements.most_common()
    ):
        print(
            f"{value:>7} | {key}"
        )

    print()
    print(
        "=== COUNTRY ==="
    )

    for key, value in (
        countries.most_common()
    ):
        print(
            f"{value:>7} | {key}"
        )

    print()
    print(
        "=== TOP US STATES ==="
    )

    for key, value in (
        states.most_common(25)
    ):
        print(
            f"{value:>7} | {key}"
        )


if __name__ == "__main__":
    main()
