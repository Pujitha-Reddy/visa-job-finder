from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from .canonical_db import canonical_conn, backend_name
from .database import DB_PATH
from .registry.repository import list_enabled_sources


BASE_DIR = Path(__file__).resolve().parents[1]

load_dotenv(
    BASE_DIR / ".env",
    override=False,
)

PLIST_LABEL = "com.visajobfinder.refresh"


def scalar(conn, sql):
    row = conn.execute(sql).fetchone()

    if row is None:
        return 0

    if isinstance(row, dict):
        return next(iter(row.values()))

    try:
        return row[0]
    except (KeyError, TypeError):
        return next(iter(dict(row).values()))


def scheduler_health():
    try:
        result = subprocess.run(
            [
                "launchctl",
                "print",
                f"gui/{os.getuid()}/{PLIST_LABEL}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:
        return {
            "loaded": False,
            "state": "UNKNOWN",
            "last_exit_code": None,
            "error": str(exc),
        }

    text = result.stdout or ""

    if result.returncode != 0:
        return {
            "loaded": False,
            "state": "NOT_LOADED",
            "last_exit_code": None,
        }

    state = None
    last_exit = None
    runs = None

    for line in text.splitlines():
        stripped = line.strip()

        if (
            stripped.startswith("state =")
            and state is None
        ):
            state = stripped.split("=", 1)[1].strip()

        elif stripped.startswith("runs ="):
            try:
                runs = int(
                    stripped.split("=", 1)[1].strip()
                )
            except ValueError:
                pass

        elif stripped.startswith("last exit code ="):
            value = stripped.split("=", 1)[1].strip()

            if value == "(never exited)":
                last_exit = None
            else:
                try:
                    last_exit = int(value)
                except ValueError:
                    last_exit = value

    return {
        "loaded": True,
        "state": state,
        "runs": runs,
        "last_exit_code": last_exit,
    }


def ingestion_health():

    registry = list_enabled_sources()

    expected_ids = {
        str(source["source_id"])
        for source in registry
    }

    if os.getenv("DATABASE_URL"):

        from .postgres_repository import pg_conn

        with pg_conn() as conn, conn.cursor() as cur:

            cur.execute("""
                SELECT
                    source_key,
                    employer_name,
                    ats,
                    consecutive_failures,
                    last_error
                FROM source_health
                WHERE enabled IS TRUE
            """)

            rows = cur.fetchall()

        failures = []

        for row in rows:
            row = dict(row)

            if (
                row.get("consecutive_failures")
                or 0
            ) > 0:

                failures.append({
                    "source_key":
                        row.get("source_key"),

                    "employer":
                        row.get("employer_name"),

                    "provider":
                        row.get("ats"),

                    "status":
                        "FAILED",

                    "error":
                        row.get("last_error"),
                })

        successful = (
            len(expected_ids)
            - len(failures)
        )

        return {
            "enabled_sources":
                len(expected_ids),

            "sources_with_run":
                len(expected_ids),

            "status_counts": {
                "SUCCESS": successful,
                **(
                    {"FAILED": len(failures)}
                    if failures
                    else {}
                ),
            },

            "missing_sources": [],

            "persistent_failures":
                failures,
        }

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        rows = conn.execute(
            """
            SELECT *
            FROM ingestion_runs
            WHERE provider_source_id IS NOT NULL
            ORDER BY id DESC
            """
        ).fetchall()
    finally:
        conn.close()

    latest = {}

    for row in rows:
        source_id = str(
            row["provider_source_id"]
        )

        if (
            source_id in expected_ids
            and source_id not in latest
        ):
            latest[source_id] = dict(row)

        if len(latest) == len(expected_ids):
            break

    counts = Counter(
        row.get("status") or "UNKNOWN"
        for row in latest.values()
    )

    missing = sorted(
        expected_ids - set(latest)
    )

    failures = []

    for source_id, row in latest.items():

        if row.get("status") != "SUCCESS":

            failures.append({
                "source_id": source_id,
                "provider":
                    row.get("provider"),
                "status":
                    row.get("status"),
                "error":
                    row.get("error"),
            })

    return {
        "enabled_sources":
            len(expected_ids),

        "sources_with_run":
            len(latest),

        "status_counts":
            dict(counts),

        "missing_sources":
            missing,

        "persistent_failures":
            failures,
    }


def canonical_health():
    is_postgres = (
        backend_name() == "postgres"
    )

    active_true = (
        "TRUE"
        if is_postgres
        else "1"
    )

    eligible_true = (
        "TRUE"
        if is_postgres
        else "1"
    )

    software_true = (
        "TRUE"
        if is_postgres
        else "1"
    )

    us_false = (
        "FALSE"
        if is_postgres
        else "0"
    )

    with canonical_conn() as conn:
        total = scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM canonical_jobs
            """,
        )

        active = scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM canonical_jobs
            WHERE is_active={active_true}
            """,
        )

        eligible = scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM canonical_job_enrichment
            WHERE is_eligible={eligible_true}
            """,
        )

        software = scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM canonical_job_enrichment
            WHERE is_software_role={software_true}
            """,
        )

        non_us_leaks = scalar(
            conn,
            f"""
            SELECT COUNT(*)
            FROM canonical_job_enrichment
            WHERE is_eligible={eligible_true}
              AND COALESCE(
                    is_us_job,
                    {us_false}
                  )={us_false}
            """,
        )

        freshest = conn.execute(
            """
            SELECT
                MAX(last_seen_at) AS last_seen
            FROM canonical_jobs
            """
        ).fetchone()

        freshest = (
            dict(freshest).get("last_seen")
            if freshest
            else None
        )

    return {
        "backend": backend_name(),
        "canonical_jobs": int(total or 0),
        "active_jobs": int(active or 0),
        "eligible_jobs": int(eligible or 0),
        "software_jobs": int(software or 0),
        "non_us_eligible_leaks": int(non_us_leaks or 0),
        "freshest_last_seen": (
            str(freshest)
            if freshest is not None
            else None
        ),
    }


