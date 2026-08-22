from __future__ import annotations

from .database import get_connection


def strength(
    active_years: int,
    complete_year_approvals: int,
    five_year_approvals: int,
) -> str:
    """
    Conservative USCIS petition-history strength.

    FY2025 is treated as the latest complete year.
    FY2026 is useful as current activity but does not replace
    the complete-year baseline.
    """
    if (
        active_years >= 3
        and (
            complete_year_approvals >= 100
            or five_year_approvals >= 300
        )
    ):
        return "STRONG"

    if (
        active_years >= 2
        and (
            complete_year_approvals >= 20
            or five_year_approvals >= 50
        )
    ):
        return "MEDIUM"

    if five_year_approvals > 0:
        return "WEAK"

    return "UNKNOWN"


def main():
    with get_connection() as conn:
        conn.execute(
            "DROP TABLE IF EXISTS uscis_h1b_rollup"
        )

        conn.execute("""
            CREATE TABLE uscis_h1b_rollup (
                normalized_name TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,

                first_year INTEGER,
                latest_year INTEGER,
                active_years INTEGER NOT NULL DEFAULT 0,

                approvals_2022 INTEGER NOT NULL DEFAULT 0,
                approvals_2023 INTEGER NOT NULL DEFAULT 0,
                approvals_2024 INTEGER NOT NULL DEFAULT 0,
                approvals_2025 INTEGER NOT NULL DEFAULT 0,
                approvals_2026 INTEGER NOT NULL DEFAULT 0,

                denials_2022 INTEGER NOT NULL DEFAULT 0,
                denials_2023 INTEGER NOT NULL DEFAULT 0,
                denials_2024 INTEGER NOT NULL DEFAULT 0,
                denials_2025 INTEGER NOT NULL DEFAULT 0,
                denials_2026 INTEGER NOT NULL DEFAULT 0,

                new_employment_approvals INTEGER NOT NULL DEFAULT 0,
                new_employment_denials INTEGER NOT NULL DEFAULT 0,

                continuation_approvals INTEGER NOT NULL DEFAULT 0,
                continuation_denials INTEGER NOT NULL DEFAULT 0,

                total_approvals INTEGER NOT NULL DEFAULT 0,
                total_denials INTEGER NOT NULL DEFAULT 0,

                complete_year_approvals INTEGER NOT NULL DEFAULT 0,
                current_year_approvals INTEGER NOT NULL DEFAULT 0,

                approval_rate REAL,

                uscis_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

                last_verified_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX idx_uscis_rollup_total_approvals
            ON uscis_h1b_rollup(total_approvals DESC)
        """)

        conn.execute("""
            CREATE INDEX idx_uscis_rollup_complete_year
            ON uscis_h1b_rollup(complete_year_approvals DESC)
        """)

        rows = conn.execute("""
            SELECT
                normalized_name,

                MIN(display_name) AS display_name,

                MIN(fiscal_year) AS first_year,
                MAX(fiscal_year) AS latest_year,
                COUNT(DISTINCT fiscal_year) AS active_years,

                SUM(CASE
                    WHEN fiscal_year=2022
                    THEN total_approvals ELSE 0
                END) AS approvals_2022,

                SUM(CASE
                    WHEN fiscal_year=2023
                    THEN total_approvals ELSE 0
                END) AS approvals_2023,

                SUM(CASE
                    WHEN fiscal_year=2024
                    THEN total_approvals ELSE 0
                END) AS approvals_2024,

                SUM(CASE
                    WHEN fiscal_year=2025
                    THEN total_approvals ELSE 0
                END) AS approvals_2025,

                SUM(CASE
                    WHEN fiscal_year=2026
                    THEN total_approvals ELSE 0
                END) AS approvals_2026,

                SUM(CASE
                    WHEN fiscal_year=2022
                    THEN total_denials ELSE 0
                END) AS denials_2022,

                SUM(CASE
                    WHEN fiscal_year=2023
                    THEN total_denials ELSE 0
                END) AS denials_2023,

                SUM(CASE
                    WHEN fiscal_year=2024
                    THEN total_denials ELSE 0
                END) AS denials_2024,

                SUM(CASE
                    WHEN fiscal_year=2025
                    THEN total_denials ELSE 0
                END) AS denials_2025,

                SUM(CASE
                    WHEN fiscal_year=2026
                    THEN total_denials ELSE 0
                END) AS denials_2026,

                SUM(new_employment_approvals)
                    AS new_employment_approvals,

                SUM(new_employment_denials)
                    AS new_employment_denials,

                SUM(continuation_approvals)
                    AS continuation_approvals,

                SUM(continuation_denials)
                    AS continuation_denials,

                SUM(total_approvals)
                    AS total_approvals,

                SUM(total_denials)
                    AS total_denials

            FROM uscis_h1b_employer_history

            GROUP BY normalized_name
        """).fetchall()

        for row in rows:
            total_a = int(
                row["total_approvals"] or 0
            )

            total_d = int(
                row["total_denials"] or 0
            )

            denominator = total_a + total_d

            approval_rate = (
                total_a / denominator
                if denominator
                else None
            )

            complete_year = int(
                row["approvals_2025"] or 0
            )

            current_year = int(
                row["approvals_2026"] or 0
            )

            uscis_strength = strength(
                int(row["active_years"] or 0),
                complete_year,
                total_a,
            )

            conn.execute("""
                INSERT INTO uscis_h1b_rollup (
                    normalized_name,
                    display_name,

                    first_year,
                    latest_year,
                    active_years,

                    approvals_2022,
                    approvals_2023,
                    approvals_2024,
                    approvals_2025,
                    approvals_2026,

                    denials_2022,
                    denials_2023,
                    denials_2024,
                    denials_2025,
                    denials_2026,

                    new_employment_approvals,
                    new_employment_denials,

                    continuation_approvals,
                    continuation_denials,

                    total_approvals,
                    total_denials,

                    complete_year_approvals,
                    current_year_approvals,

                    approval_rate,

                    uscis_strength,
                    last_verified_at
                )
                VALUES (
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?, ?,
                    ?,
                    ?,
                    CURRENT_TIMESTAMP
                )
            """, (
                row["normalized_name"],
                row["display_name"],

                row["first_year"],
                row["latest_year"],
                row["active_years"],

                row["approvals_2022"],
                row["approvals_2023"],
                row["approvals_2024"],
                row["approvals_2025"],
                row["approvals_2026"],

                row["denials_2022"],
                row["denials_2023"],
                row["denials_2024"],
                row["denials_2025"],
                row["denials_2026"],

                row["new_employment_approvals"],
                row["new_employment_denials"],

                row["continuation_approvals"],
                row["continuation_denials"],

                total_a,
                total_d,

                complete_year,
                current_year,

                approval_rate,

                uscis_strength,
            ))

        conn.commit()

    print(
        "USCIS EMPLOYER ROLLUPS:",
        len(rows),
    )


if __name__ == "__main__":
    main()
