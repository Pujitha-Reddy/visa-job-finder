SCHEMA = '''
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS employers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'DIRECT_EMPLOYER',
    website TEXT,
    careers_url TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employer_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id INTEGER NOT NULL,
    ats TEXT NOT NULL,
    token TEXT,
    careers_url TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_checked_at TEXT,
    last_success_at TEXT,
    active_jobs INTEGER DEFAULT 0,
    source_verified INTEGER DEFAULT 0,
    notes TEXT,
    FOREIGN KEY(employer_id) REFERENCES employers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_employer_sources_enabled ON employer_sources(enabled);
CREATE INDEX IF NOT EXISTS idx_employer_sources_ats ON employer_sources(ats);
'''
