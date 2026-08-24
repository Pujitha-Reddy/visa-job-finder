from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.database import get_connection
from app.postgres_repository import pg_conn


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

STATE_PATH = DATA_DIR / "v114_onboarding_state.json"

DEFAULT_BATCH = "AUTO_ONBOARDING"
DEFAULT_BATCH_LIMIT = 25

DISCOVERY_TIMEOUT = 900
VERIFY_TIMEOUT = 1800
GENERIC_PROMOTION_TIMEOUT = 900
ATS_PROMOTION_TIMEOUT = 180


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "V114 automatic employer/source onboarding pipeline."
        )
    )

    parser.add_argument(
        "--batch-name",
        default=None,
        help=(
            "Process one discovery batch only. "
            "Default processes every pending batch."
        ),
    )

    parser.add_argument(
        "--create-batch",
        action="store_true",
        help=(
            "Create/add sponsor candidates to the automatic "
            "onboarding batch before discovery."
        ),
    )

    parser.add_argument(
        "--new-batch-name",
        default=DEFAULT_BATCH,
    )

    parser.add_argument(
        "--batch-limit",
        type=int,
        default=DEFAULT_BATCH_LIMIT,
    )

    parser.add_argument(
        "--discovery-limit",
        type=int,
        default=5,
        help=(
            "Maximum number of new employers to run through "
            "careers discovery per batch."
        ),
    )

    parser.add_argument(
        "--verification-limit",
        type=int,
        default=5,
        help=(
            "Maximum number of unresolved source candidates "
            "to verify per batch."
        ),
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore the normal onboarding cooldown.",
    )

    parser.add_argument(
        "--min-interval-hours",
        type=float,
        default=24.0,
        help=(
            "Minimum production interval between full "
            "automatic onboarding attempts."
        ),
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
    )

    return parser.parse_args()


def utc_now():
    return datetime.now(timezone.utc)


def read_state():
    """
    Postgres is authoritative in production/cloud execution.

    Local JSON remains a development fallback only when no
    DATABASE_URL is configured.
    """

    if os.getenv("DATABASE_URL"):
        with pg_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT state_value
                FROM pipeline_runtime_state
                WHERE state_key='v114_onboarding'
            """)

            row = cur.fetchone()

        if not row:
            return {}

        value = row["state_value"]

        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return {}

        return dict(value or {})

    if not STATE_PATH.exists():
        return {}

    try:
        return json.loads(
            STATE_PATH.read_text()
        )
    except Exception:
        return {}


def write_state(payload):
    payload = dict(payload)
    payload["updated_at"] = utc_now().isoformat()

    if os.getenv("DATABASE_URL"):
        with pg_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
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
                """,
                (
                    json.dumps(payload),
                ),
            )

            conn.commit()

        return

    STATE_PATH.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def cooldown_active(hours):
    state = read_state()

    raw = state.get("last_completed_at")

    if not raw:
        return False, None

    try:
        previous = datetime.fromisoformat(
            raw.replace("Z", "+00:00")
        )

        if previous.tzinfo is None:
            previous = previous.replace(
                tzinfo=timezone.utc
            )

    except Exception:
        return False, None

    age_hours = (
        utc_now() - previous
    ).total_seconds() / 3600

    return age_hours < hours, age_hours


def run_command(
    label,
    command,
    *,
    timeout,
):
    print()
    print("=" * 110)
    print(label)
    print("=" * 110)

    print(
        "COMMAND:",
        " ".join(command),
    )

    started = time.perf_counter()

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    try:
        result = subprocess.run(
            command,
            cwd=BASE_DIR,
            env=env,
            check=False,
            timeout=timeout,
        )

    except subprocess.TimeoutExpired:
        duration = round(
            time.perf_counter()
            - started,
            2,
        )

        print(
            "[TIMEOUT]",
            label,
            "|",
            duration,
            "seconds",
        )

        return {
            "label": label,
            "status": "TIMEOUT",
            "returncode": 124,
            "duration": duration,
        }

    duration = round(
        time.perf_counter()
        - started,
        2,
    )

    status = (
        "SUCCESS"
        if result.returncode == 0
        else "FAILED"
    )

    print(
        status,
        "| exit=",
        result.returncode,
        "| duration=",
        duration,
    )

    return {
        "label": label,
        "status": status,
        "returncode": result.returncode,
        "duration": duration,
    }


