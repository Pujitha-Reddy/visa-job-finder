from .jobs_repository import _conn, init_jobs

def migrate():
    init_jobs()
    with _conn() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        added = []
        for name, ddl in {
            "agency_name": "TEXT",
            "end_client": "TEXT",
        }.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {ddl}")
                added.append(name)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_agency_name ON jobs(agency_name)")
        conn.commit()
    print({"migration":"ok","columns_added":added})

if __name__ == "__main__":
    migrate()
