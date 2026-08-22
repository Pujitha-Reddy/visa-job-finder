from __future__ import annotations

import json
from pathlib import Path

from app.database import get_connection
from app.postgres_repository import pg_conn


BASE_DIR = Path(__file__).resolve().parents[1]

RUNNER_SCHEMA_PATH = (
    BASE_DIR.parent
    / "config"
    / "v119_runner_schema.sql"
)


def convert_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value)

    if (
        value is not None
        and not isinstance(
            value,
            (
                str,
                int,
                float,
                bytes,
            ),
        )
    ):
        return str(value)

    return value


def hydrate_table_from_postgres(
    sqlite,
    pg,
    table: str,
):
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT
                column_name
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name=%s
            ORDER BY ordinal_position
            """,
            (table,),
        )

        schema_rows = cur.fetchall()

        if not schema_rows:
            raise RuntimeError(
                f"Postgres table missing: {table}"
            )

        pg_columns = [
            row["column_name"]
            for row in schema_rows
        ]

        local_columns = [
            row["name"]
            for row in sqlite.execute(
                f'PRAGMA table_info("{table}")'
            ).fetchall()
        ]

        if not local_columns:
            raise RuntimeError(
                f"Runner SQLite schema missing table: {table}"
            )

        columns = [
            column
            for column in pg_columns
            if column in local_columns
        ]

        if not columns:
            raise RuntimeError(
                f"No shared columns for table: {table}"
            )

        column_select = ", ".join(
            f'"{column}"'
            for column in columns
        )

        cur.execute(
            f'SELECT {column_select} FROM "{table}"'
        )

        rows = cur.fetchall()

    sqlite.execute(
        f'DELETE FROM "{table}"'
    )

    if rows:
        placeholders = ", ".join(
            "?"
            for _ in columns
        )

        column_sql = ", ".join(
            f'"{column}"'
            for column in columns
        )

        values = [
            tuple(
                convert_value(
                    row[column]
                )
                for column in columns
            )
            for row in rows
        ]

        sqlite.executemany(
            f'''
            INSERT INTO "{table}" (
                {column_sql}
            )
            VALUES (
                {placeholders}
            )
            ''',
            values,
        )

    sqlite.commit()

    print(
        f"{table:<36}",
        len(rows),
    )

    return len(rows)


def restore_v114_state(pg):
    with pg.cursor() as cur:
        cur.execute(
            """
            SELECT state_value
            FROM pipeline_runtime_state
            WHERE state_key='v114_onboarding'
            """
        )

        row = cur.fetchone()

    if not row:
        return {}

    value = row["state_value"]

    if isinstance(value, str):
        value = json.loads(value)

    return value or {}


def main():
    print("=" * 110)
    print("V119.8B SCHEMA-ACCURATE CLOUD RUNNER HYDRATION")
    print("=" * 110)

    if not RUNNER_SCHEMA_PATH.exists():
        raise RuntimeError(
            "Missing certified runner schema: "
            f"{RUNNER_SCHEMA_PATH}"
        )

    with get_connection() as sqlite:
        sqlite.executescript(
            RUNNER_SCHEMA_PATH.read_text()
        )

        sqlite.commit()

    tables = [
        "employers",
        "employer_sources",
        "combined_sponsor_universe",
        "source_discovery_batches",
        "sponsor_rollup",
        "employer_identities",
        "job_observations",
        "canonical_jobs",
        "canonical_job_enrichment",
        "canonical_job_sources",
    ]

    with get_connection() as sqlite:
        with pg_conn() as pg:
            counts = {}

            for table in tables:
                counts[table] = (
                    hydrate_table_from_postgres(
                        sqlite,
                        pg,
                        table,
                    )
                )

            # ingestion_runs exists in the certified schema
            # but intentionally begins empty on every fresh runner.
            sqlite.execute(
                "DELETE FROM ingestion_runs"
            )

            sqlite.commit()

            state = restore_v114_state(
                pg
            )

    print()
    print("V114 STATE:", state)

    print()
    print("COUNTS")

    for table, count in counts.items():
        print(
            f"  {table:<34}",
            count,
        )

    print()
    print("=" * 110)
    print("V119.8B HYDRATION COMPLETE")
    print("=" * 110)


if __name__ == "__main__":
    main()
