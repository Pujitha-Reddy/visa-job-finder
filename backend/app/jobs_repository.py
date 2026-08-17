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
"""

V84_COLUMNS = {
    "visa_detail_status": "TEXT",
    "employment_detail_type": "TEXT",
    "agency_name": "TEXT",
    "end_client": "TEXT",
    "source_published_at": "TEXT",
    "source_updated_at": "TEXT",
    "effective_posted_at": "TEXT",
    "freshness_confidence": "TEXT",
    "freshness_source": "TEXT",
    "source_confidence_score": "REAL DEFAULT 0",
    "source_confidence_label": "TEXT",
    "dedupe_key": "TEXT",
}

def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_jobs():
    with _conn() as conn:
        conn.executescript(JOB_SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        for name, typ in V84_COLUMNS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {typ}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_posted_at ON jobs(posted_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_dedupe_key ON jobs(dedupe_key)")
        conn.commit()

def _existing_for_job(conn, job):
    row = conn.execute(
        "SELECT * FROM jobs WHERE source_url=?",
        (job["source_url"],),
    ).fetchone()
    if row:
        return row

    key = job.get("dedupe_key")
    if key:
        return conn.execute(
            "SELECT * FROM jobs WHERE dedupe_key=? ORDER BY id LIMIT 1",
            (key,),
        ).fetchone()
    return None

def _should_replace_source(existing, job):
    old_direct = (existing["source_type"] or "") == "DIRECT_EMPLOYER"
    new_direct = (job.get("source_type") or "") == "DIRECT_EMPLOYER"

    if old_direct and not new_direct:
        return False
    if new_direct and not old_direct:
        return True

    old_fresh = (existing["freshness_confidence"] or "") == "HIGH"
    new_fresh = (job.get("freshness_confidence") or "") == "HIGH"

    if old_fresh and not new_fresh:
        return False
    if new_fresh and not old_fresh:
        return True

    return False

def upsert_job(job: dict) -> str:
    init_jobs()

    fields = [
        "external_id","source","source_url","apply_url","company_name_raw",
        "source_type","ats","title","description","location_raw","posted_at",
        "min_experience_years","max_experience_years","experience_text",
        "experience_match","experience_band","work_arrangement","employment_type",
        "employment_detail_type","visa_language_status","visa_detail_status",
        "visa_evidence_text","decision","decision_reason","agency_name","end_client",
        "source_published_at","source_updated_at","effective_posted_at",
        "freshness_confidence","freshness_source","source_confidence_score",
        "source_confidence_label","dedupe_key",
    ]

    with _conn() as conn:
        existing = _existing_for_job(conn, job)

        if existing:
            # If this is a semantic duplicate from another source, prefer the better
            # source. Never overwrite Saved/Applied/etc.
            if existing["source_url"] != job["source_url"] and not _should_replace_source(existing, job):
                conn.execute(
                    "UPDATE jobs SET last_seen_at=CURRENT_TIMESTAMP WHERE id=?",
                    (existing["id"],),
                )
                conn.commit()
                return "UPDATED"

            assignments = ", ".join(f"{f}=?" for f in fields)
            vals = [job.get(f) for f in fields]

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
