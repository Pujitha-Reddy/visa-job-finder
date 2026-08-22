from __future__ import annotations

from collections import defaultdict

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from pydantic import BaseModel

from .canonical_db import (
    canonical_conn,
    adapt_sql,
    backend_name,
)


router = APIRouter(
    prefix="/v110",
    tags=["v110"],
)


APPLICATION_STATUSES = {
    "NEW",
    "SAVED",
    "APPLIED",
    "INTERVIEW",
    "REJECTED",
    "SKIPPED",
}


class ApplicationStatusUpdate(BaseModel):
    status: str


def ensure_application_state_table():
    """
    Canonical V110 application state.

    V80 stores state against the legacy jobs table. V110 uses
    canonical_jobs IDs, so application state must also be keyed
    by canonical_job_id rather than relying on legacy ID parity.
    """

    with canonical_conn() as conn:
        conn.execute(_sql("""
            CREATE TABLE IF NOT EXISTS
            canonical_job_application_state (
                canonical_job_id INTEGER PRIMARY KEY,
                application_status TEXT NOT NULL DEFAULT 'NEW',
                date_applied TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))

        conn.commit()


def update_canonical_application_status(
    canonical_job_id: int,
    status: str,
):
    status = (status or "").strip().upper()

    if status not in APPLICATION_STATUSES:
        raise ValueError(
            f"Unsupported application status: {status}"
        )

    ensure_application_state_table()

    with canonical_conn() as conn:

        existing = conn.execute(
            _sql("""
                SELECT id
                FROM canonical_jobs
                WHERE id=?
            """),
            (canonical_job_id,),
        ).fetchone()

        if not existing:
            return None

        conn.execute(
            _sql("""
                INSERT INTO canonical_job_application_state (
                    canonical_job_id,
                    application_status,
                    date_applied,
                    updated_at
                )
                VALUES (
                    ?,
                    ?,
                    CASE
                        WHEN ?='APPLIED'
                        THEN CAST(CURRENT_TIMESTAMP AS TEXT)
                        ELSE NULL
                    END,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT(canonical_job_id)
                DO UPDATE SET
                    application_status=excluded.application_status,
                    date_applied=
                        CASE
                            WHEN excluded.application_status='APPLIED'
                            THEN COALESCE(
                                canonical_job_application_state.date_applied,
                                CAST(CURRENT_TIMESTAMP AS TEXT)
                            )
                            ELSE canonical_job_application_state.date_applied
                        END,
                    updated_at=CURRENT_TIMESTAMP
            """),
            (
                canonical_job_id,
                status,
                status,
            ),
        )

        conn.commit()

        row = conn.execute(
            _sql("""
                SELECT
                    canonical_job_id AS id,
                    application_status,
                    date_applied
                FROM canonical_job_application_state
                WHERE canonical_job_id=?
            """),
            (canonical_job_id,),
        ).fetchone()

        return _serialize(row)


def _sql(query: str):
    return adapt_sql(query)

def _serialize(row):
    return dict(row)


def _diversify(
    rows,
    *,
    limit,
    max_per_employer,
):
    """
    Preserve ranking order while limiting employer
    concentration on a returned page.
    """

    selected = []
    employer_counts = defaultdict(int)

    # ------------------------------------------------------
    # Pass 1: diversified
    # ------------------------------------------------------

    for row in rows:
        job = dict(row)

        employer_id = job[
            "employer_identity_id"
        ]

        if (
            employer_counts[
                employer_id
            ]
            >= max_per_employer
        ):
            continue

        selected.append(job)

        employer_counts[
            employer_id
        ] += 1

        if len(selected) >= limit:
            return selected

    # ------------------------------------------------------
    # Pass 2: backfill if needed
    # ------------------------------------------------------

    selected_ids = {
        item["id"]
        for item in selected
    }

    for row in rows:
        job = dict(row)

        if job["id"] in selected_ids:
            continue

        selected.append(job)

        if len(selected) >= limit:
            break

    return selected


def _base_select():
    return """
        SELECT
            j.id,

            j.canonical_title AS title,
            j.canonical_location AS location,

            j.description,

            j.preferred_source_url AS source_url,
            j.preferred_apply_url AS apply_url,

            j.external_id,

            j.posted_at,
            j.first_seen_at,
            j.last_seen_at,

            j.source_count,
            j.best_source_confidence,

            i.id AS employer_identity_id,
            i.canonical_name AS employer,
            i.primary_domain AS employer_domain,

            e.software_role_family,
            e.software_role_score,

            e.country_code,
            e.state_code,
            e.city,

            e.work_arrangement,
            e.is_us_remote,

            e.min_experience_years,
            e.max_experience_years,
            e.seniority_band,

            e.sponsor_history_strength,
            e.sponsor_recent_filings,
            e.sponsor_recent_approvals,

            e.visa_language_status,
            e.visa_language_evidence,

            e.sponsorship_score,

            e.relevance_score,
            e.freshness_score,
            e.source_quality_score,
            e.overall_score,

            e.eligibility_reason,
            e.location_eligibility,
            e.experience_eligibility,
            e.sponsorship_eligibility,

            COALESCE(
                a.application_status,
                'NEW'
            ) AS application_status,

            a.date_applied

        FROM canonical_jobs j

        JOIN canonical_job_enrichment e
          ON e.canonical_job_id=j.id

        JOIN employer_identities i
          ON i.id=j.employer_identity_id

        LEFT JOIN canonical_job_application_state a
          ON a.canonical_job_id=j.id
    """


# ==========================================================
# Ranked job feed
# ==========================================================


@router.get("/jobs")
def jobs(
    q: str | None = None,

    company: str | None = None,

    role_family: str | None = None,

    state: str | None = None,

    work_arrangement: str | None = None,

    seniority: str | None = None,

    visa_status: str | None = None,

    sponsor_strength: str | None = None,

    application_status: str = "NEW",

    min_score: float = Query(
        default=0,
        ge=0,
        le=100,
    ),

    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),

    offset: int = Query(
        default=0,
        ge=0,
    ),

    diversify: bool = True,

    max_per_employer: int = Query(
        default=4,
        ge=1,
        le=50,
    ),
):
    ensure_application_state_table()

    clauses = [
        "j.is_active=1",
        "e.is_software_role=1",
        "e.is_eligible=1",
        "e.overall_score >= ?",
    ]

    params = [
        float(min_score),
    ]

    # ------------------------------------------------------
    # Search
    # ------------------------------------------------------

    if q:
        value = (
            f"%{q.strip().lower()}%"
        )

        clauses.append("""
            (
                LOWER(j.canonical_title) LIKE ?
                OR LOWER(i.canonical_name) LIKE ?
                OR LOWER(
                    COALESCE(
                        j.description,
                        ''
                    )
                ) LIKE ?
            )
        """)

        params.extend(
            [
                value,
                value,
                value,
            ]
        )

    # ------------------------------------------------------
    # Exact/filterable fields
    # ------------------------------------------------------

    if company:
        clauses.append(
            "LOWER(i.canonical_name)=?"
        )

        params.append(
            company.strip().lower()
        )

    if role_family:
        clauses.append(
            "e.software_role_family=?"
        )

        params.append(
            role_family.strip().upper()
        )

    if state:
        clauses.append(
            "e.state_code=?"
        )

        params.append(
            state.strip().upper()
        )

    if work_arrangement:
        clauses.append(
            "e.work_arrangement=?"
        )

        params.append(
            work_arrangement.strip().upper()
        )

    if seniority:
        clauses.append(
            "e.seniority_band=?"
        )

        params.append(
            seniority.strip().upper()
        )

    if visa_status:
        clauses.append(
            "e.visa_language_status=?"
        )

        params.append(
            visa_status.strip().upper()
        )

    if sponsor_strength:
        clauses.append(
            "e.sponsor_history_strength=?"
        )

        params.append(
            sponsor_strength.strip().upper()
        )

    if application_status:
        normalized_status = (
            application_status
            .strip()
            .upper()
        )

        # ALL means do not constrain by application state.
        if normalized_status != "ALL":

            if normalized_status not in APPLICATION_STATUSES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Unsupported application status: "
                        f"{normalized_status}"
                    ),
                )

            clauses.append(
                "COALESCE(a.application_status, 'NEW')=?"
            )

            params.append(
                normalized_status
            )

    # ------------------------------------------------------
    # Candidate-pool sizing
    #
    # Diversification needs a larger candidate set than the
    # final requested page.
    # ------------------------------------------------------

    if diversify:
        candidate_limit = max(
            500,
            (offset + limit) * 20,
        )

        candidate_limit = min(
            candidate_limit,
            5000,
        )

    else:
        candidate_limit = (
            offset + limit
        )

    sql = f"""
        {_base_select()}

        WHERE {
            ' AND '.join(
                clauses
            )
        }

        ORDER BY
            e.overall_score DESC,

            COALESCE(
                j.posted_at,
                j.last_seen_at
            ) DESC,

            j.id DESC

        LIMIT ?
    """

    params.append(
        candidate_limit
    )

    with canonical_conn() as conn:
        rows = conn.execute(
            _sql(sql),
            params,
        ).fetchall()

    # ------------------------------------------------------
    # Diversified browsing feed
    # ------------------------------------------------------

    if diversify:

        diversified = _diversify(
            rows,
            limit=(
                offset
                + limit
            ),
            max_per_employer=(
                max_per_employer
            ),
        )

        page = diversified[
            offset:
            offset + limit
        ]

    else:

        page = [
            dict(row)
            for row in rows[
                offset:
                offset + limit
            ]
        ]

    return {
        "items": page,

        "count": len(page),

        "offset": offset,
        "limit": limit,

        "diversified": diversify,

        "max_per_employer": (
            max_per_employer
            if diversify
            else None
        ),
    }


# ==========================================================
# Job detail
# ==========================================================


@router.get("/jobs/{job_id}")
def job_detail(
    job_id: int,
):
    with canonical_conn() as conn:

        row = conn.execute(
            _sql(f"""
            {_base_select()}

            WHERE j.id=?
              AND j.is_active=1

            LIMIT 1
            """),
            (
                job_id,
            ),
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Job not found",
            )

        sources = conn.execute(_sql("""
            SELECT
                s.provider,
                s.source_confidence,
                s.match_method,
                s.match_confidence,
                s.first_seen_at,
                s.last_seen_at,
                s.is_active,

                o.provider_job_id,
                o.source_url,
                o.apply_url

            FROM canonical_job_sources s

            JOIN job_observations o
              ON o.id=s.observation_id

            WHERE s.canonical_job_id=?

            ORDER BY
                s.is_active DESC,
                s.source_confidence DESC
        """), (
            job_id,
        )).fetchall()

    result = dict(row)

    result[
        "sources"
    ] = [
        dict(source)
        for source in sources
    ]

    return result


# ==========================================================
# Stats
# ==========================================================


@router.patch("/jobs/{job_id}/status")
def update_job_application_status(
    job_id: int,
    body: ApplicationStatusUpdate,
):
    try:
        row = update_canonical_application_status(
            job_id,
            body.status,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    if not row:
        raise HTTPException(
            status_code=404,
            detail="Canonical job not found",
        )

    return row


@router.get("/stats")
def stats():
    with canonical_conn() as conn:

        row = conn.execute(_sql("""
            SELECT
                COUNT(*) AS eligible_jobs,

                COUNT(
                    DISTINCT j.employer_identity_id
                ) AS employers,

                SUM(
                    CASE
                        WHEN e.work_arrangement='REMOTE'
                        THEN 1
                        ELSE 0
                    END
                ) AS remote,

                SUM(
                    CASE
                        WHEN e.work_arrangement='HYBRID'
                        THEN 1
                        ELSE 0
                    END
                ) AS hybrid,

                SUM(
                    CASE
                        WHEN e.work_arrangement='ONSITE'
                        THEN 1
                        ELSE 0
                    END
                ) AS onsite,

                SUM(
                    CASE
                        WHEN e.visa_language_status=
                             'EXPLICIT_SPONSORSHIP'
                        THEN 1
                        ELSE 0
                    END
                ) AS explicit_sponsorship,

                SUM(
                    CASE
                        WHEN e.visa_language_status=
                             'POSSIBLE_SPONSORSHIP'
                        THEN 1
                        ELSE 0
                    END
                ) AS possible_sponsorship,

                AVG(
                    e.overall_score
                ) AS average_score

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1
              AND e.is_eligible=1
        """)).fetchone()

    result = dict(row)

    if result[
        "average_score"
    ] is not None:
        result[
            "average_score"
        ] = round(
            result[
                "average_score"
            ],
            2,
        )

    return result


# ==========================================================
# Facets
# ==========================================================


@router.get("/facets")
def facets():
    with canonical_conn() as conn:

        role_families = conn.execute(_sql("""
            SELECT
                e.software_role_family AS value,
                COUNT(*) AS count

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1
              AND e.is_eligible=1

            GROUP BY
                e.software_role_family

            ORDER BY
                count DESC
        """)).fetchall()

        states = conn.execute(_sql("""
            SELECT
                e.state_code AS value,
                COUNT(*) AS count

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1
              AND e.is_eligible=1
              AND e.state_code IS NOT NULL

            GROUP BY
                e.state_code

            ORDER BY
                count DESC
        """)).fetchall()

        arrangements = conn.execute(_sql("""
            SELECT
                e.work_arrangement AS value,
                COUNT(*) AS count

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1
              AND e.is_eligible=1

            GROUP BY
                e.work_arrangement

            ORDER BY
                count DESC
        """)).fetchall()

        seniorities = conn.execute(_sql("""
            SELECT
                e.seniority_band AS value,
                COUNT(*) AS count

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1
              AND e.is_eligible=1

            GROUP BY
                e.seniority_band

            ORDER BY
                count DESC
        """)).fetchall()

        sponsor_strengths = conn.execute(_sql("""
            SELECT
                e.sponsor_history_strength AS value,
                COUNT(*) AS count

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1
              AND e.is_eligible=1

            GROUP BY
                e.sponsor_history_strength

            ORDER BY
                count DESC
        """)).fetchall()

        visa_statuses = conn.execute(_sql("""
            SELECT
                e.visa_language_status AS value,
                COUNT(*) AS count

            FROM canonical_jobs j

            JOIN canonical_job_enrichment e
              ON e.canonical_job_id=j.id

            WHERE j.is_active=1
              AND e.is_eligible=1

            GROUP BY
                e.visa_language_status

            ORDER BY
                count DESC
        """)).fetchall()

    def pack(rows):
        return [
            dict(row)
            for row in rows
        ]

    return {
        "role_families": pack(
            role_families
        ),

        "states": pack(
            states
        ),

        "work_arrangements": pack(
            arrangements
        ),

        "seniority": pack(
            seniorities
        ),

        "sponsor_strength": pack(
            sponsor_strengths
        ),

        "visa_status": pack(
            visa_statuses
        ),
    }
