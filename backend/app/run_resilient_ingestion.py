from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass

from app.database import get_connection
from app.registry.repository import (
    init_registry,
    list_enabled_sources,
)


DEFAULT_BACKOFFS = (
    5,
    15,
    45,
)

DEFAULT_SOURCE_TIMEOUT_SECONDS = 900
@dataclass
class Failure:
    source_id: int
    employer_name: str
    provider: str | None
    status: str
    error: str | None
    run_id: int


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run universal ingestion and retry only "
            "sources that fail during this ingestion pass."
        )
    )

    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        choices=(0, 1, 2, 3),
    )

    parser.add_argument(
        "--no-backoff",
        action="store_true",
        help=(
            "Retry immediately. Useful for local testing."
        ),
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Return non-zero if sources remain failed after "
            "all retries. Normal production mode continues."
        ),
    )

    parser.add_argument(
        "--source-timeout",
        type=int,
        default=DEFAULT_SOURCE_TIMEOUT_SECONDS,
        help=(
            "Maximum runtime in seconds for one "
            "source ingestion subprocess."
        ),
    )

    return parser.parse_args()


def max_run_id():
    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                COALESCE(
                    MAX(id),
                    0
                ) AS max_id
            FROM ingestion_runs
        """).fetchone()

    return int(
        row["max_id"]
    )


def source_map():
    init_registry()

    return {
        int(source["source_id"]): source
        for source in list_enabled_sources()
    }


def run_command(
    command,
    *,
    timeout_seconds=None,
):
    print()

    print(
        "COMMAND:",
        " ".join(command),
        flush=True,
    )

    started = time.perf_counter()

    try:
        result = subprocess.run(
            command,
            check=False,
            timeout=timeout_seconds,
        )

        returncode = result.returncode

    except subprocess.TimeoutExpired:
        duration = round(
            time.perf_counter()
            - started,
            2,
        )

        print(
            "[PROCESS TIMEOUT]",
            "| timeout=",
            timeout_seconds,
            "| duration=",
            duration,
            "seconds",
            flush=True,
        )

        return 124

    duration = round(
        time.perf_counter()
        - started,
        2,
    )

    print(
        "EXIT:",
        returncode,
        "| DURATION:",
        duration,
        "seconds",
        flush=True,
    )

    return returncode

def record_process_failure(
    source_id,
    provider,
    error,
):
    source_key = str(source_id)

    with get_connection() as conn:
        row = conn.execute("""
            SELECT
                id,
                status
            FROM ingestion_runs
            WHERE provider_source_id=?
            ORDER BY id DESC
            LIMIT 1
        """, (
            source_key,
        )).fetchone()

        if row and row["status"] == "RUNNING":
            conn.execute("""
                UPDATE ingestion_runs
                SET
                    status='FAILED',
                    finished_at=CURRENT_TIMESTAMP,
                    error=?
                WHERE id=?
                  AND status='RUNNING'
            """, (
                error,
                row["id"],
            ))

            conn.commit()

            print(
                "[PROCESS FAILURE RECORDED]",
                "| source=",
                source_id,
                "| run_id=",
                row["id"],
                flush=True,
            )

            return

        if row and row["status"] == "FAILED":
            return

        conn.execute("""
            INSERT INTO ingestion_runs (
                provider,
                provider_source_id,
                transport_type,
                status,
                started_at,
                finished_at,
                error
            )
            VALUES (
                ?,
                ?,
                ?,
                'FAILED',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                ?
            )
        """, (
            provider or "UNKNOWN",
            source_key,
            provider,
            error,
        ))

        conn.commit()

        print(
            "[SYNTHETIC PROCESS FAILURE RECORDED]",
            "| source=",
            source_id,
            flush=True,
        )


def run_single_source(
    source_id,
    *,
    timeout_seconds,
    provider=None,
):
    exit_code = run_command(
        [
            sys.executable,
            "-u",
            "-m",
            "app.run_universal_ingestion",
            "--source-id",
            str(source_id),
        ],
        timeout_seconds=timeout_seconds,
    )

    if exit_code == 124:
        record_process_failure(
            source_id,
            provider,
            (
                "SOURCE_TIMEOUT: exceeded "
                f"{timeout_seconds} seconds"
            ),
        )

    elif exit_code != 0:
        record_process_failure(
            source_id,
            provider,
            (
                "SOURCE_PROCESS_EXIT: "
                f"exit={exit_code}"
            ),
        )

    return exit_code


def run_initial_source_pass(
    registry,
    *,
    timeout_seconds,
):
    source_ids = sorted(
        registry
    )

    process_errors = []

    print()
    print("=" * 110)
    print("INITIAL PER-SOURCE INGESTION PASS")
    print("=" * 110)

    print(
        "SOURCES:",
        len(source_ids),
    )

    print(
        "SOURCE TIMEOUT:",
        timeout_seconds,
        "seconds",
    )

    for index, source_id in enumerate(
        source_ids,
        1,
    ):
        source = registry.get(
            source_id,
            {},
        )

        print()
        print("=" * 110)

        print(
            f"[{index}/{len(source_ids)}]",
            source_id,
            "|",
            source.get(
                "employer_name",
                "UNKNOWN",
            ),
            "|",
            source.get(
                "ats",
                "UNKNOWN",
            ),
        )

        print("=" * 110)

        exit_code = run_single_source(
            source_id,
            timeout_seconds=timeout_seconds,
            provider=source.get("ats"),
        )

        if exit_code != 0:
            process_errors.append(
                {
                    "source_id": source_id,
                    "exit_code": exit_code,
                }
            )

            print(
                "[SOURCE PROCESS ERROR]",
                f"source={source_id}",
                f"exit={exit_code}",
                flush=True,
            )

    return process_errors

def latest_current_pass_runs(
    baseline_run_id,
):
    """
    Get exactly one latest ingestion run per source,
    considering only runs created during this wrapper run.

    Historical failures are intentionally ignored.
    """

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT r.*
            FROM ingestion_runs r

            JOIN (
                SELECT
                    provider_source_id,
                    MAX(id) AS latest_id

                FROM ingestion_runs

                WHERE id > ?
                  AND provider_source_id IS NOT NULL

                GROUP BY
                    provider_source_id
            ) latest
              ON latest.latest_id=r.id

            ORDER BY
                r.id
        """, (
            baseline_run_id,
        )).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def current_failures(
    baseline_run_id,
    registry,
):
    rows = latest_current_pass_runs(
        baseline_run_id
    )

    failures = []

    for row in rows:

        if row["status"] != "FAILED":
            continue

        raw_source_id = row[
            "provider_source_id"
        ]

        try:
            source_id = int(
                raw_source_id
            )
        except (
            TypeError,
            ValueError,
        ):
            print(
                "[RETRY WARNING] "
                "Non-numeric provider_source_id:",
                raw_source_id,
            )
            continue

        source = registry.get(
            source_id,
            {},
        )

        failures.append(
            Failure(
                source_id=source_id,

                employer_name=(
                    source.get(
                        "employer_name"
                    )
                    or f"SOURCE {source_id}"
                ),

                provider=row.get(
                    "provider"
                ),

                status=row[
                    "status"
                ],

                error=row.get(
                    "error"
                ),

                run_id=int(
                    row["id"]
                ),
            )
        )

    return failures


