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
            # SQLite stores booleans as 0/1 integers.
# PostgreSQL jobs.is_active is BOOLEAN.
            if "is_active" in data and data["is_active"] is not None:
                data["is_active"] = bool(data["is_active"])

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

        # ---------------------------------------------------------
        # PRUNE STALE POSTGRES-ONLY NEW JOBS
        # ---------------------------------------------------------
        #
        # SQLite is the canonical collection dataset.
        #
        # If a job exists in Postgres but is no longer present in
        # SQLite, remove it ONLY when its application status is NEW.
        #
        # Never remove SAVED / APPLIED / INTERVIEW / REJECTED /
        # SKIPPED jobs because those are part of application history.

        sqlite_urls = {
            row.get("source_url")
            for row in rows
            if row.get("source_url")
        }

        with pg.cursor() as cur:
            cur.execute("""
                SELECT
                    id,
                    source_url,
                    application_status
                FROM jobs
            """)

            stale_ids = []

            for job_id, source_url, application_status in cur.fetchall():
                if (
                    source_url not in sqlite_urls
                    and application_status == "NEW"
                    ):
                    stale_ids.append(job_id)

            if stale_ids:
                cur.execute(
                    "DELETE FROM jobs WHERE id = ANY(%s)",
                    (stale_ids,),
                )

            stale_deleted = len(stale_ids)

        pg.commit()

        with pg.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM jobs")
            total = cur.fetchone()[0]

    return {
    "sqlite_jobs_seen": len(rows),
    "postgres_inserted": inserted,
    "postgres_updated": updated,
    "skipped": skipped,
    "stale_new_deleted": stale_deleted,
    "postgres_total_jobs": total,
}

if __name__ == "__main__":
    print(sync())
