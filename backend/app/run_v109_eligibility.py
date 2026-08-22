from __future__ import annotations

from collections import Counter

from app.database import get_connection
from app.enrichment_eligibility import evaluate_job


def main():
    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                j.id,
                j.is_active,

                e.is_software_role,

                e.is_us_job,
                e.is_us_remote,
                e.work_arrangement,

                e.min_experience_years,
                e.max_experience_years,
                e.seniority_band,

                e.sponsor_history_strength,
                e.visa_language_status,
                e.sponsorship_score

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            ORDER BY j.id
        """).fetchall()

        counts = Counter()
        reasons = Counter()

        for row in rows:
            result = evaluate_job(
                dict(row)
            )

            conn.execute("""
                UPDATE canonical_job_enrichment
                SET
                    is_eligible=?,
                    eligibility_reason=?,
                    location_eligibility=?,
                    experience_eligibility=?,
                    sponsorship_eligibility=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE canonical_job_id=?
            """, (
                result["is_eligible"],
                result["eligibility_reason"],
                result["location_eligibility"],
                result["experience_eligibility"],
                result["sponsorship_eligibility"],
                row["id"],
            ))

            if result["is_eligible"]:
                counts["eligible"] += 1
            elif str(
                result["eligibility_reason"]
            ).startswith("REVIEW:"):
                counts["review"] += 1
            else:
                counts["rejected"] += 1

            reasons[
                result[
                    "eligibility_reason"
                ]
            ] += 1

        conn.commit()

    print("=" * 80)
    print("V109E ELIGIBILITY COMPLETE")
    print("=" * 80)
    print(dict(counts))

    print()
    print("=== TOP REASONS ===")

    for reason, count in reasons.most_common(30):
        print(
            f"{count:>7} | {reason}"
        )


if __name__ == "__main__":
    main()
