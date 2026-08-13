from .jobs_repository import _conn, init_jobs

def migrate():
    init_jobs()
    with _conn() as conn:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        added = []
        if "visa_detail_status" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN visa_detail_status TEXT")
            added.append("visa_detail_status")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_visa_detail_status ON jobs(visa_detail_status)")
        conn.commit()
    print({"migration":"ok","columns_added":added})

if __name__ == "__main__":
    migrate()
