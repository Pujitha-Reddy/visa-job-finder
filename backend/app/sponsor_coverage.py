from .jobs_repository import _conn, init_jobs

if __name__ == "__main__":
    init_jobs()
    with _conn() as conn:
        rollup = conn.execute("SELECT COUNT(*) c FROM sponsor_rollup").fetchone()["c"]
        total = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
        matched = conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE h1b_history_strength <> 'UNKNOWN'"
        ).fetchone()["c"]
        top = [dict(r) for r in conn.execute("""
            SELECT company_name_raw, h1b_history_strength,
                   ROUND(MAX(sponsorship_score),0) sponsor_score,
                   COUNT(*) jobs
            FROM jobs
            GROUP BY company_name_raw, h1b_history_strength
            ORDER BY jobs DESC
            LIMIT 25
        """).fetchall()]
    print({
        "sponsor_rollup_rows":rollup,
        "jobs_total":total,
        "jobs_with_history":matched,
        "job_match_percent":round(matched/total*100,1) if total else 0,
        "top_companies":top
    })
