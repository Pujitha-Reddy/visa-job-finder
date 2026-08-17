from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from .v84_query_rules import (
    strict_eligibility_sql,
    strict_freshness_sql,
    strict_freshness_params,
)

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

SORT_SQL = {
    "best": """
        overall_score DESC NULLS LAST,
        NULLIF(source_published_at, '')::timestamptz DESC NULLS LAST,
        source_confidence_score DESC NULLS LAST
    """,
    "newest": """
        NULLIF(source_published_at, '')::timestamptz DESC NULLS LAST,
        overall_score DESC NULLS LAST
    """,
    "sponsor": """
        sponsorship_score DESC NULLS LAST,
        overall_score DESC NULLS LAST,
        NULLIF(source_published_at, '')::timestamptz DESC NULLS LAST
    """,
    "experience": """
        min_experience_years ASC NULLS LAST,
        overall_score DESC NULLS LAST,
        NULLIF(source_published_at, '')::timestamptz DESC NULLS LAST
    """,
    "company": """
        LOWER(company_name_raw) ASC,
        overall_score DESC NULLS LAST,
        NULLIF(source_published_at, '')::timestamptz DESC NULLS LAST
    """,
}


def get_database_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is missing.")
    return url


def pg_conn():
    return psycopg.connect(
        get_database_url(),
        connect_timeout=20,
        row_factory=dict_row,
    )


def fetch_jobs(
    hours=72,
    source_type="DIRECT_EMPLOYER",
    agency=None,
    employment_detail_type=None,
    visa_detail_status=None,
    experience_band=None,
    work_arrangement=None,
    application_status="NEW",
    query_text=None,
    sort="best",
):
    clauses = ["1=1"]
    params = []

    if application_status == "NEW":
        clauses.extend([strict_freshness_sql(), strict_eligibility_sql()])
        params.extend(strict_freshness_params(hours))

    if source_type:
        clauses.append("AND source_type = %s")
        params.append(source_type)
    if agency:
        clauses.append("AND agency_name = %s")
        params.append(agency)
    if employment_detail_type:
        clauses.append("AND employment_detail_type = %s")
        params.append(employment_detail_type)
    if visa_detail_status:
        clauses.append("AND visa_detail_status = %s")
        params.append(visa_detail_status)
    if experience_band:
        clauses.append("AND experience_band = %s")
        params.append(experience_band)
    if work_arrangement:
        clauses.append("AND work_arrangement = %s")
        params.append(work_arrangement)
    if application_status != "ALL":
        clauses.append("AND application_status = %s")
        params.append(application_status)

    if query_text and query_text.strip():
        q = f"%{query_text.strip()}%"
        clauses.append("""
            AND (
                title ILIKE %s
                OR company_name_raw ILIKE %s
                OR COALESCE(location_raw, '') ILIKE %s
            )
        """)
        params.extend([q, q, q])

    order_by = SORT_SQL.get(sort, SORT_SQL["best"])

    query = f"""
        SELECT *
        FROM jobs
        WHERE {' '.join(clauses)}
        ORDER BY {order_by}
        LIMIT 2000
    """

    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(query, params)
        return cur.fetchall()


def fetch_stats(hours=72, source_type="DIRECT_EMPLOYER"):
    clauses = ["1=1", strict_freshness_sql(), strict_eligibility_sql()]
    params = strict_freshness_params(hours)

    if source_type:
        clauses.append("AND source_type = %s")
        params.append(source_type)

    live_query = f"""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE work_arrangement='REMOTE') AS remote,
            COUNT(*) FILTER (WHERE work_arrangement='HYBRID') AS hybrid,
            COUNT(*) FILTER (WHERE work_arrangement='ONSITE') AS onsite,
            COUNT(*) FILTER (WHERE decision='NEEDS_REVIEW') AS review_count,
            COUNT(*) FILTER (WHERE overall_score >= 80) AS strong_matches
        FROM jobs
        WHERE {' '.join(clauses)}
          AND application_status='NEW'
    """

    history_query = """
        SELECT
            COUNT(*) FILTER (WHERE application_status='SAVED') AS saved,
            COUNT(*) FILTER (WHERE application_status='APPLIED') AS applied,
            COUNT(*) FILTER (WHERE application_status='INTERVIEW') AS interviews,
            COUNT(*) FILTER (WHERE application_status='REJECTED') AS rejected,
            COUNT(*) FILTER (WHERE application_status='SKIPPED') AS skipped
        FROM jobs
    """

    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(live_query, params)
        live = cur.fetchone() or {}
        cur.execute(history_query)
        history = cur.fetchone() or {}
        return {**live, **history}


def fetch_facets():
    cols = {
        "source_type": "source_type",
        "agency": "agency_name",
        "employment_detail_type": "employment_detail_type",
        "visa_detail_status": "visa_detail_status",
        "experience_band": "experience_band",
        "work_arrangement": "work_arrangement",
    }
    out = {}
    with pg_conn() as conn, conn.cursor() as cur:
        for key, col in cols.items():
            cur.execute(
                f"""
                SELECT COALESCE({col}, 'UNKNOWN') AS value,
                       COUNT(*) AS count
                FROM jobs
                GROUP BY COALESCE({col}, 'UNKNOWN')
                ORDER BY count DESC
                """
            )
            out[key] = cur.fetchall()
    return out


def update_application_status(job_id, status):
    allowed = {"NEW", "SAVED", "APPLIED", "INTERVIEW", "REJECTED", "SKIPPED"}
    if status not in allowed:
        raise ValueError(f"Unsupported application status: {status}")

    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE jobs
            SET application_status=%s,
                date_applied=CASE
                    WHEN %s='APPLIED'
                    THEN COALESCE(date_applied, CURRENT_TIMESTAMP::text)
                    ELSE date_applied
                END
            WHERE id=%s
            RETURNING id, application_status, date_applied
            """,
            (status, status, job_id),
        )
        row = cur.fetchone()
        conn.commit()
        return row


def health():
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                current_database() AS database,
                current_user AS username,
                COUNT(*) AS jobs
            FROM jobs
            """
        )
        return cur.fetchone()
