from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from psycopg import sql

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


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Sync canonical SQLite job-board "
            "tables to PostgreSQL."
        )
    )

    parser.add_argument(
        "--table",
        choices=TABLES,
        default=None,
        help="Sync only one canonical table.",
    )

    parser.add_argument(
        "--skip-identities",
        action="store_true",
        help=(
            "Skip employer_identities during normal "
            "incremental job refreshes."
        ),
    )

    return parser.parse_args()


def sqlite_conn():
    conn = sqlite3.connect(
        SQLITE_PATH
    )

    conn.row_factory = sqlite3.Row

    return conn


def sqlite_rows(
    conn,
    table,
):
    return [
        dict(row)
        for row in conn.execute(
            f'''
            SELECT *
            FROM "{table}"
            '''
        ).fetchall()
    ]


def pg_columns(
    pg,
    table,
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
            (
                table,
            ),
        )

        return [
            row["column_name"]
            for row in cur.fetchall()
        ]


def coerce_bool(value):
    """
    Convert SQLite boolean-like values safely.

    Handles:
        1 / 0
        True / False
        "1" / "0"
        "true" / "false"

    Never use bool("0"), because that is True in Python.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    normalized = str(value).strip().lower()

    if normalized in {
        "1",
        "true",
        "t",
        "yes",
        "y",
        "on",
    }:
        return True

    if normalized in {
        "0",
        "false",
        "f",
        "no",
        "n",
        "off",
        "",
    }:
        return False

    raise ValueError(
        f"Cannot safely convert boolean value: {value!r}"
    )


def normalize_row(
    table,
    row,
    allowed_columns,
):
    data = {
        key: value
        for key, value
        in row.items()
        if key in allowed_columns
    }

    for field in BOOLEAN_COLUMNS.get(
        table,
        set(),
    ):
        if (
            field in data
            and data[field] is not None
        ):
            data[field] = coerce_bool(
                data[field]
            )

    return data


def primary_key(
    sqlite,
    table,
):
    columns = sqlite.execute(
        f'''
        PRAGMA table_info("{table}")
        '''
    ).fetchall()

    pk = [
        row["name"]
        for row in columns
        if row["pk"]
    ]

    if not pk:
        raise RuntimeError(
            f"No primary key found for {table}"
        )

    return pk


def build_upsert_query(
    *,
    table,
    data,
    pk_columns,
):
    insert_columns = list(
        data.keys()
    )

    update_columns = [
        column
        for column in insert_columns
        if column not in pk_columns
    ]

    if update_columns:
        conflict_action = sql.SQL(
            "DO UPDATE SET {}"
        ).format(
            sql.SQL(", ").join(
                sql.SQL(
                    "{} = EXCLUDED.{}"
                ).format(
                    sql.Identifier(column),
                    sql.Identifier(column),
                )
                for column in update_columns
            )
        )
    else:
        conflict_action = sql.SQL(
            "DO NOTHING"
        )

    return sql.SQL("""
        INSERT INTO {table} (
            {columns}
        )
        VALUES (
            {placeholders}
        )
        ON CONFLICT (
            {pk_columns}
        )
        {conflict_action}
    """).format(
        table=sql.Identifier(
            table
        ),

        columns=sql.SQL(", ").join(
            sql.Identifier(column)
            for column in insert_columns
        ),

        placeholders=sql.SQL(", ").join(
            sql.Placeholder()
            for _ in insert_columns
        ),

        pk_columns=sql.SQL(", ").join(
            sql.Identifier(column)
            for column in pk_columns
        ),

        conflict_action=(
            conflict_action
        ),
    )


def sync_table_bulk(
    sqlite,
    pg,
    table,
    *,
    batch_size=2000,
):
    rows = sqlite_rows(
        sqlite,
        table,
    )

    columns = pg_columns(
        pg,
        table,
    )

    allowed = set(
        columns
    )

    pk_columns = primary_key(
        sqlite,
        table,
    )

    normalized = []

    skipped = 0

    for row in rows:
        data = normalize_row(
            table,
            row,
            allowed,
        )

        if not data:
            skipped += 1
            continue

        if any(
            data.get(key) is None
            for key in pk_columns
        ):
            skipped += 1
            continue

        normalized.append(
            data
        )

    if not normalized:
        return {
            "table": table,
            "sqlite": len(rows),
            "upserted": 0,
            "skipped": skipped,
        }

    template = normalized[0]

    query = build_upsert_query(
        table=table,
        data=template,
        pk_columns=pk_columns,
    )

    insert_columns = list(
        template.keys()
    )

    total = len(
        normalized
    )

    done = 0

    for start in range(
        0,
        total,
        batch_size,
    ):
        batch = normalized[
            start:
            start + batch_size
        ]

        values = [
            [
                row[column]
                for column in insert_columns
            ]
            for row in batch
        ]

        with pg.cursor() as cur:
            cur.executemany(
                query,
                values,
            )

        pg.commit()

        done += len(
            batch
        )

        print(
            f"  {table}: "
            f"{done}/{total}"
        )

    return {
        "table": table,
        "sqlite": len(rows),
        "upserted": total,
        "skipped": skipped,
    }


def sync_table(
    sqlite,
    pg,
    table,
):
    # All canonical tables use batched upserts.
    #
    # employer_identities is much larger, so use a
    # somewhat larger batch. Job tables remain small
    # enough for 2,000-row batches.
    batch_size = (
        5000
        if table == "employer_identities"
        else 2000
    )

    return sync_table_bulk(
        sqlite,
        pg,
        table,
        batch_size=batch_size,
    )


def refresh_identity_sequences(
    pg,
):
    """
    Advance PostgreSQL ID sequences beyond IDs copied
    from SQLite.

    If these PG tables were created without SERIAL/IDENTITY
    sequences, pg_get_serial_sequence() simply returns NULL
    and we skip them.
    """

    for table in (
        "employer_identities",
        "job_observations",
        "canonical_jobs",
        "canonical_job_sources",
    ):

        with pg.cursor() as cur:
            cur.execute(
                """
                SELECT
                    pg_get_serial_sequence(
                        %s,
                        'id'
                    ) AS sequence_name
                """,
                (
                    table,
                ),
            )

            row = cur.fetchone()

            sequence = (
                row["sequence_name"]
                if row
                else None
            )

        if not sequence:
            continue

        with pg.cursor() as cur:
            cur.execute(
                sql.SQL("""
                    SELECT
                        COALESCE(
                            MAX(id),
                            1
                        ) AS max_id
                    FROM {}
                """).format(
                    sql.Identifier(
                        table
                    )
                )
            )

            row = cur.fetchone()

            maximum = (
                row["max_id"]
                if row
                else 1
            )

        with pg.cursor() as cur:
            cur.execute(
                """
                SELECT setval(
                    %s,
                    %s,
                    true
                )
                """,
                (
                    sequence,
                    maximum,
                ),
            )


def main():
    args = parse_args()

    tables = (
        (args.table,)
        if args.table
        else TABLES
    )

    if (
        args.skip_identities
        and not args.table
    ):
        tables = tuple(
            table
            for table in tables
            if table != "employer_identities"
        )

    print("=" * 100)
    print(
        "V111 CANONICAL POSTGRES SYNC"
    )
    print("=" * 100)

    results = []

    with sqlite_conn() as sqlite, pg_conn() as pg:

        for table in tables:

            print()
            print(
                "SYNC:",
                table,
            )

            result = sync_table(
                sqlite,
                pg,
                table,
            )

            pg.commit()

            results.append(
                result
            )

            print(
                result
            )

        refresh_identity_sequences(
            pg
        )

        pg.commit()

    print()
    print("=" * 100)
    print(
        "SYNC SUMMARY"
    )
    print("=" * 100)

    for result in results:
        print(
            result
        )


if __name__ == "__main__":
    main()