def print_failures(
    failures,
    *,
    heading,
):
    print()
    print("=" * 110)
    print(heading)
    print("=" * 110)

    if not failures:
        print("NONE")
        return

    for failure in failures:
        print()
        print(
            f"SOURCE={failure.source_id} | "
            f"{failure.employer_name} | "
            f"{failure.provider or '-'}"
        )

        print(
            "RUN:",
            failure.run_id,
        )

        print(
            "ERROR:",
            failure.error,
        )


def sleep_before_retry(
    retry_number,
    *,
    no_backoff,
):
    if no_backoff:
        return

    index = min(
        retry_number - 1,
        len(DEFAULT_BACKOFFS) - 1,
    )

    seconds = DEFAULT_BACKOFFS[
        index
    ]

    print()
    print(
        f"BACKOFF: {seconds}s"
    )

    time.sleep(
        seconds
    )


def main():
    args = parse_args()

    registry = source_map()

    baseline_run_id = max_run_id()

    print("=" * 110)
    print("V112.2 RESILIENT UNIVERSAL INGESTION")
    print("=" * 110)

    print(
        "ENABLED SOURCES:",
        len(registry),
    )

    print(
        "BASELINE RUN ID:",
        baseline_run_id,
    )

    pipeline_started = time.perf_counter()

    # ======================================================
    # INITIAL ISOLATED SOURCE PASS
    # ======================================================

    initial_process_errors = (
        run_initial_source_pass(
            registry,
            timeout_seconds=(
                args.source_timeout
            ),
        )
    )

    if initial_process_errors:
        print()
        print(
            "INITIAL SOURCE PROCESS ERRORS:",
            len(initial_process_errors),
        )

    failures = current_failures(
        baseline_run_id,
        registry,
    )

    print_failures(
        failures,
        heading=(
            "FAILED SOURCES AFTER INITIAL PASS"
        ),
    )

    initial_failed = len(
        failures
    )

    # ======================================================
    # TARGETED RETRIES
    # ======================================================

    retry_round = 0

    while (
        failures
        and retry_round < args.max_retries
    ):

        retry_round += 1

        print()
        print("=" * 110)
        print(
            f"RETRY ROUND {retry_round}"
        )
        print("=" * 110)

        print(
            "SOURCES TO RETRY:",
            len(failures),
        )

        sleep_before_retry(
            retry_round,
            no_backoff=(
                args.no_backoff
            ),
        )

        source_ids = [
            failure.source_id
            for failure in failures
        ]

        for source_id in source_ids:

            source = registry.get(
                source_id,
                {},
            )

            print()
            print("-" * 110)

            print(
                "RETRY:",
                source_id,
                "|",
                source.get(
                    "employer_name",
                    "UNKNOWN",
                ),
                "|",
                source.get(
                    "ats",
                    "UNKNOWN",
                ),
            )

            # run_universal_ingestion catches individual
            # collector exceptions and records FAILED in
            # ingestion_runs. A non-zero subprocess exit
            # therefore means a larger process-level crash.
            exit_code = run_single_source(
                source_id,
                timeout_seconds=(
                    args.source_timeout
                ),
                provider=source.get("ats"),
            )

            if exit_code != 0:
                print(
                    "[RETRY PROCESS ERROR] "
                    f"source={source_id} "
                    f"exit={exit_code}"
                )

        # Re-read latest statuses after every retry round.
        # A successful retry supersedes the earlier failure.
        failures = current_failures(
            baseline_run_id,
            registry,
        )

        print_failures(
            failures,
            heading=(
                f"FAILED SOURCES AFTER "
                f"RETRY ROUND {retry_round}"
            ),
        )

    # ======================================================
    # FINAL CURRENT-PASS AUDIT
    # ======================================================

    latest = latest_current_pass_runs(
        baseline_run_id
    )

    status_counts = {}

    for row in latest:
        status = row[
            "status"
        ]

        status_counts[
            status
        ] = (
            status_counts.get(
                status,
                0,
            )
            + 1
        )

    duration = round(
        time.perf_counter()
        - pipeline_started,
        2,
    )

    print()
    print("=" * 110)
    print("V112.2 INGESTION SUMMARY")
    print("=" * 110)

    print(
        "CURRENT-PASS SOURCES:",
        len(latest),
    )

    print(
        "INITIAL FAILED:",
        initial_failed,
    )

    print(
        "PERSISTENT FAILED:",
        len(failures),
    )

    print(
        "RETRY ROUNDS:",
        retry_round,
    )

    print(
        "STATUS COUNTS:",
        status_counts,
    )

    print(
        "DURATION:",
        duration,
        "seconds",
    )

    if failures:
        print_failures(
            failures,
            heading=(
                "PERSISTENT INGESTION FAILURES"
            ),
        )

        # Normal production mode does NOT kill the complete
        # refresh because one external provider is down.
        #
        # Failed runs also do not finalize lifecycle, so
        # existing jobs from that source remain protected.
        if args.strict:
            raise SystemExit(1)

        print()
        print(
            "[DEGRADED SUCCESS] "
            "Persistent source failures remain, "
            "but downstream pipeline may continue."
        )

    else:
        print()
        print(
            "[SUCCESS] All current-pass sources "
            "completed after retries."
        )


if __name__ == "__main__":
    main()
