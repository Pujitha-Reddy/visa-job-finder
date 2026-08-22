from __future__ import annotations

import sqlite3
from pathlib import Path

from app.postgres_repository import pg_conn


BASE_DIR = Path(__file__).resolve().parents[1]
SQLITE_PATH = BASE_DIR / "data" / "jobs.db"


TABLES = (
    "employer_identities",
    "job_observations",
    "canonical_jobs",
    "canonical_job_enrichment",
    "canonical_job_sources",
)


BOOLEAN_COLUMNS = {
    "job_observations": {
        "is_active",
    },

    "canonical_jobs": {
        "is_active",
    },

    "canonical_job_enrichment": {
        "is_software_role",
        "is_us_job",
        "is_us_remote",
        "is_eligible",
    },

    "canonical_job_sources": {
        "is_active",
    },
}


def sqlite_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sqlite_columns(conn, table):
    return [
        dict(row)
        for row in conn.execute(
            f'PRAGMA table_info("{table}")'
        ).fetchall()
    ]


def pg_type(
    sqlite_type,
    *,
    table=None,
    column=None,
):
    if (
        table
        and column
        and column
            in BOOLEAN_COLUMNS.get(
                table,
                set(),
            )
    ):
        return "BOOLEAN"

    value = (
        sqlite_type
        or "TEXT"
    ).upper()

    if "INT" in value:
        return "BIGINT"

    if (
        "REAL" in value
        or "FLOA" in value
        or "DOUB" in value
        or "NUM" in value
    ):
        return "DOUBLE PRECISION"

    if "BLOB" in value:
        return "BYTEA"

    return "TEXT"


def create_table(pg, table, columns):
    definitions = []

    for col in columns:
        name = col["name"]
        data_type = pg_type(
            col["type"],
            table=table,
            column=name,
        )

        definition = (
            f'"{name}" {data_type}'
        )

        if col["pk"]:
            definition += " PRIMARY KEY"

        definitions.append(
            definition
        )

    ddl = f'''
        CREATE TABLE IF NOT EXISTS "{table}" (
            {", ".join(definitions)}
        )
    '''

    with pg.cursor() as cur:
        cur.execute(ddl)


def existing_pg_columns(pg, table):
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT
                column_name
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=%s
            """,
            (
                table,
            ),
        )

        return {
            row["column_name"]
            for row in cur.fetchall()
        }


def reconcile_columns(
    pg,
    table,
    sqlite_columns_list,
):
    existing = existing_pg_columns(
        pg,
        table,
    )

    added = []

    with pg.cursor() as cur:
        for col in sqlite_columns_list:
            name = col["name"]

            if name in existing:
                continue

            data_type = pg_type(
                col["type"]
            )

            cur.execute(
                f'''
                ALTER TABLE "{table}"
                ADD COLUMN "{name}" {data_type}
                '''
            )

            added.append(
                name
            )

    return added


def create_indexes(pg):
    indexes = (
        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_identity_registry
        ON employer_identities(
            registry_employer_id
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_identity_sponsor
        ON employer_identities(
            sponsor_parent_key
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_observation_provider_source
        ON job_observations(
            provider,
            provider_source_id
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_observation_canonical
        ON job_observations(
            canonical_job_id
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_canonical_employer
        ON canonical_jobs(
            employer_identity_id
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_canonical_active
        ON canonical_jobs(
            is_active
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_enrichment_eligible_score
        ON canonical_job_enrichment(
            is_eligible,
            overall_score DESC
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_enrichment_state
        ON canonical_job_enrichment(
            state_code
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_enrichment_role
        ON canonical_job_enrichment(
            software_role_family
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_sources_canonical
        ON canonical_job_sources(
            canonical_job_id
        )
        """,

        """
        CREATE INDEX IF NOT EXISTS
        idx_pg_sources_observation
        ON canonical_job_sources(
            observation_id
        )
        """,
    )

    with pg.cursor() as cur:
        for query in indexes:
            try:
                cur.execute(query)
            except Exception as exc:
                print(
                    "[INDEX WARNING]",
                    repr(exc),
                )

                pg.rollback()

                # Continue schema migration even if an optional
                # index references a column absent in an older
                # local schema.
                continue


def main():
    print("=" * 90)
    print(
        "V111 POSTGRES CANONICAL MIGRATION"
    )
    print("=" * 90)

    with sqlite_conn() as sqlite, pg_conn() as pg:

        sqlite_tables = {
            row["name"]
            for row in sqlite.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                """
            ).fetchall()
        }

        for table in TABLES:
            print()
            print("TABLE:", table)

            if table not in sqlite_tables:
                raise RuntimeError(
                    f"SQLite table missing: {table}"
                )

            columns = sqlite_columns(
                sqlite,
                table,
            )

            create_table(
                pg,
                table,
                columns,
            )

            added = reconcile_columns(
                pg,
                table,
                columns,
            )

            print(
                "SQLITE COLUMNS:",
                len(columns),
            )

            print(
                "POSTGRES ADDED:",
                added,
            )

        pg.commit()

        create_indexes(
            pg
        )

        pg.commit()

    print()
    print("=" * 90)
    print(
        "V111 POSTGRES CANONICAL MIGRATION COMPLETE"
    )
    print("=" * 90)


if __name__ == "__main__":
    main()
