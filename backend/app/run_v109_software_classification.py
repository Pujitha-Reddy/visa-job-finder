from __future__ import annotations

from collections import Counter

from app.database import get_connection
from app.enrichment_software import classify_software_role


def main():
    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                id,
                canonical_title
            FROM canonical_jobs
            WHERE is_active=1
            ORDER BY id
        """).fetchall()

        counts = Counter()
        families = Counter()

        for row in rows:
            result = classify_software_role(
                row["canonical_title"]
            )

            conn.execute("""
                INSERT INTO canonical_job_enrichment (
                    canonical_job_id,
                    is_software_role,
                    software_role_family,
                    software_role_score,
                    software_role_reason
                )
                VALUES (?, ?, ?, ?, ?)

                ON CONFLICT(canonical_job_id)
                DO UPDATE SET
                    is_software_role=
                        excluded.is_software_role,

                    software_role_family=
                        excluded.software_role_family,

                    software_role_score=
                        excluded.software_role_score,

                    software_role_reason=
                        excluded.software_role_reason,

                    updated_at=CURRENT_TIMESTAMP
            """, (
                row["id"],
                result["is_software_role"],
                result["software_role_family"],
                result["software_role_score"],
                result["software_role_reason"],
            ))

            if result["is_software_role"]:
                counts["software"] += 1
                families[
                    result["software_role_family"]
                ] += 1
            else:
                counts["rejected"] += 1

        conn.commit()

    print("=" * 80)
    print("V109A SOFTWARE CLASSIFICATION COMPLETE")
    print("=" * 80)
    print(dict(counts))

    print()
    print("=== ROLE FAMILIES ===")

    for family, count in families.most_common():
        print(
            f"{count:>6} | {family}"
        )


if __name__ == "__main__":
    main()
