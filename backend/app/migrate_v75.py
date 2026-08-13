from .jobs_repository import _conn, init_jobs

REQUIRED_COLUMNS = {
    "source_type": "TEXT DEFAULT 'DIRECT_EMPLOYER'",
    "ats": "TEXT",
    "experience_band": "TEXT",
}

def column_names(conn, table):
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}

def migrate():
    init_jobs()
    with _conn() as conn:
        cols = column_names(conn, "jobs")
        added = []
        for name, ddl in REQUIRED_COLUMNS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {ddl}")
                added.append(name)

        # Add indexes only after columns exist.
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source_type ON jobs(source_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_experience_band ON jobs(experience_band)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_ats ON jobs(ats)")
        conn.commit()

    print({"migration":"ok","columns_added":added})

if __name__ == "__main__":
    migrate()
