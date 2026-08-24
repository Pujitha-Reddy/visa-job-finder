from __future__ import annotations

import argparse

from collections import Counter

from app.ats_parameter_resolver import (
    ATSParameterResolver,
)
from app.database import get_connection
from app.source_discovery_engine import (
    SourceDiscoveryEngine,
)
from app.collectors.factory import get_collector

SUPPORTED_AUTO_VERIFY_ATS = {
    "WORKDAY",
    "GREENHOUSE",
    "LEVER",
    "EIGHTFOLD",
    "SMARTRECRUITERS",
    "ASHBY",
    "RADANCY",
    "RADANCY_SAS",
}

PARAMETER_RESOLVER = ATSParameterResolver()


def source_dict(
    employer_name,
    candidate,
):
    return {
        "employer_name": employer_name,
        "ats": candidate.ats,
        "token": candidate.token,
        "careers_url": candidate.careers_url,
    }


def verify_ats_candidate(
    employer_name,
    candidate,
):
    """
    Verify one employer candidate without allowing a resolver,
    collector-construction, or collector-fetch exception to abort
    verification of the remaining employers.
    """

    ats = (
        candidate.ats
        or ""
    ).upper()

    if ats not in SUPPORTED_AUTO_VERIFY_ATS:
        return {
            "verified": False,
            "status": "UNSUPPORTED_ATS",
            "jobs": 0,
            "error": None,
        }

    try:
        collector = get_collector(
            ats
        )

    except Exception as exc:
        return {
            "verified": False,
            "status": "COLLECTOR_INIT_FAILED",
            "jobs": 0,
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }

    if not collector:
        return {
            "verified": False,
            "status": "NO_COLLECTOR",
            "jobs": 0,
            "error": None,
        }

    careers_url = (
        candidate.careers_url
    )

    token = candidate.token

    # -----------------------------------------------------
    # Automatically resolve missing ATS parameters.
    # Resolver failure belongs only to this employer.
    # -----------------------------------------------------

    if not token:
        try:
            resolved = (
                PARAMETER_RESOLVER.resolve(
                    ats,
                    careers_url,
                )
            )

        except Exception as exc:
            return {
                "verified": False,
                "status":
                    "PARAMETER_RESOLUTION_FAILED",
                "jobs": 0,
                "error": (
                    f"{type(exc).__name__}: {exc}"
                ),
            }

        if resolved:
            careers_url = (
                resolved.careers_url
            )

            token = resolved.token

            print(
                "ATS PARAMS:",
                {
                    "ats":
                        resolved.ats,
                    "careers_url":
                        resolved.careers_url,
                    "token":
                        resolved.token,
                    "confidence":
                        resolved.confidence,
                    "evidence":
                        resolved.evidence,
                },
            )

    source = {
        "employer_name":
            employer_name,
        "ats":
            ats,
        "token":
            token,
        "careers_url":
            careers_url,
    }

    try:
        jobs = collector.fetch(
            source
        )

    except Exception as exc:
        return {
            "verified": False,
            "status": "COLLECTOR_FAILED",
            "jobs": 0,
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }

    jobs = jobs or []

    valid = [
        job
        for job in jobs
        if (
            job.get("title")
            and job.get("source_url")
        )
    ]

    if not valid:
        return {
            "verified": False,
            "status": "ZERO_JOBS",
            "jobs": 0,
            "error": None,
        }

    unique_urls = {
        job.get("source_url")
        for job in valid
        if job.get("source_url")
    }

    if not unique_urls:
        return {
            "verified": False,
            "status": "NO_STABLE_URLS",
            "jobs": 0,
            "error": None,
        }

    return {
        "verified": True,
        "status": "VERIFIED",
        "jobs": len(valid),
        "unique_urls":
            len(unique_urls),
        "resolved_token":
            token,
        "resolved_careers_url":
            careers_url,
        "error": None,
    }


def verify_generic_job_list(
    candidate,
):
    """
    Discovery already proved this surface exposes
    repeated job-detail URLs.

    This is not yet sufficient for automatic promotion,
    but it is strong enough to route into the generic
    collector/verifier stage.
    """

    if candidate.source_type != "GENERIC_JOB_LIST":
        return {
            "verified": False,
            "status": "NOT_GENERIC_JOB_LIST",
        }

    return {
        "verified": False,
        "status": "GENERIC_VERIFICATION_REQUIRED",
    }



def parse_args():
    parser = argparse.ArgumentParser(
        description="Verify automatically discovered sources."
    )

    parser.add_argument(
        "--batch-name",
        default="SPONSOR_EXPANSION_V1",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help=(
            "Maximum number of pending source candidates "
            "to verify during this invocation."
        ),
    )

    return parser.parse_args()


