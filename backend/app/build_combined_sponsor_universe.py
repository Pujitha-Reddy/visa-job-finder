from __future__ import annotations

from .database import get_connection


def dol_component(
    recent_filings: int,
) -> float:
    n = int(
        recent_filings or 0
    )

    if n >= 1000:
        return 40.0
    if n >= 500:
        return 36.0
    if n >= 200:
        return 32.0
    if n >= 100:
        return 27.0
    if n >= 50:
        return 22.0
    if n >= 20:
        return 16.0
    if n >= 5:
        return 10.0
    if n >= 1:
        return 5.0

    return 0.0


def uscis_volume_component(
    approvals_2025: int,
) -> float:
    """
    Latest complete FY is weighted most heavily.
    Maximum 30 points.
    """
    n = int(
        approvals_2025 or 0
    )

    if n >= 1000:
        return 30.0
    if n >= 500:
        return 27.0
    if n >= 200:
        return 24.0
    if n >= 100:
        return 21.0
    if n >= 50:
        return 17.0
    if n >= 20:
        return 13.0
    if n >= 5:
        return 8.0
    if n >= 1:
        return 4.0

    return 0.0


def consistency_component(
    active_years: int,
) -> float:
    years = int(
        active_years or 0
    )

    return {
        5: 15.0,
        4: 13.0,
        3: 10.0,
        2: 6.0,
        1: 3.0,
    }.get(
        years,
        0.0,
    )


def approval_component(
    approvals: int,
    denials: int,
) -> float:
    """
    Approval percentage is only meaningful when volume
    is sufficiently large.

    Maximum 5 points.
    """
    a = int(
        approvals or 0
    )

    d = int(
        denials or 0
    )

    decisions = a + d

    if decisions < 20:
        return 0.0

    rate = a / decisions

    if rate >= 0.98:
        return 5.0
    if rate >= 0.95:
        return 4.0
    if rate >= 0.90:
        return 3.0
    if rate >= 0.80:
        return 2.0

    return 1.0


def current_activity_component(
    approvals_2026: int,
) -> float:
    """
    FY2026 is current/in-progress, so it receives
    only a modest recent-activity weight.
    """
    n = int(
        approvals_2026 or 0
    )

    if n >= 500:
        return 10.0
    if n >= 200:
        return 9.0
    if n >= 100:
        return 8.0
    if n >= 50:
        return 7.0
    if n >= 20:
        return 5.0
    if n >= 5:
        return 3.0
    if n >= 1:
        return 1.0

    return 0.0


def priority_band(
    score: float,
) -> str:
    if score >= 80:
        return "TIER_1"

    if score >= 60:
        return "TIER_2"

    if score >= 40:
        return "TIER_3"

    return "LOW"


