from .normalization import normalize_company_name
from .score_v2 import calculate_sponsorship_score
from ..jobs_repository import _conn, init_jobs

ALIASES = {
    "openai": ["openai opco", "openai"],
    "insight global": ["insight global"],
    "robert half": ["robert half international", "robert half"],
    "randstad": ["randstad"],
}

def _load_rollup(conn):
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sponsor_rollup'"
    ).fetchone()
    if not exists:
        return {}
    rows = conn.execute("""
        SELECT normalized_name, total_filings, recent_filings, sponsor_strength
        FROM sponsor_rollup
    """).fetchall()
    return {
        r["normalized_name"]:{
            "total":int(r["total_filings"] or 0),
            "recent":int(r["recent_filings"] or 0),
            "strength":r["sponsor_strength"] or "UNKNOWN"
        }
        for r in rows
    }

def _match(history, entity):
    base = normalize_company_name(entity)
    keys = [base] + ALIASES.get(base, [])
    for key in keys:
        if key in history:
            return history[key]
    if len(base) >= 6:
        matches = [v for k, v in history.items() if k.startswith(base + " ") or base.startswith(k + " ")]
        if len(matches) == 1:
            return matches[0]
    return {"total":0, "recent":0, "strength":"UNKNOWN"}

def enrich_all_jobs_v2():
    init_jobs()
    with _conn() as conn:
        history = _load_rollup(conn)
        jobs = [dict(r) for r in conn.execute("""
            SELECT id, company_name_raw, agency_name,
                   visa_language_status, visa_detail_status
            FROM jobs
        """).fetchall()]

        matched = 0
        for job in jobs:
            entity = job.get("agency_name") or job.get("company_name_raw")
            hist = _match(history, entity)
            strength = hist["strength"]
            if strength != "UNKNOWN":
                matched += 1

            score = calculate_sponsorship_score(
                strength,
                job.get("visa_detail_status"),
                job.get("visa_language_status"),
            )
            conn.execute("""
                UPDATE jobs
                SET h1b_history_strength=?, sponsorship_score=?
                WHERE id=?
            """, (strength, score, job["id"]))
        conn.commit()

    return {
        "jobs_processed":len(jobs),
        "history_matches":matched,
        "history_unknown":len(jobs)-matched,
        "history_records_loaded":len(history),
    }
