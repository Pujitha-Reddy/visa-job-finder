from pathlib import Path
import sqlite3

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.db"

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    website TEXT,
    careers_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sponsor_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    source_year INTEGER,
    filings_count INTEGER,
    approved_count INTEGER,
    denied_count INTEGER,
    sponsor_strength TEXT CHECK (
        sponsor_strength IN ('STRONG','MEDIUM','LOW','UNKNOWN')
    ) DEFAULT 'UNKNOWN',
    evidence_url TEXT,
    last_verified_at TEXT,
    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id TEXT,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    apply_url TEXT,
    company_id INTEGER,
    company_name_raw TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    location_raw TEXT,
    country TEXT,
    posted_at TEXT,
    first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,

    min_experience_years REAL,
    max_experience_years REAL,
    experience_text TEXT,
    experience_match INTEGER,

    work_arrangement TEXT CHECK (
        work_arrangement IN ('REMOTE','HYBRID','ONSITE','UNKNOWN')
    ) DEFAULT 'UNKNOWN',

    employment_type TEXT CHECK (
        employment_type IN (
            'FULL_TIME',
            'CONTRACT_W2',
            'CONTRACT_C2C',
            'CONTRACT_UNKNOWN',
            'TEMPORARY',
            'INTERNSHIP',
            'UNKNOWN'
        )
    ) DEFAULT 'UNKNOWN',

    visa_language_status TEXT CHECK (
        visa_language_status IN (
            'SPONSORSHIP_AVAILABLE',
            'OPT_F1_MENTIONED',
            'NO_SPONSORSHIP',
            'RESTRICTED',
            'NOT_MENTIONED',
            'UNKNOWN'
        )
    ) DEFAULT 'UNKNOWN',

    visa_evidence_text TEXT,
    h1b_history_strength TEXT CHECK (
        h1b_history_strength IN ('STRONG','MEDIUM','LOW','UNKNOWN')
    ) DEFAULT 'UNKNOWN',

    sponsorship_score REAL DEFAULT 0,
    overall_score REAL DEFAULT 0,

    decision TEXT CHECK (
        decision IN ('APPLY','OK_TO_APPLY','NEEDS_REVIEW','SKIP')
    ) DEFAULT 'NEEDS_REVIEW',

    decision_reason TEXT,

    application_status TEXT CHECK (
        application_status IN (
            'NEW','SAVED','APPLIED','INTERVIEW','REJECTED','SKIPPED'
        )
    ) DEFAULT 'NEW',

    date_applied TEXT,
    notes TEXT,

    FOREIGN KEY(company_id) REFERENCES companies(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_posted_at
ON jobs(posted_at);

CREATE INDEX IF NOT EXISTS idx_jobs_decision
ON jobs(decision);

CREATE INDEX IF NOT EXISTS idx_jobs_work_arrangement
ON jobs(work_arrangement);

CREATE INDEX IF NOT EXISTS idx_jobs_employment_type
ON jobs(employment_type);

CREATE INDEX IF NOT EXISTS idx_jobs_application_status
ON jobs(application_status);

CREATE TABLE IF NOT EXISTS job_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    skill TEXT NOT NULL,
    matched_to_profile INTEGER DEFAULT 0,
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS collection_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    hours_lookback INTEGER NOT NULL,
    jobs_found INTEGER DEFAULT 0,
    jobs_added INTEGER DEFAULT 0,
    jobs_updated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'RUNNING',
    error_message TEXT
);
"""


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_connection() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
