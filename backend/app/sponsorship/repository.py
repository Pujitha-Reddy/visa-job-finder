from __future__ import annotations

from ..database import get_connection
from .normalize import normalize_company_name
from .scoring import score_sponsor_history


def ensure_company(display_name: str) -> int:
    canonical = normalize_company_name(display_name)

    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM companies WHERE canonical_name = ?", (canonical,)
        ).fetchone()

        if row:
            return row["id"]

        cur = conn.execute(
            """
            INSERT INTO companies (canonical_name, display_name)
            VALUES (?, ?)
            """,
            (canonical, display_name),
        )
        conn.commit()
        return cur.lastrowid


def add_sponsor_record(
    company_name: str,
    source: str,
    source_year: int | None,
    filings_count: int = 0,
    approved_count: int = 0,
    denied_count: int = 0,
    evidence_url: str | None = None,
):
    company_id = ensure_company(company_name)

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sponsor_history (
                company_id, source, source_year, filings_count,
                approved_count, denied_count, evidence_url, last_verified_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                company_id, source.upper(), source_year, filings_count,
                approved_count, denied_count, evidence_url
            ),
        )
        conn.commit()


def sponsor_profile(company_name: str) -> dict:
    canonical = normalize_company_name(company_name)

    with get_connection() as conn:
        company = conn.execute(
            "SELECT * FROM companies WHERE canonical_name = ?", (canonical,)
        ).fetchone()

        if not company:
            return {
                "canonical_name": canonical,
                "strength": "UNKNOWN",
                "score": 0,
                "records": [],
            }

        rows = conn.execute(
            "SELECT * FROM sponsor_history WHERE company_id = ?",
            (company["id"],),
        ).fetchall()

    records = [dict(r) for r in rows]
    score = score_sponsor_history(records)

    return {
        "canonical_name": canonical,
        **score,
        "records": records,
    }
