from .jobs_repository import _conn, init_jobs

def migrate():
    init_jobs()
    with _conn() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        added = []
        if "employment_detail_type" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN employment_detail_type TEXT")
            added.append("employment_detail_type")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_jobs_employment_detail_type "
            "ON jobs(employment_detail_type)"
        )
        conn.commit()
    print({"migration":"ok","columns_added":added})

if __name__ == "__main__":
    migrate()
