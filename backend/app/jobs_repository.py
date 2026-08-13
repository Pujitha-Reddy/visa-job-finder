from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "jobs.db"

JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    apply_url TEXT,
    company_name_raw TEXT NOT NULL,
    source_type TEXT DEFAULT 'DIRECT_EMPLOYER',
    ats TEXT,
    title TEXT NOT NULL,
    description TEXT,
    location_raw TEXT,
    posted_at TEXT,
    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    min_experience_years REAL,
    max_experience_years REAL,
    experience_text TEXT,
    experience_match INTEGER,
    experience_band TEXT,
    work_arrangement TEXT DEFAULT 'UNKNOWN',
    employment_type TEXT DEFAULT 'UNKNOWN',
    visa_language_status TEXT DEFAULT 'UNKNOWN',
    visa_evidence_text TEXT,
    h1b_history_strength TEXT DEFAULT 'UNKNOWN',
    sponsorship_score REAL DEFAULT 0,
    overall_score REAL DEFAULT 0,
    decision TEXT DEFAULT 'NEEDS_REVIEW',
    decision_reason TEXT,
    application_status TEXT DEFAULT 'NEW',
    date_applied TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at);
"""

def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_jobs():
    with _conn() as conn:
        conn.executescript(JOB_SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "visa_detail_status" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN visa_detail_status TEXT")
        if "employment_detail_type" not in cols:
            conn.execute("ALTER TABLE jobs ADD COLUMN employment_detail_type TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_visa_detail_status ON jobs(visa_detail_status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_employment_detail_type ON jobs(employment_detail_type)")
        conn.commit()

def upsert_job(job: dict) -> str:
    init_jobs()
    fields = [
        "external_id","source","source_url","apply_url","company_name_raw",
        "source_type","ats","title","description","location_raw","posted_at",
        "min_experience_years","max_experience_years","experience_text",
        "experience_match","experience_band","work_arrangement","employment_type","employment_detail_type",
        "visa_language_status","visa_detail_status","visa_evidence_text","decision","decision_reason","agency_name","end_client"
    ]
    with _conn() as conn:
        existing = conn.execute("SELECT id FROM jobs WHERE source_url=?", (job["source_url"],)).fetchone()
        if existing:
            assignments = ", ".join(f"{f}=?" for f in fields if f != "source_url")
            vals = [job.get(f) for f in fields if f != "source_url"]
            conn.execute(
                f"UPDATE jobs SET {assignments}, last_seen_at=CURRENT_TIMESTAMP WHERE id=?",
                vals + [existing["id"]],
            )
            conn.commit()
            return "UPDATED"

        placeholders = ",".join("?" for _ in fields)
        conn.execute(
            f"INSERT INTO jobs ({','.join(fields)}) VALUES ({placeholders})",
            [job.get(f) for f in fields],
        )
        conn.commit()
        return "ADDED"

def save_jobs(jobs: list[dict]) -> dict:
    stats = {"found": len(jobs), "added": 0, "updated": 0, "errors": 0}
    for job in jobs:
        if not job.get("source_url"):
            stats["errors"] += 1
            continue
        try:
            result = upsert_job(job)
            stats[result.lower()] += 1
        except Exception as exc:
            print(f"[SAVE ERROR] {job.get('company_name_raw')} / {job.get('title')}: {exc}")
            stats["errors"] += 1
    return stats
