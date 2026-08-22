from __future__ import annotations

import json
from pathlib import Path

from app.database import get_connection
from app.postgres_repository import pg_conn


BASE_DIR = Path(__file__).resolve().parents[1]

ONBOARDING_STATE_PATH = (
    BASE_DIR
    / "data"
    / "v114_onboarding_state.json"
)


def dict_rows(rows):
    return [
        dict(row)
        for row in rows
    ]


def create_cloud_tables(cur):

    cur.execute("""
        CREATE TABLE IF NOT EXISTS combined_sponsor_universe (
            parent_key TEXT PRIMARY KEY,

            display_name TEXT NOT NULL,

            dol_present INTEGER NOT NULL DEFAULT 0,
            uscis_present INTEGER NOT NULL DEFAULT 0,

            dol_recent_filings INTEGER NOT NULL DEFAULT 0,
            dol_total_filings INTEGER NOT NULL DEFAULT 0,
            dol_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

            uscis_active_years INTEGER NOT NULL DEFAULT 0,

            uscis_2025_approvals INTEGER NOT NULL DEFAULT 0,
            uscis_2026_approvals INTEGER NOT NULL DEFAULT 0,

            uscis_total_approvals INTEGER NOT NULL DEFAULT 0,
            uscis_total_denials INTEGER NOT NULL DEFAULT 0,

            uscis_strength TEXT NOT NULL DEFAULT 'UNKNOWN',

            dol_score_component DOUBLE PRECISION NOT NULL DEFAULT 0,
            uscis_volume_component DOUBLE PRECISION NOT NULL DEFAULT 0,
            consistency_component DOUBLE PRECISION NOT NULL DEFAULT 0,
            approval_component DOUBLE PRECISION NOT NULL DEFAULT 0,
            current_activity_component DOUBLE PRECISION NOT NULL DEFAULT 0,

            combined_sponsor_score DOUBLE PRECISION NOT NULL DEFAULT 0,
            combined_priority_band TEXT NOT NULL DEFAULT 'LOW',

            already_in_registry INTEGER NOT NULL DEFAULT 0,
            matched_employer_id BIGINT,

            source_resolution_status TEXT NOT NULL DEFAULT 'UNRESOLVED',

            updated_at TEXT,

            employer_relevance_band TEXT,
            employer_relevance_score INTEGER NOT NULL DEFAULT 0,
            employer_relevance_reason TEXT,

            source_discovery_score DOUBLE PRECISION NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS source_discovery_batches (
            id BIGINT PRIMARY KEY,

            batch_name TEXT NOT NULL,

            parent_key TEXT NOT NULL,
            display_name TEXT NOT NULL,

            combined_sponsor_score DOUBLE PRECISION NOT NULL,
            employer_relevance_band TEXT,
            source_discovery_score DOUBLE PRECISION NOT NULL,

            dol_recent_filings INTEGER NOT NULL DEFAULT 0,
            uscis_2025_approvals INTEGER NOT NULL DEFAULT 0,
            uscis_2026_approvals INTEGER NOT NULL DEFAULT 0,

            resolution_status TEXT NOT NULL DEFAULT 'PENDING',

            discovered_careers_url TEXT,
            discovered_ats TEXT,
            discovered_token TEXT,

            verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',

            notes TEXT,

            created_at TEXT,
            updated_at TEXT,

            careers_discovery_status TEXT,
            careers_candidate_url TEXT,
            careers_discovery_score DOUBLE PRECISION,

            UNIQUE(batch_name, parent_key)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runtime_state (
            state_key TEXT PRIMARY KEY,
            state_value JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def preflight_registry(sqlite, cur):
    """
    Employer IDs are durable and referenced elsewhere.

    Require every shared employer ID to map to the same canonical
    employer before replacing the source registry.

    employer_sources IDs are safe to replace because Postgres has
    no external FK references to employer_sources.id.
    """

    sqlite_employers = {
        row["id"]: dict(row)
        for row in sqlite.execute("""
            SELECT *
            FROM employers
        """).fetchall()
    }

    cur.execute("""
        SELECT *
        FROM employers
    """)

    for row in cur.fetchall():
        pg = dict(row)

        local = sqlite_employers.get(
            pg["id"]
        )

        if not local:
            continue

        if (
            local["canonical_name"]
            != pg["canonical_name"]
        ):
            raise RuntimeError(
                "EMPLOYER ID CONFLICT: "
                f"id={pg['id']} "
                f"sqlite={local['canonical_name']!r} "
                f"postgres={pg['canonical_name']!r}"
            )


def sync_employers(sqlite, cur):
    rows = dict_rows(
        sqlite.execute("""
            SELECT
                id,
                canonical_name,
                display_name,
                source_type,
                website,
                careers_url,
                enabled,
                created_at,
                updated_at
            FROM employers
            ORDER BY id
        """).fetchall()
    )

    for row in rows:
        cur.execute("""
            INSERT INTO employers (
                id,
                canonical_name,
                display_name,
                source_type,
                website,
                careers_url,
                enabled,
                created_at,
                updated_at
            )
            VALUES (
                %(id)s,
                %(canonical_name)s,
                %(display_name)s,
                %(source_type)s,
                %(website)s,
                %(careers_url)s,
                %(enabled)s,
                %(created_at)s,
                %(updated_at)s
            )

            ON CONFLICT (id)
            DO UPDATE SET
                canonical_name=EXCLUDED.canonical_name,
                display_name=EXCLUDED.display_name,
                source_type=EXCLUDED.source_type,
                website=EXCLUDED.website,
                careers_url=EXCLUDED.careers_url,
                enabled=EXCLUDED.enabled,
                created_at=EXCLUDED.created_at,
                updated_at=EXCLUDED.updated_at
        """, row)

    return len(rows)


def sync_sources(sqlite, cur):
    """
    Replace the Postgres source registry with the certified
    authoritative SQLite registry.

    This intentionally fixes old semantic ID drift such as:
      53  CUSTOM -> WORKDAY
      105 CUSTOM -> WORKDAY

    No production table has an FK to employer_sources.id.
    """

    rows = dict_rows(
        sqlite.execute("""
            SELECT
                id,
                employer_id,
                ats,
                token,
                careers_url,
                enabled,
                last_checked_at,
                last_success_at,
                active_jobs,
                source_verified,
                notes
            FROM employer_sources
            ORDER BY id
        """).fetchall()
    )

    cur.execute("""
        DELETE FROM employer_sources
    """)

    for row in rows:
        cur.execute("""
            INSERT INTO employer_sources (
                id,
                employer_id,
                ats,
                token,
                careers_url,
                enabled,
                last_checked_at,
                last_success_at,
                active_jobs,
                source_verified,
                notes
            )
            VALUES (
                %(id)s,
                %(employer_id)s,
                %(ats)s,
                %(token)s,
                %(careers_url)s,
                %(enabled)s,
                %(last_checked_at)s,
                %(last_success_at)s,
                %(active_jobs)s,
                %(source_verified)s,
                %(notes)s
            )
        """, row)

    return len(rows)


def sync_combined_sponsors(sqlite, cur):
    rows = dict_rows(
        sqlite.execute("""
            SELECT *
            FROM combined_sponsor_universe
            ORDER BY parent_key
        """).fetchall()
    )

    sql = """
        INSERT INTO combined_sponsor_universe (
            parent_key,
            display_name,
            dol_present,
            uscis_present,
            dol_recent_filings,
            dol_total_filings,
            dol_strength,
            uscis_active_years,
            uscis_2025_approvals,
            uscis_2026_approvals,
            uscis_total_approvals,
            uscis_total_denials,
            uscis_strength,
            dol_score_component,
            uscis_volume_component,
            consistency_component,
            approval_component,
            current_activity_component,
            combined_sponsor_score,
            combined_priority_band,
            already_in_registry,
            matched_employer_id,
            source_resolution_status,
            updated_at,
            employer_relevance_band,
            employer_relevance_score,
            employer_relevance_reason,
            source_discovery_score
        )
        VALUES (
            %(parent_key)s,
            %(display_name)s,
            %(dol_present)s,
            %(uscis_present)s,
            %(dol_recent_filings)s,
            %(dol_total_filings)s,
            %(dol_strength)s,
            %(uscis_active_years)s,
            %(uscis_2025_approvals)s,
            %(uscis_2026_approvals)s,
            %(uscis_total_approvals)s,
            %(uscis_total_denials)s,
            %(uscis_strength)s,
            %(dol_score_component)s,
            %(uscis_volume_component)s,
            %(consistency_component)s,
            %(approval_component)s,
            %(current_activity_component)s,
            %(combined_sponsor_score)s,
            %(combined_priority_band)s,
            %(already_in_registry)s,
            %(matched_employer_id)s,
            %(source_resolution_status)s,
            %(updated_at)s,
            %(employer_relevance_band)s,
            %(employer_relevance_score)s,
            %(employer_relevance_reason)s,
            %(source_discovery_score)s
        )

        ON CONFLICT (parent_key)
        DO UPDATE SET
            display_name=EXCLUDED.display_name,
            dol_present=EXCLUDED.dol_present,
            uscis_present=EXCLUDED.uscis_present,
            dol_recent_filings=EXCLUDED.dol_recent_filings,
            dol_total_filings=EXCLUDED.dol_total_filings,
            dol_strength=EXCLUDED.dol_strength,
            uscis_active_years=EXCLUDED.uscis_active_years,
            uscis_2025_approvals=EXCLUDED.uscis_2025_approvals,
            uscis_2026_approvals=EXCLUDED.uscis_2026_approvals,
            uscis_total_approvals=EXCLUDED.uscis_total_approvals,
            uscis_total_denials=EXCLUDED.uscis_total_denials,
            uscis_strength=EXCLUDED.uscis_strength,
            dol_score_component=EXCLUDED.dol_score_component,
            uscis_volume_component=EXCLUDED.uscis_volume_component,
            consistency_component=EXCLUDED.consistency_component,
            approval_component=EXCLUDED.approval_component,
            current_activity_component=EXCLUDED.current_activity_component,
            combined_sponsor_score=EXCLUDED.combined_sponsor_score,
            combined_priority_band=EXCLUDED.combined_priority_band,
            already_in_registry=EXCLUDED.already_in_registry,
            matched_employer_id=EXCLUDED.matched_employer_id,
            source_resolution_status=EXCLUDED.source_resolution_status,
            updated_at=EXCLUDED.updated_at,
            employer_relevance_band=EXCLUDED.employer_relevance_band,
            employer_relevance_score=EXCLUDED.employer_relevance_score,
            employer_relevance_reason=EXCLUDED.employer_relevance_reason,
            source_discovery_score=EXCLUDED.source_discovery_score
    """

    # Avoid one 134k-row transaction command payload.
    for index in range(
        0,
        len(rows),
        2000,
    ):
        chunk = rows[
            index:
            index + 2000
        ]

        cur.executemany(
            sql,
            chunk,
        )

        print(
            "  combined_sponsor_universe:",
            min(
                index + len(chunk),
                len(rows),
            ),
            "/",
            len(rows),
        )

    return len(rows)


def sync_discovery(sqlite, cur):
    rows = dict_rows(
        sqlite.execute("""
            SELECT *
            FROM source_discovery_batches
            ORDER BY id
        """).fetchall()
    )

    for row in rows:
        cur.execute("""
            INSERT INTO source_discovery_batches (
                id,
                batch_name,
                parent_key,
                display_name,
                combined_sponsor_score,
                employer_relevance_band,
                source_discovery_score,
                dol_recent_filings,
                uscis_2025_approvals,
                uscis_2026_approvals,
                resolution_status,
                discovered_careers_url,
                discovered_ats,
                discovered_token,
                verification_status,
                notes,
                created_at,
                updated_at,
                careers_discovery_status,
                careers_candidate_url,
                careers_discovery_score
            )
            VALUES (
                %(id)s,
                %(batch_name)s,
                %(parent_key)s,
                %(display_name)s,
                %(combined_sponsor_score)s,
                %(employer_relevance_band)s,
                %(source_discovery_score)s,
                %(dol_recent_filings)s,
                %(uscis_2025_approvals)s,
                %(uscis_2026_approvals)s,
                %(resolution_status)s,
                %(discovered_careers_url)s,
                %(discovered_ats)s,
                %(discovered_token)s,
                %(verification_status)s,
                %(notes)s,
                %(created_at)s,
                %(updated_at)s,
                %(careers_discovery_status)s,
                %(careers_candidate_url)s,
                %(careers_discovery_score)s
            )

            ON CONFLICT (id)
            DO UPDATE SET
                batch_name=EXCLUDED.batch_name,
                parent_key=EXCLUDED.parent_key,
                display_name=EXCLUDED.display_name,
                combined_sponsor_score=EXCLUDED.combined_sponsor_score,
                employer_relevance_band=EXCLUDED.employer_relevance_band,
                source_discovery_score=EXCLUDED.source_discovery_score,
                dol_recent_filings=EXCLUDED.dol_recent_filings,
                uscis_2025_approvals=EXCLUDED.uscis_2025_approvals,
                uscis_2026_approvals=EXCLUDED.uscis_2026_approvals,
                resolution_status=EXCLUDED.resolution_status,
                discovered_careers_url=EXCLUDED.discovered_careers_url,
                discovered_ats=EXCLUDED.discovered_ats,
                discovered_token=EXCLUDED.discovered_token,
                verification_status=EXCLUDED.verification_status,
                notes=EXCLUDED.notes,
                created_at=EXCLUDED.created_at,
                updated_at=EXCLUDED.updated_at,
                careers_discovery_status=EXCLUDED.careers_discovery_status,
                careers_candidate_url=EXCLUDED.careers_candidate_url,
                careers_discovery_score=EXCLUDED.careers_discovery_score
        """, row)

    return len(rows)


def sync_onboarding_state(cur):
    state = {}

    if ONBOARDING_STATE_PATH.exists():
        try:
            state = json.loads(
                ONBOARDING_STATE_PATH.read_text()
            )
        except Exception:
            state = {}

    cur.execute("""
        INSERT INTO pipeline_runtime_state (
            state_key,
            state_value,
            updated_at
        )
        VALUES (
            'v114_onboarding',
            %s::jsonb,
            NOW()
        )

        ON CONFLICT (state_key)
        DO UPDATE SET
            state_value=EXCLUDED.state_value,
            updated_at=NOW()
    """, (
        json.dumps(state),
    ))

    return state


def main():
    print("=" * 110)
    print("V119.7B SQLITE -> POSTGRES DURABLE CLOUD STATE")
    print("=" * 110)

    with get_connection() as sqlite:
        with pg_conn() as pg, pg.cursor() as cur:

            create_cloud_tables(
                cur
            )

            preflight_registry(
                sqlite,
                cur,
            )

            print()
            print("SYNC: employers")
            employers = sync_employers(
                sqlite,
                cur,
            )
            print(" ", employers)

            print()
            print("SYNC: employer_sources")
            sources = sync_sources(
                sqlite,
                cur,
            )
            print(" ", sources)

            print()
            print("SYNC: combined_sponsor_universe")
            sponsors = sync_combined_sponsors(
                sqlite,
                cur,
            )

            print()
            print("SYNC: source_discovery_batches")
            discovery = sync_discovery(
                sqlite,
                cur,
            )
            print(" ", discovery)

            print()
            print("SYNC: v114 onboarding state")
            state = sync_onboarding_state(
                cur
            )
            print(" ", state)

            pg.commit()

    print()
    print("=" * 110)
    print("V119.7B MIGRATION COMPLETE")
    print("=" * 110)


if __name__ == "__main__":
    main()
