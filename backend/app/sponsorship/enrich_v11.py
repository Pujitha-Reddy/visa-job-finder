from __future__ import annotations

from .score_v2 import calculate_sponsorship_score
from .matcher_v11 import best_unique_match
from ..jobs_repository import _conn, init_jobs


def _load_rollup(conn):
    rows = conn.execute("""
        SELECT
            normalized_name,
            sponsor_strength,
            total_filings,
            recent_filings
        FROM sponsor_rollup
    """).fetchall()

    return {
        r["normalized_name"]: {
            "strength": r["sponsor_strength"] or "UNKNOWN",
            "total": int(r["total_filings"] or 0),
            "recent": int(r["recent_filings"] or 0),
        }
        for r in rows
    }


def enrich_all_jobs_v11():
    init_jobs()

    with _conn() as conn:
        history = _load_rollup(conn)
        sponsor_names = list(history)

        jobs = [
            dict(r)
            for r in conn.execute("""
                SELECT
                    id,
                    company_name_raw,
                    agency_name,
                    visa_language_status,
                    visa_detail_status
                FROM jobs
            """).fetchall()
        ]

        matched = 0
        alias_or_fuzzy = 0
        unknown = 0

        for job in jobs:
            entity = (
                job.get("agency_name")
                or job.get("company_name_raw")
            )

            # IMPORTANT:
            # Always use the V7.11 matcher.
            #
            # candidate_keys() already checks curated aliases first
            # and the generic company name last.
            #
            # This prevents "Amazon" from matching the tiny
            # "Amazon LLC" DOL record before checking
            # "Amazon.com Services LLC".
            match_name, confidence, method = best_unique_match(
                entity,
                sponsor_names,
            )

            if match_name:
                hist = history[match_name]
                strength = hist["strength"]

                matched += 1

                if method != "EXACT":
                    alias_or_fuzzy += 1
            else:
                strength = "UNKNOWN"
                unknown += 1

            score = calculate_sponsorship_score(
                strength,
                job.get("visa_detail_status"),
                job.get("visa_language_status"),
            )

            conn.execute("""
                UPDATE jobs
                SET
                    h1b_history_strength=?,
                    sponsorship_score=?
                WHERE id=?
            """, (
                strength,
                score,
                job["id"],
            ))

        conn.commit()

    return {
        "jobs_processed": len(jobs),
        "history_matches": matched,
        "alias_or_fuzzy_matches": alias_or_fuzzy,
        "history_unknown": unknown,
        "history_records_loaded": len(history),
    }