from __future__ import annotations

from collections import Counter

from app.database import get_connection

from app.enrichment_sponsorship import (
    extract_visa_language,
    calculate_sponsorship,
)


def main():
    with get_connection() as conn:

        rows = conn.execute("""
            SELECT
                j.id,
                j.canonical_title,
                j.description,

                i.sponsor_parent_key,

                s.combined_sponsor_score,
                s.dol_recent_filings,
                s.uscis_2025_approvals,
                s.uscis_2026_approvals

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            JOIN employer_identities i
              ON i.id=j.employer_identity_id

            LEFT JOIN combined_sponsor_universe s
              ON s.parent_key=
                 i.sponsor_parent_key

            WHERE j.is_active=1
              AND e.is_software_role=1

            ORDER BY j.id
        """).fetchall()

        visa_counts = Counter()
        strength_counts = Counter()

        sponsor_linked = 0

        for row in rows:

            visa = extract_visa_language(
                row["canonical_title"],
                row["description"],
            )

            approvals = (
                int(
                    row[
                        "uscis_2025_approvals"
                    ]
                    or 0
                )
                +
                int(
                    row[
                        "uscis_2026_approvals"
                    ]
                    or 0
                )
            )

            sponsorship = (
                calculate_sponsorship(
                    sponsor_parent_key=(
                        row[
                            "sponsor_parent_key"
                        ]
                    ),

                    combined_score=(
                        row[
                            "combined_sponsor_score"
                        ]
                    ),

                    filings=(
                        row[
                            "dol_recent_filings"
                        ]
                    ),

                    approvals=approvals,

                    visa_status=(
                        visa["status"]
                    ),
                )
            )

            if row[
                "sponsor_parent_key"
            ]:
                sponsor_linked += 1

            visa_counts[
                visa["status"]
            ] += 1

            strength_counts[
                sponsorship[
                    "history_strength"
                ]
            ] += 1

            conn.execute("""
                UPDATE canonical_job_enrichment
                SET
                    sponsor_parent_key=?,

                    sponsor_history_strength=?,

                    sponsor_recent_filings=?,
                    sponsor_recent_approvals=?,

                    visa_language_status=?,
                    visa_language_evidence=?,

                    sponsorship_score=?,
                    sponsorship_reason=?,

                    updated_at=
                        CURRENT_TIMESTAMP

                WHERE canonical_job_id=?
            """, (
                row[
                    "sponsor_parent_key"
                ],

                sponsorship[
                    "history_strength"
                ],

                int(
                    row[
                        "dol_recent_filings"
                    ]
                    or 0
                ),

                approvals,

                visa[
                    "status"
                ],

                visa[
                    "evidence"
                ],

                sponsorship[
                    "score"
                ],

                sponsorship[
                    "reason"
                ],

                row["id"],
            ))

        conn.commit()

    print("=" * 80)
    print(
        "V109D SPONSORSHIP ENRICHMENT COMPLETE"
    )
    print("=" * 80)

    print(
        "SOFTWARE JOBS:",
        len(rows),
    )

    print(
        "SPONSOR-IDENTITY LINKED:",
        sponsor_linked,
    )

    print()
    print(
        "=== HISTORICAL SPONSOR STRENGTH ==="
    )

    for key, value in (
        strength_counts.most_common()
    ):
        print(
            f"{value:>7} | {key}"
        )

    print()
    print(
        "=== JOB VISA LANGUAGE ==="
    )

    for key, value in (
        visa_counts.most_common()
    ):
        print(
            f"{value:>7} | {key}"
        )


if __name__ == "__main__":
    main()
