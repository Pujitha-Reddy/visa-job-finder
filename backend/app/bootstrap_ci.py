from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from .postgres_repository import pg_conn
from .registry.repository import (
    conn as registry_conn,
    init_registry,
    upsert_employer,
    upsert_source,
)

BASE_DIR = Path(__file__).resolve().parents[1]
CONFIG_DIR = BASE_DIR.parent / "config"
REGISTRY_SNAPSHOT = CONFIG_DIR / "registry_sources_v1.csv"


def bootstrap_registry():
    if not REGISTRY_SNAPSHOT.exists():
        raise RuntimeError(
            f"Missing registry snapshot: {REGISTRY_SNAPSHOT}"
        )

    init_registry()

    imported = 0

    with REGISTRY_SNAPSHOT.open(
        newline="",
        encoding="utf-8",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            company = (row.get("company") or "").strip()
            ats = (row.get("ats") or "").strip()

            if not company or not ats:
                continue

            employer_id = upsert_employer(
                company,
                (row.get("source_type") or "DIRECT_EMPLOYER").strip(),
                (row.get("careers_url") or "").strip() or None,
            )

            upsert_source(
                employer_id,
                ats,
                (row.get("token") or "").strip() or None,
                (row.get("careers_url") or "").strip() or None,
                True,
                (row.get("notes") or "").strip() or "CI registry snapshot",
            )

            imported += 1

    return imported


def _sqlite_type(pg_type: str) -> str:
    pg_type = (pg_type or "").lower()

    if pg_type in {
        "smallint",
        "integer",
        "bigint",
    }:
        return "INTEGER"

    if pg_type in {
        "numeric",
        "decimal",
        "real",
        "double precision",
    }:
        return "REAL"

    return "TEXT"


def bootstrap_sponsor_rollup():
    """
    Supabase is the durable sponsor-data store.

    Copy sponsor_rollup into the runner's temporary SQLite DB
    so enrich_v11 can continue using its existing SQLite path.
    """

    with pg_conn() as pg, pg.cursor() as cur:
        cur.execute("""
            SELECT
                column_name,
                data_type
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='sponsor_rollup'
            ORDER BY ordinal_position
        """)

        schema_rows = cur.fetchall()

        if not schema_rows:
            raise RuntimeError(
                "Supabase sponsor_rollup table is missing."
            )

        columns = [r["column_name"] for r in schema_rows]

        cur.execute(
            'SELECT * FROM sponsor_rollup'
        )
        sponsor_rows = cur.fetchall()

    if not sponsor_rows:
        raise RuntimeError(
            "Supabase sponsor_rollup is empty."
        )

    definitions = ", ".join(
        f'"{r["column_name"]}" {_sqlite_type(r["data_type"])}'
        for r in schema_rows
    )

    placeholders = ",".join(
        "?" for _ in columns
    )

    column_sql = ",".join(
        f'"{c}"' for c in columns
    )

    with registry_conn() as local:
        local.execute("DROP TABLE IF EXISTS sponsor_rollup")

        local.execute(
            f"CREATE TABLE sponsor_rollup ({definitions})"
        )

        local.executemany(
            f"""
            INSERT INTO sponsor_rollup ({column_sql})
            VALUES ({placeholders})
            """,
            [
                tuple(row.get(c) for c in columns)
                for row in sponsor_rows
            ],
        )

        local.commit()

    return len(sponsor_rows)


def main():
    print("=== CI BOOTSTRAP ===")

    registry_count = bootstrap_registry()
    print("REGISTRY SOURCES:", registry_count)

    sponsor_count = bootstrap_sponsor_rollup()
    print("SPONSOR ROLLUP:", sponsor_count)

    print("CI BOOTSTRAP COMPLETE")


if __name__ == "__main__":
    main()
