from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass
class Step:
    name: str
    command: list[str]
    required: bool = True


STEPS = (
    Step(
        "universal_ingestion",
        [
            sys.executable,
            "-m",
            "app.run_resilient_ingestion",
        ],
    ),

    Step(
        "employer_resolution",
        [
            sys.executable,
            "-m",
            "app.reconcile_job_observations",
        ],
    ),

    Step(
        "canonicalization",
        [
            sys.executable,
            "-m",
            "app.canonicalize_job_observations",
        ],
    ),

    Step(
        "software_classification",
        [
            sys.executable,
            "-m",
            "app.run_v109_software_classification",
        ],
    ),

    Step(
        "location_enrichment",
        [
            sys.executable,
            "-m",
            "app.run_v109_location_enrichment",
        ],
    ),

    Step(
        "experience_enrichment",
        [
            sys.executable,
            "-m",
            "app.run_v109_experience_enrichment",
        ],
    ),

    Step(
        "sponsorship_enrichment",
        [
            sys.executable,
            "-m",
            "app.run_v109_sponsorship_enrichment",
        ],
    ),

    Step(
        "eligibility",
        [
            sys.executable,
            "-m",
            "app.run_v109_eligibility",
        ],
    ),

    Step(
        "ranking",
        [
            sys.executable,
            "-m",
            "app.run_v109_ranking",
        ],
    ),

    Step(
        "postgres_sync",
        [
            sys.executable,
            "-m",
            "app.sync_canonical_to_postgres",
            "--skip-identities",
        ],
    ),
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run the complete V112 job-board refresh pipeline."
        )
    )

    parser.add_argument(
        "--from-step",
        default=None,
        help=(
            "Start at a named step instead of the beginning."
        ),
    )

    parser.add_argument(
        "--skip-postgres",
        action="store_true",
        help=(
            "Run the local canonical pipeline without "
            "syncing PostgreSQL."
        ),
    )

    return parser.parse_args()


def run_step(step: Step):
    print()
    print("=" * 110)
    print("V112 STEP:", step.name)
    print("=" * 110)

    started = time.perf_counter()

    result = subprocess.run(
        step.command,
        check=False,
    )

    duration = round(
        time.perf_counter() - started,
        2,
    )

    if result.returncode != 0:
        print()
        print(
            f"[FAILED] {step.name} "
            f"exit={result.returncode} "
            f"duration={duration}s"
        )

        return {
            "name": step.name,
            "status": "FAILED",
            "returncode": result.returncode,
            "duration_seconds": duration,
        }

    print()
    print(
        f"[SUCCESS] {step.name} "
        f"duration={duration}s"
    )

    return {
        "name": step.name,
        "status": "SUCCESS",
        "returncode": 0,
        "duration_seconds": duration,
    }


def main():
    args = parse_args()

    steps = list(
        STEPS
    )

    if args.skip_postgres:
        steps = [
            step
            for step in steps
            if step.name != "postgres_sync"
        ]

    if args.from_step:
        names = [
            step.name
            for step in steps
        ]

        if args.from_step not in names:
            raise SystemExit(
                "Unknown --from-step. Valid values: "
                + ", ".join(names)
            )

        index = names.index(
            args.from_step
        )

        steps = steps[
            index:
        ]

    print("=" * 110)
    print("V112 UNIVERSAL REFRESH PIPELINE")
    print("=" * 110)

    print(
        "STEPS:",
        [
            step.name
            for step in steps
        ],
    )

    pipeline_started = time.perf_counter()

    results = []

    for step in steps:

        result = run_step(
            step
        )

        results.append(
            result
        )

        if (
            result["status"]
            == "FAILED"
            and step.required
        ):
            print()
            print(
                "PIPELINE STOPPED AT:",
                step.name,
            )
            break

    total_duration = round(
        time.perf_counter()
        - pipeline_started,
        2,
    )

    print()
    print("=" * 110)
    print("V112 PIPELINE SUMMARY")
    print("=" * 110)

    for result in results:
        print(
            f"{result['status']:<8} | "
            f"{result['duration_seconds']:>8.2f}s | "
            f"{result['name']}"
        )

    failures = [
        result
        for result in results
        if result["status"] == "FAILED"
    ]

    print()
    print(
        "TOTAL DURATION:",
        total_duration,
        "seconds",
    )

    print(
        "FAILURES:",
        len(failures),
    )

    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
