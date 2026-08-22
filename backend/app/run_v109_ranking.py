from __future__ import annotations

from collections import Counter

from app.database import (
    get_connection,
)

from app.enrichment_ranking import (
    rank_job,
)


def main():
    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                j.id,

                j.posted_at,
                j.last_seen_at,

                j.best_source_confidence,
                j.source_count,

                e.is_eligible,

                e.software_role_score,

                e.seniority_band,
                e.min_experience_years,

                e.sponsorship_score,
                e.visa_language_status,

                e.work_arrangement,
                e.is_us_remote

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1

            ORDER BY j.id
        """).fetchall()

        eligible = 0
        zeroed = 0

        score_bands = Counter()

        for row in rows:

            if not row[
                "is_eligible"
            ]:
                # Remove any stale ranking from a previous
                # eligibility state.
                conn.execute("""
                    UPDATE canonical_job_enrichment
                    SET
                        relevance_score=0,
                        freshness_score=0,
                        source_quality_score=0,
                        overall_score=0,

                        updated_at=
                            CURRENT_TIMESTAMP

                    WHERE canonical_job_id=?
                """, (
                    row["id"],
                ))

                zeroed += 1
                continue

            result = rank_job(
                dict(row)
            )

            conn.execute("""
                UPDATE canonical_job_enrichment
                SET
                    relevance_score=?,
                    freshness_score=?,
                    source_quality_score=?,
                    overall_score=?,

                    updated_at=
                        CURRENT_TIMESTAMP

                WHERE canonical_job_id=?
            """, (
                result[
                    "relevance_score"
                ],

                result[
                    "freshness_score"
                ],

                result[
                    "source_quality_score"
                ],

                result[
                    "overall_score"
                ],

                row["id"],
            ))

            eligible += 1

            score = result[
                "overall_score"
            ]

            if score >= 90:
                band = "90-100"

            elif score >= 80:
                band = "80-89"

            elif score >= 70:
                band = "70-79"

            elif score >= 60:
                band = "60-69"

            elif score >= 50:
                band = "50-59"

            else:
                band = "<50"

            score_bands[
                band
            ] += 1

        conn.commit()

    print("=" * 80)
    print(
        "V109F RANKING COMPLETE"
    )
    print("=" * 80)

    print(
        "ELIGIBLE JOBS RANKED:",
        eligible,
    )

    print(
        "NON-ELIGIBLE ZEROED:",
        zeroed,
    )

    print()
    print(
        "=== SCORE DISTRIBUTION ==="
    )

    order = (
        "90-100",
        "80-89",
        "70-79",
        "60-69",
        "50-59",
        "<50",
    )

    for band in order:
        print(
            f"{score_bands[band]:>7} | {band}"
        )


if __name__ == "__main__":
    main()
