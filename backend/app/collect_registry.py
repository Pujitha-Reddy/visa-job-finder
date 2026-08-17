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
}
from .collectors.factory import get_collector
from .classifiers.pipeline import analyze_job
from .classifiers.eligibility_v83 import eligibility_gate
from .jobs_repository import save_jobs
from .lifecycle_v87 import mark_source_lifecycle


def main():
    init_registry()

    sources = list_enabled_sources()

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
        collector = get_collector(source["ats"])

        if not collector:
            totals["errors"] += 1

            print(
                f"[ERROR] No collector for "
                f"{source['employer_name']} "
                f"[{source['ats']}]"
            )

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
                    analyzed.append(job)
                else:
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

            print(
                f"[ERROR] "
                f"{source['employer_name']} "
                f"[{source['ats']}]: "
                f"{exc}"
            )

    print(totals)


if __name__ == "__main__":
    main()
