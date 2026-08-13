from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql


BASE_DIR = Path(__file__).resolve().parents[1]
SQLITE_PATH = BASE_DIR / "data" / "jobs.db"
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing.")

# These are dashboard/user-state fields. Never overwrite them from the ephemeral
# SQLite collector database once the job already exists in Supabase.
PRESERVE_ON_UPDATE = {
    "id",
    "source_url",
    "application_status",
    "date_applied",
    "notes",
    "first_seen_at",
}

def sqlite_jobs():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute("SELECT * FROM jobs").fetchall()]
    conn.close()
    return rows

def pg_columns(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name='jobs'
            ORDER BY ordinal_position
        """)
        return [r[0] for r in cur.fetchall()]

def sync():
    rows = sqlite_jobs()

    with psycopg.connect(DATABASE_URL, connect_timeout=20) as pg:
        columns = pg_columns(pg)
        column_set = set(columns)

        inserted = 0
        updated = 0
        skipped = 0

        for row in rows:
            source_url = row.get("source_url")
            if not source_url:
                skipped += 1
                continue

            data = {k: v for k, v in row.items() if k in column_set}

            # For new rows we do not force the SQLite id into Postgres. This
            # avoids identity collisions after Supabase becomes authoritative.
            insert_data = {k: v for k, v in data.items() if k != "id"}

            insert_cols = list(insert_data)
            update_cols = [
                k for k in insert_cols
                if k not in PRESERVE_ON_UPDATE
            ]

            query = sql.SQL("""
                INSERT INTO jobs ({insert_columns})
                VALUES ({placeholders})
                ON CONFLICT (source_url)
                DO UPDATE SET {assignments}
                RETURNING (xmax = 0) AS inserted
            """).format(
                insert_columns=sql.SQL(", ").join(
                    sql.Identifier(c) for c in insert_cols
                ),
                placeholders=sql.SQL(", ").join(
                    sql.Placeholder() for _ in insert_cols
                ),
                assignments=sql.SQL(", ").join(
                    sql.SQL("{} = EXCLUDED.{}").format(
                        sql.Identifier(c), sql.Identifier(c)
                    )
                    for c in update_cols
                ),
            )

            with pg.cursor() as cur:
                cur.execute(query, [insert_data[c] for c in insert_cols])
                was_inserted = bool(cur.fetchone()[0])

            if was_inserted:
                inserted += 1
            else:
                updated += 1

        pg.commit()

        with pg.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jobs")
            pg_total = cur.fetchone()[0]

    return {
        "sqlite_jobs_seen": len(rows),
        "postgres_inserted": inserted,
        "postgres_updated": updated,
        "skipped": skipped,
        "postgres_total_jobs": pg_total,
    }

if __name__ == "__main__":
    print(sync())
