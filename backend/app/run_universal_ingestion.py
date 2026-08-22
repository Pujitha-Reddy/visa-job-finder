from __future__ import annotations

import argparse

from app.database import get_connection

from app.registry.repository import (
    init_registry,
    list_enabled_sources,
)

from app.ingestion.providers.registry import (
    collect_source,
)

from app.ingestion.repository import (
    save_observations,
)

from app.ingestion.runs import (
    start_run,
    finish_run,
    fail_run,
)

from app.ingestion.lifecycle import (
    finalize_source_snapshot,
    refresh_source_canonical_lifecycle,
)




def source_had_nonzero_success(
    *,
    provider,
    provider_source_id,
):
    """
    Return True if this source has ever completed a successful
    ingestion with at least one observation.

    This protects sources whose current observation store is
    empty but which historically exposed jobs.
    """

    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1 AS found
            FROM ingestion_runs
            WHERE provider=?
              AND provider_source_id=?
              AND status IN ('SUCCESS', 'PARTIAL')
              AND raw_found > 0
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                provider,
                str(provider_source_id),
            ),
        ).fetchone()

    return row is not None


def active_observation_count(
    *,
    provider,
    provider_source_id,
):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM job_observations
            WHERE provider=?
              AND provider_source_id=?
              AND COALESCE(is_active, 1)=1
            """,
            (
                provider,
                str(provider_source_id),
            ),
        ).fetchone()

    return int(
        row["n"]
        if row
        else 0
    )



def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Run provider-neutral job ingestion "
            "into job_observations."
        )
    )

    parser.add_argument(
        "--source-id",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--employer",
        default=None,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    init_registry()

    sources = list_enabled_sources()

    if args.source_id is not None:
        sources = [
            source
            for source in sources
            if source["source_id"]
            == args.source_id
        ]

    if args.employer:
        target = (
            args.employer
            .strip()
            .lower()
        )

        sources = [
            source
            for source in sources
            if (
                source["employer_name"]
                .strip()
                .lower()
                == target
            )
        ]

    print(
        "UNIVERSAL INGESTION SOURCES:",
        len(sources),
    )

    totals = {
        "sources": len(sources),
        "raw": 0,
        "inserted": 0,
        "updated": 0,
        "errors": 0,
    }

    for source in sources:
        name = source[
            "employer_name"
        ]

        ats = source[
            "ats"
        ]

        print()
        print("=" * 100)
        print(
            "SOURCE:",
            source["source_id"],
            "|",
            name,
            "|",
            ats,
        )

        run_id = start_run(
            provider=ats,
            provider_source_id=str(
                source["source_id"]
            ),
            transport_type=ats,
            metadata={
                "employer": name,
                "careers_url": (
                    source.get(
                        "careers_url"
                    )
                ),
            },
        )

        try:
            collection = collect_source(
                source
            )

            observations = (
                collection.observations
            )

            saved = save_observations(
                observations,
                ingestion_run_id=run_id,
            )

            print(
                "[SNAPSHOT]",
                name,
                "| complete=",
                collection.snapshot_complete,
                "| scanned=",
                collection.records_scanned,
                "| expected=",
                collection.expected_total,
                "| pages=",
                collection.pages_completed,
                "| termination=",
                collection.termination_reason,
            )

            # ==================================================
            # SOURCE SNAPSHOT LIFECYCLE
            #
            # We are inside the successful collection path.
            # Failed runs never reach this block.
            # ==================================================

            previous_active = active_observation_count(
                provider=ats,
                provider_source_id=source["source_id"],
            )

            historical_nonzero = (
                source_had_nonzero_success(
                    provider=ats,
                    provider_source_id=source["source_id"],
                )
            )

            suspicious_zero = (
                len(observations) == 0
                and (
                    previous_active > 0
                    or historical_nonzero
                )
            )

            lifecycle_allowed = (
                collection.snapshot_complete
                and not suspicious_zero
            )

            if suspicious_zero:
                print(
                    "[ZERO SNAPSHOT QUARANTINED]",
                    name,
                    "|",
                    ats,
                    "| previous_active=",
                    previous_active,
                    "| historical_nonzero=",
                    historical_nonzero,
                )

            elif not collection.snapshot_complete:
                print(
                    "[INCOMPLETE SNAPSHOT]",
                    name,
                    "|",
                    ats,
                    "| lifecycle deactivation skipped",
                    "| scanned=",
                    collection.records_scanned,
                    "| expected=",
                    collection.expected_total,
                    "| termination=",
                    collection.termination_reason,
                )

            if lifecycle_allowed:
                lifecycle = finalize_source_snapshot(
                    provider=ats,
                    provider_source_id=str(
                        source["source_id"]
                    ),
                    ingestion_run_id=run_id,
                )

                canonical_lifecycle = (
                    refresh_source_canonical_lifecycle(
                        provider=ats,
                        provider_source_id=str(
                            source["source_id"]
                        ),
                    )
                )

            else:
                lifecycle = {
                    "observations_deactivated": 0,
                }

                canonical_lifecycle = {
                    "canonical_jobs_deactivated": 0,
                }

            totals["raw"] += len(
                observations
            )

            totals["inserted"] += (
                saved["inserted"]
            )

            totals["updated"] += (
                saved["updated"]
            )

            totals["errors"] += (
                saved["errors"]
            )

            finish_run(
                run_id,

                status=(
                    "SUCCESS"
                    if saved["errors"] == 0
                    else "PARTIAL"
                ),

                raw_found=len(
                    observations
                ),

                inserted=saved[
                    "inserted"
                ],

                updated=saved[
                    "updated"
                ],

                failed=saved[
                    "errors"
                ],
            )

            with __import__(
                "app.database",
                fromlist=["get_connection"],
            ).get_connection() as conn:
                conn.execute(
                    """
                    UPDATE ingestion_runs
                    SET
                        observations_deactivated=?,
                        canonical_jobs_deactivated=?
                    WHERE id=?
                    """,
                    (
                        lifecycle[
                            "observations_deactivated"
                        ],
                        canonical_lifecycle[
                            "canonical_jobs_deactivated"
                        ],
                        run_id,
                    ),
                )
                conn.commit()

            print(
                f"{len(observations)} observations | "
                f"{saved['inserted']} inserted | "
                f"{saved['updated']} updated | "
                f"{saved['errors']} errors"
            )

        except Exception as exc:
            totals["errors"] += 1

            fail_run(
                run_id,
                exc,
            )

            print(
                "[INGESTION ERROR]",
                name,
                "|",
                ats,
                "|",
                repr(exc),
            )

    print()
    print("=" * 100)
    print(
        "UNIVERSAL INGESTION SUMMARY"
    )
    print("=" * 100)
    print(totals)


if __name__ == "__main__":
    main()
