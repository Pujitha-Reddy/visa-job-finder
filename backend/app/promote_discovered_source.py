from __future__ import annotations

import argparse

from app.database import get_connection
from app.registry.repository import conn as registry_conn
from app.sponsorship.normalize import normalize_company_name


def parse_args():
    parser = argparse.ArgumentParser(
        description="Promote a verified source-discovery record into the operational registry."
    )

    parser.add_argument(
        "--batch",
        default="SPONSOR_EXPANSION_V1",
    )

    parser.add_argument(
        "--employer",
        required=True,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # ------------------------------------------------------
    # Load verified discovery record
    # ------------------------------------------------------

    with get_connection() as c:
        discovery = c.execute(
            """
            SELECT *
            FROM source_discovery_batches
            WHERE batch_name=?
              AND LOWER(display_name)=LOWER(?)
            LIMIT 1
            """,
            (
                args.batch,
                args.employer,
            ),
        ).fetchone()

    if not discovery:
        raise RuntimeError(
            f"No discovery record found for {args.employer!r}"
        )

    discovery = dict(discovery)

    if discovery["verification_status"] != "VERIFIED":
        raise RuntimeError(
            f"{args.employer} is not VERIFIED. "
            f"Current verification_status="
            f"{discovery['verification_status']}"
        )

    ats = (
        discovery["discovered_ats"]
        or ""
    ).strip().upper()

    careers_url = (
        discovery["discovered_careers_url"]
        or ""
    ).strip()

    token = discovery["discovered_token"]

    if not ats:
        raise RuntimeError(
            "Verified discovery record is missing discovered_ats."
        )

    if not careers_url:
        raise RuntimeError(
            "Verified discovery record is missing discovered_careers_url."
        )

    display_name = discovery["display_name"]

    canonical_name = normalize_company_name(
        display_name
    )

    notes = (
        discovery["notes"]
        or "Promoted from verified sponsor source discovery."
    )

    # ------------------------------------------------------
    # Operational registry
    # ------------------------------------------------------

    with registry_conn() as c:
        employer = c.execute(
            """
            SELECT *
            FROM employers
            WHERE canonical_name=?
               OR LOWER(display_name)=LOWER(?)
            LIMIT 1
            """,
            (
                canonical_name,
                display_name,
            ),
        ).fetchone()

        if employer:
            employer_id = employer["id"]

            c.execute(
                """
                UPDATE employers
                SET
                    display_name=?,
                    source_type='DIRECT_EMPLOYER',
                    careers_url=?,
                    enabled=1,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    display_name,
                    careers_url,
                    employer_id,
                ),
            )

            print(
                "EXISTING EMPLOYER:",
                employer_id,
            )

        else:
            cur = c.execute(
                """
                INSERT INTO employers (
                    canonical_name,
                    display_name,
                    source_type,
                    careers_url,
                    enabled
                )
                VALUES (?, ?, 'DIRECT_EMPLOYER', ?, 1)
                """,
                (
                    canonical_name,
                    display_name,
                    careers_url,
                ),
            )

            employer_id = cur.lastrowid

            print(
                "INSERTED EMPLOYER:",
                employer_id,
            )

        # --------------------------------------------------
        # Source
        # --------------------------------------------------

        source = c.execute(
            """
            SELECT *
            FROM employer_sources
            WHERE employer_id=?
              AND ats=?
            LIMIT 1
            """,
            (
                employer_id,
                ats,
            ),
        ).fetchone()

        if source:
            source_id = source["id"]

            c.execute(
                """
                UPDATE employer_sources
                SET
                    token=?,
                    careers_url=?,
                    enabled=1,
                    source_verified=1,
                    notes=?
                WHERE id=?
                """,
                (
                    token,
                    careers_url,
                    notes,
                    source_id,
                ),
            )

            print(
                "UPDATED SOURCE:",
                source_id,
            )

        else:
            cur = c.execute(
                """
                INSERT INTO employer_sources (
                    employer_id,
                    ats,
                    token,
                    careers_url,
                    enabled,
                    source_verified,
                    notes
                )
                VALUES (?, ?, ?, ?, 1, 1, ?)
                """,
                (
                    employer_id,
                    ats,
                    token,
                    careers_url,
                    notes,
                ),
            )

            source_id = cur.lastrowid

            print(
                "INSERTED SOURCE:",
                source_id,
            )

        c.commit()

    # ------------------------------------------------------
    # Link sponsor universe + discovery row
    # ------------------------------------------------------

    with get_connection() as c:
        c.execute(
            """
            UPDATE combined_sponsor_universe
            SET
                already_in_registry=1,
                matched_employer_id=?,
                source_resolution_status='RESOLVED',
                updated_at=CURRENT_TIMESTAMP
            WHERE parent_key=?
            """,
            (
                employer_id,
                discovery["parent_key"],
            ),
        )

        c.execute(
            """
            UPDATE source_discovery_batches
            SET
                resolution_status='PROMOTED',
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                discovery["id"],
            ),
        )

        c.commit()

    print()
    print(
        "PROMOTED:",
        display_name,
    )
    print(
        "EMPLOYER ID:",
        employer_id,
    )
    print(
        "SOURCE ID:",
        source_id,
    )
    print(
        "ATS:",
        ats,
    )
    print(
        "CAREERS:",
        careers_url,
    )
    print(
        "TOKEN:",
        token,
    )


if __name__ == "__main__":
    main()