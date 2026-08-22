from __future__ import annotations

from collections import Counter

from app.database import get_connection
from app.enrichment_experience import (
    enrich_experience,
)


def main():
    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                j.id,
                j.canonical_title,
                j.description

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1
              AND e.is_software_role=1

            ORDER BY j.id
        """).fetchall()

        bands = Counter()
        explicit = 0

        for row in rows:

            result = enrich_experience(
                title=(
                    row[
                        "canonical_title"
                    ]
                ),

                description=(
                    row[
                        "description"
                    ]
                ),
            )

            conn.execute("""
                UPDATE canonical_job_enrichment
                SET
                    min_experience_years=?,
                    max_experience_years=?,

                    seniority_band=?,

                    experience_confidence=?,
                    experience_reason=?,

                    updated_at=
                        CURRENT_TIMESTAMP

                WHERE canonical_job_id=?
            """, (
                result[
                    "min_experience_years"
                ],

                result[
                    "max_experience_years"
                ],

                result[
                    "seniority_band"
                ],

                result[
                    "experience_confidence"
                ],

                result[
                    "experience_reason"
                ],

                row["id"],
            ))

            bands[
                result[
                    "seniority_band"
                ]
            ] += 1

            if (
                result[
                    "min_experience_years"
                ]
                is not None
            ):
                explicit += 1

        conn.commit()

    print("=" * 80)
    print(
        "V109C EXPERIENCE ENRICHMENT COMPLETE"
    )
    print("=" * 80)

    print(
        "SOFTWARE JOBS:",
        len(rows),
    )

    print(
        "EXPLICIT YEARS FOUND:",
        explicit,
    )

    print()
    print(
        "=== SENIORITY BANDS ==="
    )

    for band, count in (
        bands.most_common()
    ):
        print(
            f"{count:>7} | {band}"
        )


if __name__ == "__main__":
    main()
