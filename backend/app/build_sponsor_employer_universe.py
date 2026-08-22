from __future__ import annotations

from .database import get_connection


def sponsor_strength_score(value: str) -> int:
    value = (value or "UNKNOWN").upper()

    return {
        "STRONG": 40,
        "MEDIUM": 25,
        "WEAK": 10,
        "UNKNOWN": 0,
    }.get(value, 0)


def filing_score(recent: int) -> int:
    recent = int(recent or 0)

    if recent >= 1000:
        return 40
    if recent >= 500:
        return 35
    if recent >= 200:
        return 30
    if recent >= 100:
        return 25
    if recent >= 50:
        return 20
    if recent >= 20:
        return 15
    if recent >= 5:
        return 10
    if recent >= 1:
        return 5

    return 0


def recency_score(latest_year: int | None) -> int:
    if latest_year is None:
        return 0

    if latest_year >= 2026:
        return 20
    if latest_year >= 2025:
        return 15
    if latest_year >= 2024:
        return 10
    if latest_year >= 2023:
        return 5

    return 0


def priority_band(score: float) -> str:
    if score >= 80:
        return "TIER_1"
    if score >= 60:
        return "TIER_2"
    if score >= 40:
        return "TIER_3"
    return "LOW"


def main():
    with get_connection() as conn:
        rollups = conn.execute("""
            SELECT *
            FROM sponsor_rollup
        """).fetchall()

        registry = {
            row["canonical_name"]: row["id"]
            for row in conn.execute("""
                SELECT id, canonical_name
                FROM companies
            """).fetchall()
        }

        count = 0

        for row in rollups:
            normalized = row["normalized_name"]

            score = (
                sponsor_strength_score(
                    row["sponsor_strength"]
                )
                + filing_score(
                    row["recent_filings"]
                )
                + recency_score(
                    row["latest_year"]
                )
            )

            band = priority_band(score)

            matched_id = registry.get(normalized)

            conn.execute("""
                INSERT INTO sponsor_employer_universe (
                    normalized_name,
                    display_name,
                    latest_year,
                    total_filings,
                    recent_filings,
                    approved_count,
                    denied_count,
                    sponsor_strength,
                    dol_present,
                    uscis_present,
                    matched_employer_id,
                    already_in_registry,
                    priority_score,
                    priority_band,
                    last_seen_at,
                    last_ranked_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    1, 0,
                    ?, ?,
                    ?, ?,
                    CURRENT_TIMESTAMP,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(normalized_name)
                DO UPDATE SET
                    display_name=excluded.display_name,
                    latest_year=excluded.latest_year,
                    total_filings=excluded.total_filings,
                    recent_filings=excluded.recent_filings,
                    approved_count=excluded.approved_count,
                    denied_count=excluded.denied_count,
                    sponsor_strength=excluded.sponsor_strength,
                    dol_present=1,
                    matched_employer_id=excluded.matched_employer_id,
                    already_in_registry=excluded.already_in_registry,
                    priority_score=excluded.priority_score,
                    priority_band=excluded.priority_band,
                    last_seen_at=CURRENT_TIMESTAMP,
                    last_ranked_at=CURRENT_TIMESTAMP
            """, (
                normalized,
                row["display_name"],
                row["latest_year"],
                row["total_filings"],
                row["recent_filings"],
                row["approved_count"],
                row["denied_count"],
                row["sponsor_strength"],
                matched_id,
                1 if matched_id else 0,
                score,
                band,
            ))

            count += 1

        conn.commit()

    print("SPONSOR EMPLOYERS UPSERTED:", count)


if __name__ == "__main__":
    main()
