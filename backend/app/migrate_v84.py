from __future__ import annotations
import os
from pathlib import Path
import sqlite3
import psycopg
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parents[1]
load_dotenv(BASE/".env")

SQLITE = BASE/"data"/"jobs.db"
FIELDS = [
    ("source_published_at","TEXT"),
    ("source_updated_at","TEXT"),
    ("effective_posted_at","TEXT"),
    ("freshness_confidence","TEXT"),
    ("freshness_source","TEXT"),
    ("source_confidence_score","REAL DEFAULT 0"),
    ("source_confidence_label","TEXT"),
    ("dedupe_key","TEXT"),
]

def migrate_sqlite():
    conn = sqlite3.connect(SQLITE)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    added=[]
    for name, typ in FIELDS:
        if name not in cols:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {typ}")
            added.append(name)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_dedupe_key ON jobs(dedupe_key)")
    conn.commit(); conn.close()
    return added

def migrate_postgres():
    url=os.getenv("DATABASE_URL")
    if not url:
        return []
    added=[]
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.execute("""
          SELECT column_name FROM information_schema.columns
          WHERE table_schema='public' AND table_name='jobs'
        """)
        cols={r[0] for r in cur.fetchall()}
        for name, typ in FIELDS:
            if name not in cols:
                pgtyp = "DOUBLE PRECISION DEFAULT 0" if name=="source_confidence_score" else "TEXT"
                cur.execute(f'ALTER TABLE jobs ADD COLUMN "{name}" {pgtyp}')
                added.append(name)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_dedupe_key ON jobs(dedupe_key)")
        conn.commit()
    return added

if __name__=="__main__":
    print({"sqlite_added":migrate_sqlite(), "postgres_added":migrate_postgres()})
