from __future__ import annotations

from .postgres_repository import pg_conn


DDL = """
CREATE TABLE IF NOT EXISTS source_health (
    source_key TEXT PRIMARY KEY,

    employer_name TEXT NOT NULL,
    source_type TEXT,
    ats TEXT NOT NULL,
    token TEXT,
    careers_url TEXT,

    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    source_verified BOOLEAN NOT NULL DEFAULT TRUE,

    last_attempt_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_failure_at TIMESTAMPTZ,

    last_raw_jobs INTEGER NOT NULL DEFAULT 0,
    last_eligible_jobs INTEGER NOT NULL DEFAULT 0,
    last_excluded_jobs INTEGER NOT NULL DEFAULT 0,
    last_added_jobs INTEGER NOT NULL DEFAULT 0,
    last_updated_jobs INTEGER NOT NULL DEFAULT 0,
    last_disappeared_jobs INTEGER NOT NULL DEFAULT 0,

    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_run_history (
    id BIGSERIAL PRIMARY KEY,

    source_key TEXT NOT NULL
        REFERENCES source_health(source_key)
        ON DELETE CASCADE,

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    success BOOLEAN NOT NULL,

    raw_jobs INTEGER NOT NULL DEFAULT 0,
    eligible_jobs INTEGER NOT NULL DEFAULT 0,
    excluded_jobs INTEGER NOT NULL DEFAULT 0,
    added_jobs INTEGER NOT NULL DEFAULT 0,
    updated_jobs INTEGER NOT NULL DEFAULT 0,
    disappeared_jobs INTEGER NOT NULL DEFAULT 0,

    duration_ms INTEGER,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_health_employer
    ON source_health(LOWER(employer_name));

CREATE INDEX IF NOT EXISTS idx_source_health_ats
    ON source_health(ats);

CREATE INDEX IF NOT EXISTS idx_source_health_last_success
    ON source_health(last_success_at DESC);

CREATE INDEX IF NOT EXISTS idx_source_runs_source
    ON source_run_history(source_key, completed_at DESC);

CREATE INDEX IF NOT EXISTS idx_source_runs_success
    ON source_run_history(success, completed_at DESC);
"""


def main():
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(DDL)
        conn.commit()

    print("V9.0 source-health migration complete.")


if __name__ == "__main__":
    main()