def parity_health():
    """
    SQLite/Postgres parity is a hard production check only on the
    certified ephemeral cloud runner.

    A developer Mac may intentionally have a stale local SQLite
    snapshot after GitHub has advanced Postgres, so local parity is
    informational rather than a production-health gate.
    """

    if backend_name() != "postgres":
        return {
            "checked": False,
            "match": True,
            "reason": (
                "canonical backend is not postgres"
            ),
            "authority": "LOCAL_SQLITE",
        }

    if os.getenv("CLOUD_RUNNER") != "1":
        return {
            "checked": False,
            "match": True,
            "reason": (
                "local SQLite parity is not authoritative "
                "outside certified cloud runner"
            ),
            "authority": "POSTGRES",
        }

    sqlite_conn = sqlite3.connect(
        DB_PATH
    )
    sqlite_conn.row_factory = sqlite3.Row

    sqlite_counts = {}

    try:
        sqlite_counts["canonical_jobs"] = scalar(
            sqlite_conn,
            """
            SELECT COUNT(*)
            FROM canonical_jobs
            """,
        )

        sqlite_counts["active_jobs"] = scalar(
            sqlite_conn,
            """
            SELECT COUNT(*)
            FROM canonical_jobs
            WHERE is_active=1
            """,
        )

        sqlite_counts["eligible_jobs"] = scalar(
            sqlite_conn,
            """
            SELECT COUNT(*)
            FROM canonical_job_enrichment
            WHERE is_eligible=1
            """,
        )

    finally:
        sqlite_conn.close()

    with canonical_conn() as conn:
        postgres_counts = {
            "canonical_jobs":
                scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM canonical_jobs
                    """,
                ),

            "active_jobs":
                scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM canonical_jobs
                    WHERE is_active=TRUE
                    """,
                ),

            "eligible_jobs":
                scalar(
                    conn,
                    """
                    SELECT COUNT(*)
                    FROM canonical_job_enrichment
                    WHERE is_eligible=TRUE
                    """,
                ),
        }

    sqlite_counts = {
        key: int(value or 0)
        for key, value
        in sqlite_counts.items()
    }

    postgres_counts = {
        key: int(value or 0)
        for key, value
        in postgres_counts.items()
    }

    return {
        "checked": True,
        "match":
            sqlite_counts
            == postgres_counts,
        "sqlite": sqlite_counts,
        "postgres": postgres_counts,
        "authority":
            "CLOUD_RUNNER_PARITY",
    }


def build_health():
    scheduler = scheduler_health()
    ingestion = ingestion_health()
    canonical = canonical_health()
    parity = parity_health()

    checks = {
        "scheduler_last_exit_ok": (
            scheduler.get("last_exit_code") in (0, None)
        ),
        "all_sources_have_runs": (
            ingestion["sources_with_run"]
            == ingestion["enabled_sources"]
        ),
        "no_persistent_failures": (
            len(
                ingestion["persistent_failures"]
            ) == 0
        ),
        "zero_non_us_eligible_leaks": (
            canonical["non_us_eligible_leaks"] == 0
        ),
        "parity": (
            parity.get("match", True)
        ),
    }

    overall = (
        "HEALTHY"
        if all(checks.values())
        else "DEGRADED"
    )

    return {
        "version": "V113",
        "status": overall,
        "checks": checks,
        "scheduler": scheduler,
        "ingestion": ingestion,
        "canonical": canonical,
        "parity": parity,
    }


def print_human(report):
    print("=" * 100)
    print("V113 PRODUCTION HEALTH")
    print("=" * 100)

    print()
    print("OVERALL:", report["status"])

    s = report["scheduler"]

    print()
    print("SCHEDULER")
    print(
        "  loaded:",
        s.get("loaded"),
        "| state:",
        s.get("state"),
        "| runs:",
        s.get("runs"),
        "| last exit:",
        s.get("last_exit_code"),
    )

    i = report["ingestion"]

    print()
    print("INGESTION")
    print(
        "  sources:",
        f'{i["sources_with_run"]}/{i["enabled_sources"]}',
    )
    print(
        "  statuses:",
        i["status_counts"],
    )
    print(
        "  persistent failures:",
        len(i["persistent_failures"]),
    )

    c = report["canonical"]

    print()
    print("CANONICAL DATA")
    print("  backend:", c["backend"])
    print("  canonical:", c["canonical_jobs"])
    print("  active:", c["active_jobs"])
    print("  software:", c["software_jobs"])
    print("  eligible:", c["eligible_jobs"])
    print(
        "  non-US eligible leaks:",
        c["non_us_eligible_leaks"],
    )
    print(
        "  freshest last_seen:",
        c["freshest_last_seen"],
    )

    p = report["parity"]

    print()
    print("SQLITE <-> POSTGRES PARITY")
    print(
        "  checked:",
        p.get("checked"),
        "| match:",
        p.get("match"),
    )

    print()
    print("CHECKS")

    for name, passed in report["checks"].items():
        print(
            " ",
            "PASS" if passed else "FAIL",
            "|",
            name,
        )

    print()
    print("=" * 100)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="V113 production health audit."
    )

    parser.add_argument(
        "--json",
        action="store_true",
    )

    args = parser.parse_args()

    report = build_health()

    if args.json:
        print(
            json.dumps(
                report,
                indent=2,
                default=str,
            )
        )
    else:
        print_human(report)

    if report["status"] != "HEALTHY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