def pending_batches(
    only_batch=None,
):
    with get_connection() as c:
        if only_batch:
            rows = c.execute(
                """
                SELECT DISTINCT batch_name
                FROM source_discovery_batches
                WHERE resolution_status='PENDING'
                  AND batch_name=?
                ORDER BY batch_name
                """,
                (only_batch,),
            ).fetchall()

        else:
            rows = c.execute(
                """
                SELECT DISTINCT batch_name
                FROM source_discovery_batches
                WHERE resolution_status='PENDING'
                ORDER BY batch_name
                """
            ).fetchall()

    return [
        row["batch_name"]
        for row in rows
    ]


def batch_state(batch):
    with get_connection() as c:
        row = c.execute(
            """
            SELECT
                COUNT(*) AS total,

                SUM(
                    CASE
                        WHEN resolution_status='PENDING'
                        THEN 1 ELSE 0
                    END
                ) AS pending,

                SUM(
                    CASE
                        WHEN verification_status='VERIFIED'
                         AND resolution_status!='PROMOTED'
                        THEN 1 ELSE 0
                    END
                ) AS verified_ready,

                SUM(
                    CASE
                        WHEN resolution_status='PROMOTED'
                        THEN 1 ELSE 0
                    END
                ) AS promoted
            FROM source_discovery_batches
            WHERE batch_name=?
            """,
            (batch,),
        ).fetchone()

    return dict(row)


def verified_ready(batch):
    with get_connection() as c:
        return [
            dict(row)
            for row in c.execute(
                """
                SELECT
                    id,
                    batch_name,
                    display_name,
                    discovered_ats,
                    discovered_careers_url,
                    discovered_token,
                    source_discovery_score
                FROM source_discovery_batches
                WHERE batch_name=?
                  AND verification_status='VERIFIED'
                  AND resolution_status!='PROMOTED'
                ORDER BY
                    source_discovery_score DESC,
                    id
                """,
                (batch,),
            ).fetchall()
        ]


def global_summary():
    with get_connection() as c:
        discovery = dict(
            c.execute(
                """
                SELECT
                    COUNT(*) AS total,

                    SUM(
                        CASE
                            WHEN resolution_status='PENDING'
                            THEN 1 ELSE 0
                        END
                    ) AS pending,

                    SUM(
                        CASE
                            WHEN resolution_status='PROMOTED'
                            THEN 1 ELSE 0
                        END
                    ) AS promoted,

                    SUM(
                        CASE
                            WHEN verification_status='VERIFIED'
                            THEN 1 ELSE 0
                        END
                    ) AS verified
                FROM source_discovery_batches
                """
            ).fetchone()
        )

        operational = dict(
            c.execute(
                """
                SELECT
                    COUNT(*) AS total_sources,

                    SUM(
                        CASE
                            WHEN enabled=1
                            THEN 1 ELSE 0
                        END
                    ) AS enabled_sources,

                    SUM(
                        CASE
                            WHEN source_verified=1
                            THEN 1 ELSE 0
                        END
                    ) AS verified_sources
                FROM employer_sources
                """
            ).fetchone()
        )

    return {
        "discovery": discovery,
        "operational": operational,
    }


