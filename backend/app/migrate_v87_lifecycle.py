import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "jobs.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)

    cols = {
        row[1]
        for row in conn.execute(
            "PRAGMA table_info(jobs)"
        ).fetchall()
    }

    added = []

    if "is_active" not in cols:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN is_active INTEGER DEFAULT 1"
        )
        added.append("is_active")

    if "last_verified_at" not in cols:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN last_verified_at TEXT"
        )
        added.append("last_verified_at")

    if "disappeared_at" not in cols:
        conn.execute(
            "ALTER TABLE jobs ADD COLUMN disappeared_at TEXT"
        )
        added.append("disappeared_at")

    conn.execute("""
        UPDATE jobs
        SET is_active = 1
        WHERE is_active IS NULL
    """)

    conn.commit()
    conn.close()

    print({"sqlite_added": added})


if __name__ == "__main__":
    migrate()
