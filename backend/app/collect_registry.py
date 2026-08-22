from datetime import datetime, timezone
import time
import argparse
from .registry.repository import (
    init_registry,
    list_enabled_sources,
    mark_source_result,
)
LIFECYCLE_SAFE_ATS = {
    "GREENHOUSE",
    "ASHBY",
    "LEVER",
    "SMARTRECRUITERS",
    "WORKDAY",
    "AMAZON",
    "GENERIC",
}
from .collectors.factory import get_collector
from .classifiers.pipeline import analyze_job
from .classifiers.eligibility_v83 import eligibility_gate
from .jobs_repository import save_jobs
from .eligibility_reconciliation import reconcile_job_eligibility
from .lifecycle_v87 import mark_source_lifecycle
from .source_health_repository import (
    record_source_success,
    record_source_failure,
)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Collect jobs from enabled employer sources."
    )

    parser.add_argument(
        "--source-id",
        type=int,
        default=None,
        help="Run only one employer source ID.",
    )

    parser.add_argument(
        "--employer",
        type=str,
        default=None,
        help="Run only sources for one employer name.",
    )

    return parser.parse_args()

def main():
    args = parse_args()
    init_registry()

    sources = list_enabled_sources()

    # ------------------------------------------------------
    # Optional single-source / employer filtering
    # ------------------------------------------------------

    if args.source_id is not None:
        sources = [
            source
            for source in sources
            if source["source_id"] == args.source_id
        ]

    if args.employer:
        target = args.employer.strip().lower()

        sources = [
            source
            for source in sources
            if source["employer_name"].strip().lower() == target
        ]

    if (
        args.source_id is not None
        or args.employer
    ):
        print(
            f"[SOURCE FILTER] Running {len(sources)} source(s): "
            f"{[(s['source_id'], s['employer_name'], s['ats']) for s in sources]}"
        )



    totals = {
        "sources": len(sources),
        "raw_found": 0,
        "eligible": 0,
        "excluded": 0,
        "deduped": 0,
        "added": 0,
        "updated": 0,
        "errors": 0,
        "lifecycle_disappeared": 0,
    }

    for source in sources:
        source_started_at = datetime.now(timezone.utc)
        source_timer = time.perf_counter()

        collector = get_collector(source["ats"])

        if not collector:
            totals["errors"] += 1

            error = (
                f"No collector for "
                f"{source['employer_name']} "
                f"[{source['ats']}]"
            )

            record_source_failure(
                source,
                error=error,
                started_at=source_started_at,
                duration_ms=int(
                    (time.perf_counter() - source_timer)
                    * 1000
                ),
            )

            print(f"[ERROR] {error}")

            continue

        try:
            # ---------------------------------------------
            # FETCH RAW JOBS
            # ---------------------------------------------

            raw_jobs = collector.fetch(source)

            totals["raw_found"] += len(raw_jobs)

            # ---------------------------------------------
            # CLASSIFY + ELIGIBILITY GATE
            # ---------------------------------------------

            analyzed = []
            excluded = []

            for raw_job in raw_jobs:
                job = analyze_job(raw_job)

                gate = eligibility_gate(job)

                # Preserve eligibility/debug information.
                #
                # Only fields that exist in the jobs schema
                # will actually be written by save_jobs().
                job["eligibility_reason"] = gate["reason"]

                job["location_eligibility"] = gate["location"]

                job["experience_eligibility"] = gate[
                    "experience"
                ]

                job["source_confidence_score"] = gate[
                    "source_confidence_score"
                ]

                job["source_confidence_label"] = gate[
                    "source_confidence_label"
                ]

                if gate["eligible"]:
                    job["is_eligible"] = 1
                    analyzed.append(job)
                else:
                    job["is_eligible"] = 0
                    excluded.append(job)

            totals["eligible"] += len(analyzed)
            totals["excluded"] += len(excluded)

            # ---------------------------------------------
            # DEDUPE CURRENT SOURCE BATCH
            # ---------------------------------------------

            unique = {}

            for job in analyzed:
                key = (
                    job.get("dedupe_key")
                    or job.get("source_url")
                )

                if key and key not in unique:
                    unique[key] = job

            unique_jobs = list(unique.values())

            totals["deduped"] += max(
                0,
                len(analyzed) - len(unique_jobs),
            )

            # ---------------------------------------------
            # SAVE ONLY ELIGIBLE + UNIQUE JOBS
            # ---------------------------------------------

            saved = save_jobs(unique_jobs)

            totals["added"] += saved["added"]
            totals["updated"] += saved["updated"]
            totals["errors"] += saved["errors"]

            # ---------------------------------------------
            # SAVE-FAILURE HEALTH PROTECTION
            #
            # A collector fetch can succeed while every
            # eligible DB save fails. That source must NOT
            # be marked healthy and lifecycle must NOT run,
            # because doing so could hide valid existing
            # records after a persistence failure.
            # ---------------------------------------------

            attempted_saves = len(unique_jobs)

            successful_saves = (
                saved["added"]
                + saved["updated"]
            )

            if (
                attempted_saves > 0
                and saved["errors"] >= attempted_saves
                and successful_saves == 0
            ):
                raise RuntimeError(
                    "All eligible job saves failed: "
                    f"attempted={attempted_saves}, "
                    f"errors={saved['errors']}"
                )

            # ---------------------------------------------
            # ELIGIBILITY RECONCILIATION
            #
            # Lifecycle and feed eligibility are separate:
            #
            # is_active:
            #   Does the posting still exist at the source?
            #
            # is_eligible:
            #   Does the posting currently belong in the
            #   user's feed?
            #
            # Excluded jobs are NOT inserted here.
            # Existing records are updated if their current
            # source version has become ineligible.
            # ---------------------------------------------

            eligibility_reconciliation = (
                reconcile_job_eligibility(
                    source["employer_name"],
                    unique_jobs,
                    excluded,
                )
            )

            # ---------------------------------------------
            # LIFECYCLE
            #
            # IMPORTANT:
            # Use RAW source URLs, not eligible URLs.
            #
            # Lifecycle means:
            # "Does this job still exist at the source?"
            #
            # Eligibility means:
            # "Do we want this job in the user's feed?"
            #
            # These are different questions.
            # ---------------------------------------------

            if source["ats"] in LIFECYCLE_SAFE_ATS:
                lifecycle = mark_source_lifecycle(
                    source["employer_name"],
                    source["ats"],
                    {
                        job.get("source_url")
                        for job in raw_jobs
                        if job.get("source_url")
                    },
                 )
            else:
                lifecycle = {
                    "active": 0,
                    "disappeared": 0,
                }

            totals["lifecycle_disappeared"] += lifecycle["disappeared"]

            # ---------------------------------------------
            # MARK SOURCE SUCCESS
            # ---------------------------------------------

            mark_source_result(
                source["source_id"],
                len(raw_jobs),
                True,
            )

            record_source_success(
                source,
                raw_jobs=len(raw_jobs),
                eligible_jobs=len(analyzed),
                excluded_jobs=len(excluded),
                added_jobs=saved["added"],
                updated_jobs=saved["updated"],
                disappeared_jobs=lifecycle["disappeared"],
                started_at=source_started_at,
                duration_ms=int(
                    (time.perf_counter() - source_timer)
                    * 1000
                ),
            )

            # ---------------------------------------------
            # SOURCE LOG
            # ---------------------------------------------

            print(
                f"{source['employer_name']} "
                f"[{source['ats']}]: "
                f"{len(raw_jobs)} raw / "
                f"{len(analyzed)} eligible / "
                f"{len(unique_jobs)} unique / "
                f"{saved['added']} added / "
                f"{saved['updated']} updated / "
                f"{len(excluded)} excluded / "
                f"{lifecycle['disappeared']} inactive"
            )

        except Exception as exc:
            totals["errors"] += 1

            # ---------------------------------------------
            # IMPORTANT:
            #
            # Do NOT call lifecycle here.
            #
            # If an ATS/API is temporarily unavailable,
            # we must NOT mark all of that employer's
            # existing jobs inactive.
            # ---------------------------------------------

            mark_source_result(
                source["source_id"],
                0,
                False,
            )

            record_source_failure(
                source,
                error=str(exc),
                started_at=source_started_at,
                duration_ms=int(
                    (time.perf_counter() - source_timer)
                    * 1000
                ),
            )

            print(
                f"[ERROR] "
                f"{source['employer_name']} "
                f"[{source['ats']}]: "
                f"{exc}"
            )

    print(totals)


if __name__ == "__main__":
    main()
