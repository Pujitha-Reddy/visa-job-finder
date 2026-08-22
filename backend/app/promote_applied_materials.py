from __future__ import annotations

from app.database import get_connection


EMPLOYER_NAME = "Applied Materials"

CAREERS_URL = "https://app.eightfold.ai/careers"

ATS = "EIGHTFOLD"

TOKEN = "appliedmaterials.com"

NOTES = (
    "Verified Eightfold PCS source. "
    "Uses public /careers bootstrap + CSRF session, "
    "/api/pcsx/search, and /api/pcsx/position_details. "
    "Domain=appliedmaterials.com."
)


def main():
    with get_connection() as conn:

        # --------------------------------------------------
        # 1. Find or create employer
        # --------------------------------------------------

        employer = conn.execute(
            """
            SELECT id, display_name
            FROM employers
            WHERE lower(display_name) = lower(?)
            LIMIT 1
            """,
            (EMPLOYER_NAME,),
        ).fetchone()

        if employer:
            employer_id = employer["id"]

            print(
                "EXISTING EMPLOYER:",
                employer_id,
            )

            conn.execute(
                """
                UPDATE employers
                SET careers_url=?,
                    source_type='DIRECT_EMPLOYER',
                    enabled=1,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    CAREERS_URL,
                    employer_id,
                ),
            )

        else:
            cursor = conn.execute(
                """
                INSERT INTO employers (
                    canonical_name,
                    display_name,
                    source_type,
                    careers_url,
                    enabled,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, 1,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP)
                """,
                (
                    "applied materials",
                    EMPLOYER_NAME,
                    "DIRECT_EMPLOYER",
                    CAREERS_URL,
                ),
            )

            employer_id = cursor.lastrowid

            print(
                "INSERTED EMPLOYER:",
                employer_id,
            )

        # --------------------------------------------------
        # 2. Find or create source
        # --------------------------------------------------

        source = conn.execute(
            """
            SELECT id
            FROM employer_sources
            WHERE employer_id=?
              AND ats=?
              AND careers_url=?
            LIMIT 1
            """,
            (
                employer_id,
                ATS,
                CAREERS_URL,
            ),
        ).fetchone()

        if source:
            source_id = source["id"]

            conn.execute(
                """
                UPDATE employer_sources
                SET token=?,
                    enabled=1,
                    source_verified=1,
                    notes=?
                WHERE id=?
                """,
                (
                    TOKEN,
                    NOTES,
                    source_id,
                ),
            )

            print(
                "EXISTING SOURCE:",
                source_id,
            )

        else:
            cursor = conn.execute(
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
                    ATS,
                    TOKEN,
                    CAREERS_URL,
                    NOTES,
                ),
            )

            source_id = cursor.lastrowid

            print(
                "INSERTED SOURCE:",
                source_id,
            )

        # --------------------------------------------------
        # 3. Link sponsor universe
        # --------------------------------------------------

        conn.execute(
            """
            UPDATE combined_sponsor_universe
            SET already_in_registry=1,
                matched_employer_id=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE lower(display_name)
                  LIKE '%applied materials%'
            """,
            (employer_id,),
        )

        # --------------------------------------------------
        # 4. Mark discovery record promoted
        # --------------------------------------------------

        conn.execute(
            """
            UPDATE source_discovery_batches
            SET resolution_status='PROMOTED',
                discovered_careers_url=?,
                discovered_ats=?,
                discovered_token=?,
                verification_status='VERIFIED',
                notes=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE lower(display_name)
                  LIKE '%applied materials%'
            """,
            (
                CAREERS_URL,
                ATS,
                TOKEN,
                NOTES,
            ),
        )

        conn.commit()

        # --------------------------------------------------
        # 5. Verify
        # --------------------------------------------------

        result = conn.execute(
            """
            SELECT
                e.id AS employer_id,
                e.display_name,
                e.source_type,
                s.id AS source_id,
                s.ats,
                s.token,
                s.careers_url,
                s.enabled,
                s.source_verified,
                s.notes
            FROM employers e
            JOIN employer_sources s
              ON s.employer_id=e.id
            WHERE e.id=?
              AND s.id=?
            """,
            (
                employer_id,
                source_id,
            ),
        ).fetchone()

        print()
        print(
            "=== APPLIED MATERIALS REGISTRY ==="
        )

        print(dict(result))


if __name__ == "__main__":
    main()