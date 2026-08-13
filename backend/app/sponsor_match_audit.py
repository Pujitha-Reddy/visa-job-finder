from difflib import SequenceMatcher

from .jobs_repository import _conn, init_jobs
from .sponsorship.normalization import normalize_company_name
from .sponsorship.matcher_v11 import best_unique_match

if __name__ == "__main__":
    init_jobs()
    with _conn() as conn:
        sponsor_names = [r["normalized_name"] for r in conn.execute(
            "SELECT normalized_name FROM sponsor_rollup"
        ).fetchall()]

        companies = [dict(r) for r in conn.execute("""
            SELECT company_name_raw, agency_name, COUNT(*) AS jobs
            FROM jobs
            WHERE h1b_history_strength='UNKNOWN'
            GROUP BY company_name_raw, agency_name
            ORDER BY jobs DESC
        """).fetchall()]

    print({"unmatched_companies": len(companies)})
    for row in companies[:100]:
        entity = row["agency_name"] or row["company_name_raw"]
        match, score, method = best_unique_match(entity, sponsor_names)

        # Top 3 informational candidates even when not safe to auto-match.
        base = normalize_company_name(entity)
        top = sorted(
            ((SequenceMatcher(None, base, s).ratio(), s) for s in sponsor_names),
            reverse=True
        )[:3]

        print({
            "company": entity,
            "jobs": row["jobs"],
            "safe_match": match,
            "safe_method": method,
            "safe_score": round(score, 3),
            "top_candidates": [(round(s, 3), n) for s, n in top],
        })
