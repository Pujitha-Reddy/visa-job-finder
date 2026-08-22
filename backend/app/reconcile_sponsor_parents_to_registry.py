from __future__ import annotations

from .database import get_connection
from .registry.repository import conn as registry_conn
from .sponsorship.normalize import normalize_company_name


# Parent brands whose operational registry name differs.
PARENT_REGISTRY_ALIASES = {
    "ey": "Ernst & Young",
    "pwc": "PwC",
}


def main():
    # ------------------------------------------------------
    # Operational registry
    # ------------------------------------------------------

    with registry_conn() as c:
        employers = [
            dict(r)
            for r in c.execute("""
                SELECT
                    id,
                    canonical_name,
                    display_name
                FROM employers
                WHERE enabled=1
            """).fetchall()
        ]

    by_canonical = {}
    by_display = {}

    for employer in employers:
        canonical = (
            employer["canonical_name"]
            or normalize_company_name(
                employer["display_name"]
            )
        )

        by_canonical[canonical] = employer

        by_display[
            employer["display_name"].lower()
        ] = employer

        by_canonical[
            normalize_company_name(
                employer["display_name"]
            )
        ] = employer

    counts = {
        "ALREADY_MATCHED": 0,
        "EXACT_PARENT": 0,
        "PARENT_ALIAS": 0,
        "UNMATCHED": 0,
    }

    examples = []

    # ------------------------------------------------------
    # Parent groups
    # ------------------------------------------------------

    with get_connection() as c:
        parents = [
            dict(r)
            for r in c.execute("""
                SELECT *
                FROM sponsor_parent_groups
                ORDER BY
                    highest_priority_score DESC,
                    recent_filings DESC
            """).fetchall()
        ]

        for parent in parents:
            # Preserve a valid inherited match.
            if (
                parent["already_in_registry"]
                and parent["matched_employer_id"]
                is not None
            ):
                counts["ALREADY_MATCHED"] += 1
                continue

            parent_name = (
                parent["display_name"]
                or ""
            )

            parent_key = (
                parent["parent_key"]
                or normalize_company_name(
                    parent_name
                )
            )

            match = None
            method = None

            # --------------------------------------------------
            # 1. Exact normalized parent name
            # --------------------------------------------------

            match = by_canonical.get(
                normalize_company_name(
                    parent_name
                )
            )

            if not match:
                match = by_canonical.get(
                    parent_key
                )

            if match:
                method = "EXACT_PARENT"

            # --------------------------------------------------
            # 2. Explicit parent -> registry alias
            # --------------------------------------------------

            if not match:
                alias_display = (
                    PARENT_REGISTRY_ALIASES.get(
                        parent_key
                    )
                )

                if alias_display:
                    match = by_display.get(
                        alias_display.lower()
                    )

                    if match:
                        method = "PARENT_ALIAS"

            # --------------------------------------------------
            # Persist
            # --------------------------------------------------

            if match:
                counts[method] += 1

                c.execute("""
                    UPDATE sponsor_parent_groups
                    SET already_in_registry=1,
                        matched_employer_id=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE parent_key=?
                """, (
                    match["id"],
                    parent["parent_key"],
                ))

                if len(examples) < 75:
                    examples.append(
                        (
                            parent_name,
                            match["display_name"],
                            method,
                        )
                    )

            else:
                counts["UNMATCHED"] += 1

        c.commit()

    print("=== PARENT REGISTRY RECONCILIATION ===")

    for key, value in counts.items():
        print(f"{key:<18}", value)

    print()
    print("=== NEW MATCHES ===")

    for parent, employer, method in examples:
        print(
            f"{method:<14} | "
            f"{parent:<45} -> "
            f"{employer}"
        )


if __name__ == "__main__":
    main()
