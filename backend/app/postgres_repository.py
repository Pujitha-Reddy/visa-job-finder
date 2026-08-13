import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

def get_database_url():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is missing.")
    return url

def pg_conn():
    return psycopg.connect(get_database_url(), connect_timeout=20, row_factory=dict_row)

def fetch_jobs(hours=72, source_type=None, agency=None, employment_detail_type=None,
               visa_detail_status=None, experience_band=None, work_arrangement=None,
               application_status="NEW"):
    clauses = ["1=1", "(posted_at IS NULL OR posted_at::timestamp >= NOW() - (%s * INTERVAL '1 hour'))"]
    params = [hours]
    mapping = {
        "source_type": source_type,
        "agency_name": agency,
        "employment_detail_type": employment_detail_type,
        "visa_detail_status": visa_detail_status,
        "experience_band": experience_band,
        "work_arrangement": work_arrangement,
    }
    for col, value in mapping.items():
        if value:
            clauses.append(f"{col} = %s")
            params.append(value)
    if application_status != "ALL":
        clauses.append("application_status = %s")
        params.append(application_status)
    q = f'''
        SELECT * FROM jobs
        WHERE {" AND ".join(clauses)}
        ORDER BY overall_score DESC NULLS LAST,
                 COALESCE(NULLIF(posted_at,'')::timestamp, NULLIF(last_seen_at,'')::timestamp) DESC NULLS LAST
        LIMIT 2000
    '''
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute(q, params)
        return cur.fetchall()

def fetch_stats(hours=72):
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute('''
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE work_arrangement='REMOTE') AS remote,
                   COUNT(*) FILTER (WHERE work_arrangement='HYBRID') AS hybrid,
                   COUNT(*) FILTER (WHERE work_arrangement='ONSITE') AS onsite,
                   COUNT(*) FILTER (WHERE decision='NEEDS_REVIEW') AS review_count
            FROM jobs
            WHERE posted_at IS NULL OR posted_at::timestamp >= NOW() - (%s * INTERVAL '1 hour')
        ''', (hours,))
        return cur.fetchone()

def fetch_facets():
    cols = {
        "source_type":"source_type","agency":"agency_name",
        "employment_detail_type":"employment_detail_type",
        "visa_detail_status":"visa_detail_status",
        "experience_band":"experience_band","work_arrangement":"work_arrangement"
    }
    out = {}
    with pg_conn() as conn, conn.cursor() as cur:
        for key, col in cols.items():
            cur.execute(f'''
                SELECT COALESCE({col}, 'UNKNOWN') AS value, COUNT(*) AS count
                FROM jobs GROUP BY COALESCE({col}, 'UNKNOWN') ORDER BY count DESC
            ''')
            out[key] = cur.fetchall()
    return out

def update_application_status(job_id, status):
    allowed = {"NEW","SAVED","APPLIED","INTERVIEW","REJECTED","SKIPPED"}
    if status not in allowed:
        raise ValueError(f"Unsupported application status: {status}")
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute('''
            UPDATE jobs
            SET application_status=%s,
                date_applied=CASE WHEN %s='APPLIED'
                    THEN COALESCE(date_applied, CURRENT_TIMESTAMP::text)
                    ELSE date_applied END
            WHERE id=%s
            RETURNING id, application_status, date_applied
        ''', (status, status, job_id))
        row = cur.fetchone()
        conn.commit()
        return row

def health():
    with pg_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT current_database() AS database, current_user AS username, COUNT(*) AS jobs FROM jobs")
        return cur.fetchone()
