from __future__ import annotations

from .build_sponsor_parent_groups import infer_parent
from .database import get_connection


def strength_rank(value: str) -> int:
    return {
        "STRONG": 3,
        "MEDIUM": 2,
        "WEAK": 1,
        "UNKNOWN": 0,
    }.get(
        (value or "UNKNOWN").upper(),
        0,
    )


def main():
    with get_connection() as conn:
        conn.execute(
            "DROP TABLE IF EXISTS uscis_h1b_parent_rollup"
        )

        conn.execute("""
            CREATE TABLE uscis_h1b_parent_rollup (
                parent_key TEXT PRIMARY KEY,

                display_name TEXT NOT NULL,

                matched_uscis_entities
                    INTEGER NOT NULL DEFAULT 0,

                dol_parent_present
                    INTEGER NOT NULL DEFAULT 0,

                active_years INTEGER NOT NULL DEFAULT 0,

                approvals_2022 INTEGER NOT NULL DEFAULT 0,
                approvals_2023 INTEGER NOT NULL DEFAULT 0,
                approvals_2024 INTEGER NOT NULL DEFAULT 0,
                approvals_2025 INTEGER NOT NULL DEFAULT 0,
                approvals_2026 INTEGER NOT NULL DEFAULT 0,

                total_approvals INTEGER NOT NULL DEFAULT 0,
                total_denials INTEGER NOT NULL DEFAULT 0,

                complete_year_approvals
                    INTEGER NOT NULL DEFAULT 0,

                current_year_approvals
                    INTEGER NOT NULL DEFAULT 0,

                approval_rate REAL,

                uscis_strength TEXT NOT NULL
                    DEFAULT 'UNKNOWN',

                last_verified_at TEXT
                    DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX idx_uscis_parent_complete
            ON uscis_h1b_parent_rollup(
                complete_year_approvals DESC
            )
        """)

        conn.execute("""
            CREATE INDEX idx_uscis_parent_strength
            ON uscis_h1b_parent_rollup(
                uscis_strength
            )
        """)

        # --------------------------------------------------
        # Existing DOL legal entity -> parent relationship
        # --------------------------------------------------

        member_to_parent = {
            r["normalized_name"]: r["parent_key"]
            for r in conn.execute("""
                SELECT
                    normalized_name,
                    parent_key
                FROM sponsor_parent_members
            """).fetchall()
        }

        dol_parents = {
            r["parent_key"]: r["display_name"]
            for r in conn.execute("""
                SELECT
                    parent_key,
                    display_name
                FROM sponsor_parent_groups
            """).fetchall()
        }

        uscis_rows = [
            dict(r)
            for r in conn.execute("""
                SELECT *
                FROM uscis_h1b_rollup
            """).fetchall()
        ]

        groups = {}

        exact_dol = 0
        inferred_dol = 0
        uscis_only = 0

        for row in uscis_rows:
            # ----------------------------------------------
            # 1. Exact USCIS legal entity -> DOL entity
            # ----------------------------------------------

            parent_key = member_to_parent.get(
                row["normalized_name"]
            )

            if parent_key:
                display_name = dol_parents[parent_key]
                dol_present = 1
                exact_dol += 1

            else:
                # ------------------------------------------
                # 2. Conservative parent inference
                # ------------------------------------------

                (
                    inferred_key,
                    inferred_name,
                    _,
                ) = infer_parent(
                    row["display_name"]
                )

                parent_key = inferred_key

                if parent_key in dol_parents:
                    display_name = dol_parents[
                        parent_key
                    ]

                    dol_present = 1
                    inferred_dol += 1

                else:
                    # --------------------------------------
                    # 3. USCIS-only sponsor
                    # --------------------------------------

                    display_name = inferred_name
                    dol_present = 0
                    uscis_only += 1

            group = groups.setdefault(
                parent_key,
                {
                    "display_name": display_name,

                    "matched_uscis_entities": 0,

                    "dol_parent_present":
                        dol_present,

                    "years": set(),

                    "approvals_2022": 0,
                    "approvals_2023": 0,
                    "approvals_2024": 0,
                    "approvals_2025": 0,
                    "approvals_2026": 0,

                    "total_approvals": 0,
                    "total_denials": 0,

                    "uscis_strength": "UNKNOWN",
                },
            )

            # If any member connects to DOL,
            # preserve that evidence.
            if dol_present:
                group[
                    "dol_parent_present"
                ] = 1

                group[
                    "display_name"
                ] = display_name

            group[
                "matched_uscis_entities"
            ] += 1

            # ----------------------------------------------
            # Active years based on actual approvals/denials
            # ----------------------------------------------

            for year in range(2022, 2027):
                approval_field = (
                    f"approvals_{year}"
                )

                denial_field = (
                    f"denials_{year}"
                )

                approvals = int(
                    row[approval_field] or 0
                )

                denials = int(
                    row[denial_field] or 0
                )

                if approvals > 0 or denials > 0:
                    group["years"].add(year)

                group[
                    approval_field
                ] += approvals

            group[
                "total_approvals"
            ] += int(
                row["total_approvals"]
                or 0
            )

            group[
                "total_denials"
            ] += int(
                row["total_denials"]
                or 0
            )

            if (
                strength_rank(
                    row["uscis_strength"]
                )
                > strength_rank(
                    group[
                        "uscis_strength"
                    ]
                )
            ):
                group[
                    "uscis_strength"
                ] = row[
                    "uscis_strength"
                ]

        # --------------------------------------------------
        # Persist
        # --------------------------------------------------

        for parent_key, g in groups.items():
            total_a = g[
                "total_approvals"
            ]

            total_d = g[
                "total_denials"
            ]

            denominator = (
                total_a + total_d
            )

            approval_rate = (
                total_a / denominator
                if denominator
                else None
            )

            conn.execute("""
                INSERT INTO uscis_h1b_parent_rollup (
                    parent_key,
                    display_name,

                    matched_uscis_entities,
                    dol_parent_present,
                    active_years,

                    approvals_2022,
                    approvals_2023,
                    approvals_2024,
                    approvals_2025,
                    approvals_2026,

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
                    ?, ?,
                    ?, ?,
                    ?,
                    ?,
                    CURRENT_TIMESTAMP
                )
            """, (
                parent_key,
                g["display_name"],

                g[
                    "matched_uscis_entities"
                ],

                g[
                    "dol_parent_present"
                ],

                len(
                    g["years"]
                ),

                g["approvals_2022"],
                g["approvals_2023"],
                g["approvals_2024"],
                g["approvals_2025"],
                g["approvals_2026"],

                total_a,
                total_d,

                g["approvals_2025"],
                g["approvals_2026"],

                approval_rate,

                g["uscis_strength"],
            ))

        conn.commit()

    print(
        "USCIS PARENT GROUPS:",
        len(groups),
    )

    print(
        "EXACT DOL ENTITY MATCHES:",
        exact_dol,
    )

    print(
        "INFERRED DOL PARENT MATCHES:",
        inferred_dol,
    )

    print(
        "USCIS-ONLY EMPLOYER ROWS:",
        uscis_only,
    )


if __name__ == "__main__":
    main()