def main():
    args = parse_args()

    print("=" * 110)
    print("V114 EMPLOYER AUTO-ONBOARDING")
    print("=" * 110)

    print(
        "PYTHON:",
        sys.executable,
    )

    print(
        "BASE:",
        BASE_DIR,
    )

    if (
        not args.force
        and not args.dry_run
    ):
        active, age = cooldown_active(
            args.min_interval_hours
        )

        if active:
            print(
                "[SKIP] onboarding cooldown active"
            )

            print(
                "hours since last completion:",
                round(age, 2),
            )

            print(
                "minimum interval:",
                args.min_interval_hours,
            )

            return

    before = global_summary()

    print()
    print("BEFORE")
    print(before)

    if args.dry_run:
        batches = pending_batches(
            args.batch_name
        )

        print()
        print("DRY RUN")
        print("PENDING BATCHES:", batches)

        for batch in batches:
            print(
                batch,
                batch_state(batch),
            )

        print()
        print(
            "No database or registry changes "
            "were made by V114 dry-run."
        )

        return

    results = []

    # ======================================================
    # Stage 0: add new sponsor candidates
    # ======================================================

    if args.create_batch:
        results.append(
            run_command(
                "CREATE / EXTEND AUTO-ONBOARDING BATCH",
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "app.create_source_discovery_batch",
                    "--batch-name",
                    args.new_batch_name,
                    "--limit",
                    str(args.batch_limit),
                ],
                timeout=120,
            )
        )

    batches = pending_batches(
        args.batch_name
    )

    print()
    print(
        "PENDING BATCHES:",
        batches,
    )

    # ======================================================
    # Process every currently pending batch
    # ======================================================

    for batch in batches:

        print()
        print("#" * 110)
        print(
            "BATCH:",
            batch,
        )
        print(
            "START STATE:",
            batch_state(batch),
        )
        print("#" * 110)

        # --------------------------------------------------
        # 1. Discover official careers/job surface
        # --------------------------------------------------

        results.append(
            run_command(
                f"{batch} | CAREERS DISCOVERY",
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "app.discover_employer_careers",
                    "--batch-name",
                    batch,
                    "--limit",
                    str(max(1, int(args.discovery_limit))),
                    "--only-undiscovered",
                ],
                timeout=DISCOVERY_TIMEOUT,
            )
        )

        # --------------------------------------------------
        # 2. Discover ATS and prove collector can fetch jobs
        # --------------------------------------------------

        results.append(
            run_command(
                f"{batch} | SOURCE VERIFICATION",
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "app.verify_auto_discovered_sources",
                    "--batch-name",
                    batch,
                    "--limit",
                    str(max(1, int(args.verification_limit))),
                ],
                timeout=VERIFY_TIMEOUT,
            )
        )

        # --------------------------------------------------
        # 3. Generic source promotion
        #
        # auto_promote_sources itself enforces:
        # - explicit GENERIC routing
        # - MIN_JOBS
        # - collection score threshold
        # --------------------------------------------------

        results.append(
            run_command(
                f"{batch} | GENERIC AUTO-PROMOTION",
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "app.auto_promote_sources",
                    "--batch-name",
                    batch,
                ],
                timeout=GENERIC_PROMOTION_TIMEOUT,
            )
        )

        # --------------------------------------------------
        # 4. Promote VERIFIED ATS records
        # --------------------------------------------------

        ready = verified_ready(
            batch
        )

        print()
        print(
            "VERIFIED ATS RECORDS READY:",
            len(ready),
        )

        for row in ready:
            results.append(
                run_command(
                    (
                        f"{batch} | PROMOTE | "
                        f"{row['display_name']}"
                    ),
                    [
                        sys.executable,
                        "-u",
                        "-m",
                        "app.promote_discovered_source",
                        "--batch",
                        batch,
                        "--employer",
                        row["display_name"],
                    ],
                    timeout=ATS_PROMOTION_TIMEOUT,
                )
            )

        print()
        print(
            "END STATE:",
            batch_state(batch),
        )

    after = global_summary()

    failures = [
        item
        for item in results
        if item["status"] != "SUCCESS"
    ]

    print()
    print("=" * 110)
    print("V114 AUTO-ONBOARDING SUMMARY")
    print("=" * 110)

    print(
        "BATCHES PROCESSED:",
        len(batches),
    )

    print(
        "COMMANDS:",
        len(results),
    )

    print(
        "FAILURES:",
        len(failures),
    )

    print()
    print("BEFORE:", before)
    print("AFTER: ", after)

    completion_status = (
        "PARTIAL"
        if failures
        else "SUCCESS"
    )

    if failures:
        print()
        print("FAILED / TIMED OUT STAGES")

        for failure in failures:
            print(failure)

    write_state({
        "last_completed_at":
            utc_now().isoformat(),
        "batches_processed":
            batches,
        "summary":
            after,
        "status":
            completion_status,
        "failures":
            failures,
    })

    if failures:
        print()
        print(
            "[WARNING] V114 employer auto-onboarding "
            "completed with isolated stage failures."
        )
        print(
            "[WARNING] Successful batches/stages were "
            "preserved; pending work remains eligible "
            "for a future onboarding cycle."
        )
    else:
        print()
        print(
            "[SUCCESS] V114 employer "
            "auto-onboarding completed."
        )



if __name__ == "__main__":
    main()