def main():
    with get_connection() as conn:
        conn.execute(
            "DROP TABLE IF EXISTS combined_sponsor_universe"
        )

        conn.execute("""
            CREATE TABLE combined_sponsor_universe (
                parent_key TEXT PRIMARY KEY,

                display_name TEXT NOT NULL,

                dol_present INTEGER NOT NULL DEFAULT 0,
                uscis_present INTEGER NOT NULL DEFAULT 0,

                dol_recent_filings INTEGER NOT NULL DEFAULT 0,
                dol_total_filings INTEGER NOT NULL DEFAULT 0,
                dol_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

                uscis_active_years INTEGER NOT NULL DEFAULT 0,

                uscis_2025_approvals INTEGER NOT NULL DEFAULT 0,
                uscis_2026_approvals INTEGER NOT NULL DEFAULT 0,

                uscis_total_approvals INTEGER NOT NULL DEFAULT 0,
                uscis_total_denials INTEGER NOT NULL DEFAULT 0,

                uscis_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

                dol_score_component REAL NOT NULL DEFAULT 0,
                uscis_volume_component REAL NOT NULL DEFAULT 0,
                consistency_component REAL NOT NULL DEFAULT 0,
                approval_component REAL NOT NULL DEFAULT 0,
                current_activity_component REAL NOT NULL DEFAULT 0,

                combined_sponsor_score REAL NOT NULL DEFAULT 0,
                combined_priority_band TEXT NOT NULL DEFAULT 'LOW',

                already_in_registry INTEGER NOT NULL DEFAULT 0,
                matched_employer_id INTEGER,

                source_resolution_status TEXT NOT NULL DEFAULT 'UNRESOLVED',

                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX idx_combined_sponsor_score
            ON combined_sponsor_universe(
                combined_sponsor_score DESC
            )
        """)

        dol = {
            r["parent_key"]: dict(r)
            for r in conn.execute("""
                SELECT *
                FROM sponsor_parent_groups
            """).fetchall()
        }

        uscis = {
            r["parent_key"]: dict(r)
            for r in conn.execute("""
                SELECT *
                FROM uscis_h1b_parent_rollup
            """).fetchall()
        }

        keys = (
            set(dol)
            | set(uscis)
        )

        for key in keys:
            d = dol.get(key)
            u = uscis.get(key)

            display_name = (
                d["display_name"]
                if d
                else u["display_name"]
            )

            dol_recent = (
                int(
                    d[
                        "recent_filings"
                    ] or 0
                )
                if d
                else 0
            )

            dol_total = (
                int(
                    d[
                        "total_filings"
                    ] or 0
                )
                if d
                else 0
            )

            dol_strength = (
                d[
                    "strongest_sponsor_strength"
                ]
                if d
                else "UNKNOWN"
            )

            active_years = (
                int(
                    u["active_years"]
                    or 0
                )
                if u
                else 0
            )

            approvals_2025 = (
                int(
                    u[
                        "approvals_2025"
                    ] or 0
                )
                if u
                else 0
            )

            approvals_2026 = (
                int(
                    u[
                        "approvals_2026"
                    ] or 0
                )
                if u
                else 0
            )

            total_a = (
                int(
                    u[
                        "total_approvals"
                    ] or 0
                )
                if u
                else 0
            )

            total_d = (
                int(
                    u[
                        "total_denials"
                    ] or 0
                )
                if u
                else 0
            )

            uscis_strength = (
                u["uscis_strength"]
                if u
                else "UNKNOWN"
            )

            dol_points = (
                dol_component(
                    dol_recent
                )
            )

            uscis_points = (
                uscis_volume_component(
                    approvals_2025
                )
            )

            consistency_points = (
                consistency_component(
                    active_years
                )
            )

            approval_points = (
                approval_component(
                    total_a,
                    total_d,
                )
            )

            current_points = (
                current_activity_component(
                    approvals_2026
                )
            )

            combined = min(
                100.0,
                dol_points
                + uscis_points
                + consistency_points
                + approval_points
                + current_points,
            )

            already_in_registry = (
                int(
                    d[
                        "already_in_registry"
                    ] or 0
                )
                if d
                else 0
            )

            matched_employer_id = (
                d[
                    "matched_employer_id"
                ]
                if d
                else None
            )

            conn.execute("""
                INSERT INTO combined_sponsor_universe (
                    parent_key,
                    display_name,

                    dol_present,
                    uscis_present,

                    dol_recent_filings,
                    dol_total_filings,
                    dol_strength,

                    uscis_active_years,
                    uscis_2025_approvals,
                    uscis_2026_approvals,

                    uscis_total_approvals,
                    uscis_total_denials,
                    uscis_strength,

                    dol_score_component,
                    uscis_volume_component,
                    consistency_component,
                    approval_component,
                    current_activity_component,

                    combined_sponsor_score,
                    combined_priority_band,

                    already_in_registry,
                    matched_employer_id,

                    source_resolution_status,
                    updated_at
                )
                VALUES (
                    ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?, ?,
                    ?, ?,
                    ?, ?,
                    'UNRESOLVED',
                    CURRENT_TIMESTAMP
                )
            """, (
                key,
                display_name,

                1 if d else 0,
                1 if u else 0,

                dol_recent,
                dol_total,
                dol_strength,

                active_years,
                approvals_2025,
                approvals_2026,

                total_a,
                total_d,
                uscis_strength,

                dol_points,
                uscis_points,
                consistency_points,
                approval_points,
                current_points,

                combined,
                priority_band(
                    combined
                ),

                already_in_registry,
                matched_employer_id,
            ))

        conn.commit()

    print(
        "COMBINED SPONSOR PARENTS:",
        len(keys),
    )


if __name__ == "__main__":
    main()
