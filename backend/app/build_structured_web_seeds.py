from __future__ import annotations

from app.database import get_connection


def main():
    with get_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS
            structured_web_seeds (
                id INTEGER PRIMARY KEY
                    AUTOINCREMENT,

                employer_identity_id INTEGER,

                employer_name TEXT
                    NOT NULL,

                seed_url TEXT
                    NOT NULL,

                seed_source TEXT
                    NOT NULL,

                confidence REAL
                    NOT NULL DEFAULT 0,

                enabled INTEGER
                    NOT NULL DEFAULT 1,

                last_run_at TEXT,
                last_job_count INTEGER
                    NOT NULL DEFAULT 0,

                last_error TEXT,

                created_at TEXT
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                updated_at TEXT
                    NOT NULL
                    DEFAULT CURRENT_TIMESTAMP,

                UNIQUE(
                    employer_name,
                    seed_url
                )
            )
        """)

        # ==================================================
        # Do NOT crawl operational registry employers here.
        #
        # They already have dedicated collectors and are
        # ingested through V103.
        #
        # Structured-web ingestion is a fallback lane for
        # employers without working registry transports.
        # ==================================================

        registry_added = 0

        # ==================================================
        # Source-discovery candidates
        #
        # This includes employers that did NOT make it
        # into the operational collector registry.
        # ==================================================

        rows = conn.execute("""
            SELECT
                b.display_name,
                COALESCE(
                    b.discovered_careers_url,
                    b.careers_candidate_url
                ) AS careers_url,
                i.id AS identity_id

            FROM source_discovery_batches b

            LEFT JOIN employer_identities i
              ON i.sponsor_parent_key =
                 b.parent_key

            WHERE COALESCE(
                b.discovered_careers_url,
                b.careers_candidate_url
            ) IS NOT NULL
        """).fetchall()

        discovery_added = 0

        for row in rows:
            conn.execute("""
                INSERT OR IGNORE INTO
                structured_web_seeds (
                    employer_identity_id,
                    employer_name,
                    seed_url,
                    seed_source,
                    confidence
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                row["identity_id"],
                row["display_name"],
                row["careers_url"],
                "SOURCE_DISCOVERY",
                0.80,
            ))

            discovery_added += 1

        conn.commit()

        total = conn.execute("""
            SELECT COUNT(*) AS n
            FROM structured_web_seeds
            WHERE enabled=1
        """).fetchone()["n"]

    print(
        "REGISTRY SEEDS PROCESSED:",
        registry_added,
    )

    print(
        "DISCOVERY SEEDS PROCESSED:",
        discovery_added,
    )

    print(
        "TOTAL STRUCTURED WEB SEEDS:",
        total,
    )


if __name__ == "__main__":
    main()
