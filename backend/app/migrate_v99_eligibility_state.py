from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import psycopg
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
SQLITE_PATH = BASE_DIR / "data" / "jobs.db"

load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")


SQLITE_COLUMNS = {
    "is_eligible": "INTEGER DEFAULT 1",
    "eligibility_reason": "TEXT",
    "location_eligibility": "TEXT",
    "experience_eligibility": "TEXT",
}


POSTGRES_COLUMNS = {
    "is_eligible": "BOOLEAN DEFAULT TRUE",
    "eligibility_reason": "TEXT",
    "location_eligibility": "TEXT",
    "experience_eligibility": "TEXT",
}


def migrate_sqlite():
    conn = sqlite3.connect(SQLITE_PATH)

    try:
        existing = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(jobs)"
            ).fetchall()
        }

        added = []

        for name, ddl in SQLITE_COLUMNS.items():
            if name in existing:
                continue

            conn.execute(
                f'ALTER TABLE jobs '
                f'ADD COLUMN "{name}" {ddl}'
            )

            added.append(name)

        conn.execute("""
            UPDATE jobs
            SET is_eligible = 1
            WHERE is_eligible IS NULL
        """)

        conn.commit()

        return added

    finally:
        conn.close()


def migrate_postgres():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is missing."
        )

    added = []

    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=20,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema='public'
                  AND table_name='jobs'
            """)

            existing = {
                row[0]
                for row in cur.fetchall()
            }

            for name, ddl in (
                POSTGRES_COLUMNS.items()
            ):
                if name in existing:
                    continue

                cur.execute(
                    f'ALTER TABLE jobs '
                    f'ADD COLUMN "{name}" {ddl}'
                )

                added.append(name)

            cur.execute("""
                UPDATE jobs
                SET is_eligible = TRUE
                WHERE is_eligible IS NULL
            """)

        conn.commit()

    return added


def main():
    sqlite_added = migrate_sqlite()

    print(
        "SQLITE ADDED:",
        sqlite_added,
    )

    pg_added = migrate_postgres()

    print(
        "POSTGRES ADDED:",
        pg_added,
    )

    print(
        "ELIGIBILITY STATE MIGRATION COMPLETE"
    )


if __name__ == "__main__":
    main()
