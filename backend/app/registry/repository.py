from pathlib import Path
import sqlite3
import re

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "jobs.db"

def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def normalize_company_name(name: str) -> str:
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    for suffix in (" llc", " inc", " incorporated", " corporation", " corp", " ltd", " limited"):
        if s.endswith(suffix):
            s = s[:-len(suffix)].strip()
    return s

def init_registry():
    from .schema import SCHEMA
    with conn() as c:
        c.executescript(SCHEMA)
        c.commit()

def upsert_employer(display_name, source_type="DIRECT_EMPLOYER", careers_url=None):
    canonical = normalize_company_name(display_name)
    with conn() as c:
        row = c.execute("SELECT id FROM employers WHERE canonical_name=?", (canonical,)).fetchone()
        if row:
            c.execute(
                "UPDATE employers SET display_name=?, source_type=?, careers_url=COALESCE(?, careers_url), updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (display_name, source_type, careers_url, row["id"])
            )
            c.commit()
            return row["id"]
        cur = c.execute(
            "INSERT INTO employers(canonical_name, display_name, source_type, careers_url) VALUES(?,?,?,?)",
            (canonical, display_name, source_type, careers_url)
        )
        c.commit()
        return cur.lastrowid

def upsert_source(employer_id, ats, token=None, careers_url=None, enabled=True, notes=None):
    with conn() as c:
        row = c.execute(
            "SELECT id FROM employer_sources WHERE employer_id=? AND ats=? AND COALESCE(token,'')=COALESCE(?, '') AND COALESCE(careers_url,'')=COALESCE(?, '')",
            (employer_id, ats.upper(), token, careers_url)
        ).fetchone()
        if row:
            c.execute(
                "UPDATE employer_sources SET enabled=?, notes=? WHERE id=?",
                (1 if enabled else 0, notes, row["id"])
            )
        else:
            c.execute(
                "INSERT INTO employer_sources(employer_id, ats, token, careers_url, enabled, notes) VALUES(?,?,?,?,?,?)",
                (employer_id, ats.upper(), token, careers_url, 1 if enabled else 0, notes)
            )
        c.commit()

def list_enabled_sources():
    with conn() as c:
        rows = c.execute("""
            SELECT es.id AS source_id, e.display_name AS employer_name, e.source_type,
                   es.ats, es.token, COALESCE(es.careers_url, e.careers_url) AS careers_url
            FROM employer_sources es
            JOIN employers e ON e.id = es.employer_id
            WHERE es.enabled=1 AND e.enabled=1
            ORDER BY e.display_name
        """).fetchall()
    return [dict(r) for r in rows]

def mark_source_result(source_id, active_jobs, success):
    with conn() as c:
        if success:
            c.execute("""
                UPDATE employer_sources
                SET last_checked_at=CURRENT_TIMESTAMP,
                    last_success_at=CURRENT_TIMESTAMP,
                    active_jobs=?,
                    source_verified=1
                WHERE id=?
            """, (active_jobs, source_id))
        else:
            c.execute(
                "UPDATE employer_sources SET last_checked_at=CURRENT_TIMESTAMP WHERE id=?",
                (source_id,)
            )
        c.commit()