def main():
    args = parse_args()

    engine = SourceDiscoveryEngine()

    with get_connection() as c:
        rows = c.execute("""
            SELECT
                id,
                display_name,
                careers_candidate_url,
                careers_discovery_status,
                source_discovery_score
            FROM source_discovery_batches
            WHERE batch_name=?
              AND resolution_status='PENDING'
              AND verification_status='UNVERIFIED'
              AND careers_candidate_url IS NOT NULL
            ORDER BY
                updated_at ASC,
                source_discovery_score DESC,
                display_name
            LIMIT ?
        """, (
            args.batch_name,
            max(1, int(args.limit)),
        )).fetchall()

    print(
        "AUTO VERIFY TARGETS:",
        len(rows),
    )

    results = []

    for row in rows:
        name = row["display_name"]
        careers_url = row["careers_candidate_url"]

        print()
        print("=" * 110)
        print(
            "EMPLOYER:",
            name,
        )
        print(
            "CAREERS:",
            careers_url,
        )

        try:
            candidates = engine.discover(
                name,
                careers_url,
            )

        except Exception as exc:
            print(
                "[DISCOVERY ERROR]",
                name,
                "|",
                repr(exc),
            )

            results.append(
                {
                    "id": row["id"],
                    "name": name,
                    "status": "DISCOVERY_FAILED",
                    "ats": None,
                    "careers_url": careers_url,
                    "token": None,
                    "error": repr(exc),
                }
            )

            continue

        verified = None

        for candidate in candidates:
            print()
            print(
                "TRY:",
                candidate.source_type,
                "|",
                candidate.ats,
                "|",
                candidate.careers_url,
            )

            # ---------------------------------------------
            # Existing ATS collector
            # ---------------------------------------------

            if candidate.ats:
                result = verify_ats_candidate(
                    name,
                    candidate,
                )

                print(
                    "RESULT:",
                    result,
                )

                if result["verified"]:
                    verified = {
                        "candidate": candidate,
                        "result": result,
                    }
                    break

                continue

            # ---------------------------------------------
            # Generic repeated job-list surface
            # ---------------------------------------------

            generic = verify_generic_job_list(candidate)

            if generic["status"] == "GENERIC_VERIFICATION_REQUIRED":
                print(
                    "RESULT:",
                    generic,
                )

        if verified:
            candidate = verified["candidate"]

            result = verified["result"]

            results.append(
                {
                    "id": row["id"],
                    "name": name,
                    "status": "VERIFIED_ATS",
                    "ats": candidate.ats,
                    "careers_url": (
                        result.get("resolved_careers_url")
                        or candidate.careers_url
                    ),
                    "token": (
                        result.get("resolved_token")
                        or candidate.token
                    ),
                    "jobs": result["jobs"],
                }
            )

        else:
            generic_candidate = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.source_type == "GENERIC_JOB_LIST"
                ),
                None,
            )

            has_generic = (
                generic_candidate is not None
            )

            has_unsupported = any(
                candidate.ats
                and candidate.ats.upper()
                not in SUPPORTED_AUTO_VERIFY_ATS
                for candidate in candidates
            )

            if has_generic:
                status = "GENERIC_VERIFICATION_REQUIRED"

            elif has_unsupported:
                status = "UNSUPPORTED_ATS"

            else:
                status = "SOURCE_UNRESOLVED"

            unsupported_ats = sorted({
                candidate.ats.upper()
                for candidate in candidates
                if (
                    candidate.ats
                    and candidate.ats.upper()
                    not in SUPPORTED_AUTO_VERIFY_ATS
                )
            })

            results.append(
                {
                    "id": row["id"],
                    "name": name,
                    "status": status,
                    "ats": (
                        ",".join(unsupported_ats)
                        if unsupported_ats
                        else None
                    ),
                    "careers_url": (
                        generic_candidate.careers_url
                        if generic_candidate
                        else careers_url
                    ),
                    "token": None,
                    "jobs": 0,
                }
            )

    # ======================================================
    # Persist verification results
    # ======================================================

    with get_connection() as c:
        for result in results:
            status = result["status"]

            if status == "VERIFIED_ATS":
                c.execute(
                    """
                    UPDATE source_discovery_batches
                    SET
                        resolution_status='RESOLVED',
                        verification_status='VERIFIED',
                        discovered_ats=?,
                        discovered_careers_url=?,
                        discovered_token=?,
                        notes=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        result["ats"],
                        result["careers_url"],
                        result.get("token"),
                        (
                            "Automatic ATS verification succeeded. "
                            f"jobs={result['jobs']}"
                        ),
                        result["id"],
                    ),
                )

            elif status == "GENERIC_VERIFICATION_REQUIRED":
                c.execute(
                    """
                    UPDATE source_discovery_batches
                    SET
                        resolution_status='PENDING',
                        verification_status='UNVERIFIED',
                        discovered_ats=NULL,
                        discovered_careers_url=?,
                        discovered_token=NULL,
                        notes=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        result["careers_url"],
                        "Generic job-list verification required.",
                        result["id"],
                    ),
                )

            elif status == "UNSUPPORTED_ATS":
                c.execute(
                    """
                    UPDATE source_discovery_batches
                    SET
                        resolution_status='PENDING',
                        verification_status='UNVERIFIED',
                        discovered_ats=?,
                        discovered_careers_url=?,
                        discovered_token=NULL,
                        notes=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        result["ats"],
                        result["careers_url"],
                        (
                            "ATS detected but automatic verifier "
                            "does not yet support it."
                        ),
                        result["id"],
                    ),
                )

            else:
                c.execute(
                    """
                    UPDATE source_discovery_batches
                    SET
                        resolution_status='PENDING',
                        verification_status='UNVERIFIED',
                        discovered_ats=NULL,
                        discovered_token=NULL,
                        notes=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (
                        "Automatic source verification unresolved.",
                        result["id"],
                    ),
                )

        c.commit()

    print()
    print("=" * 110)
    print("AUTO SOURCE VERIFICATION SUMMARY")
    print("=" * 110)

    counts = Counter()

    for result in results:
        counts[result["status"]] += 1

        print(
            f"{result['name']:<42} | "
            f"{result['status']:<32} | "
            f"{result['ats'] or '-':<16} | "
            f"JOBS={result['jobs']:<5} | "
            f"{result['careers_url']}"
        )

    print()
    print("=== VERIFICATION COUNTS ===")

    for status, count in counts.most_common():
        print(
            f"{status:<32}",
            count,
        )


if __name__ == "__main__":
    main()
