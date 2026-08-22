from __future__ import annotations

import argparse

from datetime import datetime, timezone

from app.database import get_connection
from app.collectors.generic_jobs import GenericJobCollector

MIN_JOBS = 3
AUTO_PROMOTE_SCORE = 80


def score_probe(
    discovery_score,
    jobs,
):
    score = 0

    job_count = len(jobs)

    if discovery_score >= 70:
        score += 20

    if job_count >= 3:
        score += 20

    if job_count >= 10:
        score += 20

    if job_count >= 20:
        score += 10

    valid_urls = sum(1 for job in jobs if job.get("source_url"))

    valid_titles = sum(1 for job in jobs if job.get("title"))

    if job_count:
        if valid_urls / job_count >= 0.95:
            score += 15

        if valid_titles / job_count >= 0.95:
            score += 15

    return score


def employer_exists(
    conn,
    display_name,
):
    return conn.execute(
        """
        SELECT id
        FROM employers
        WHERE lower(display_name)=lower(?)
        LIMIT 1
        """,
        (display_name,),
    ).fetchone()


def source_exists(
    conn,
    employer_id,
    careers_url,
):
    return conn.execute(
        """
        SELECT id
        FROM employer_sources
        WHERE employer_id=?
          AND careers_url=?
        LIMIT 1
        """,
        (
            employer_id,
            careers_url,
        ),
    ).fetchone()


def insert_employer(
    conn,
    display_name,
    careers_url,
):
    now = datetime.now(timezone.utc).isoformat()

    cur = conn.execute(
        """
        INSERT INTO employers (
            canonical_name,
            display_name,
            source_type,
            website,
            careers_url,
            enabled,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            display_name.lower(),
            display_name,
            "DIRECT_EMPLOYER",
            None,
            careers_url,
            1,
            now,
            now,
        ),
    )

    return cur.lastrowid


def insert_source(
    conn,
    employer_id,
    careers_url,
    raw_jobs,
):
    now = datetime.now(timezone.utc).isoformat()

    notes = (
        "Auto-promoted generic source. "
        f"GenericJobCollector returned "
        f"{raw_jobs} valid job records."
    )

    cur = conn.execute(
        """
        INSERT INTO employer_sources (
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            employer_id,
            "GENERIC",
            None,
            careers_url,
            1,
            now,
            now,
            raw_jobs,
            1,
            notes,
        ),
    )

    return cur.lastrowid


def mark_batch_promoted(
    conn,
    batch_id,
    careers_url,
    raw_jobs,
    collection_score,
):
    notes = (
        "Auto-promoted via generic collector. "
        f"raw_jobs={raw_jobs}; "
        f"collection_score={collection_score}."
    )

    conn.execute(
        """
        UPDATE source_discovery_batches
        SET
            resolution_status='PROMOTED',
            verification_status='VERIFIED',
            discovered_ats='GENERIC',
            discovered_careers_url=?,
            discovered_token=NULL,
            notes=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
        """,
        (
            careers_url,
            notes,
            batch_id,
        ),
    )



def parse_args():
    parser = argparse.ArgumentParser(
        description="Run this pipeline for a specific source-discovery batch."
    )

    parser.add_argument(
        "--batch-name",
        default="SPONSOR_EXPANSION_V1",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    collector = GenericJobCollector()

    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                id,
                display_name,
                careers_discovery_score,
                discovered_careers_url
            FROM source_discovery_batches
            WHERE batch_name=?
              AND resolution_status='PENDING'

              -- Only consume rows that the verification
              -- stage explicitly routed to GENERIC.
              AND discovered_ats IS NULL
              AND discovered_careers_url IS NOT NULL
              AND notes='Generic job-list verification required.'

            ORDER BY
                source_discovery_score DESC,
                display_name
            """, (args.batch_name,)).fetchall()

        print(
            "AUTO PROMOTION TARGETS:",
            len(rows),
        )

        promoted = []
        skipped = []

        for row in rows:
            name = row["display_name"]
            url = row["discovered_careers_url"]
            discovery_score = row["careers_discovery_score"] or 0

            print()
            print("=" * 100)
            print("EMPLOYER:", name)
            print("CAREERS:", url)

            try:
                jobs = collector.fetch(
                    {
                        "employer_name": name,
                        "careers_url": url,
                    }
                )

            except Exception as exc:
                print(
                    "SKIP: collector error:",
                    repr(exc),
                )

                skipped.append(
                    (
                        name,
                        "COLLECTOR_ERROR",
                    )
                )

                continue

            collection_score = score_probe(
                discovery_score,
                jobs,
            )

            print(
                "RAW JOBS:",
                len(jobs),
            )
            print(
                "COLLECTION SCORE:",
                collection_score,
            )

            if len(jobs) < MIN_JOBS or collection_score < AUTO_PROMOTE_SCORE:
                print("SKIP: below promotion threshold")

                skipped.append(
                    (
                        name,
                        "BELOW_THRESHOLD",
                    )
                )

                continue

            existing_employer = employer_exists(
                conn,
                name,
            )

            if existing_employer:
                employer_id = existing_employer["id"]

                print(
                    "EMPLOYER EXISTS:",
                    employer_id,
                )

            else:
                employer_id = insert_employer(
                    conn,
                    name,
                    url,
                )

                print(
                    "INSERTED EMPLOYER:",
                    employer_id,
                )

            existing_source = source_exists(
                conn,
                employer_id,
                url,
            )

            if existing_source:
                source_id = existing_source["id"]

                print(
                    "SOURCE EXISTS:",
                    source_id,
                )

            else:
                source_id = insert_source(
                    conn,
                    employer_id,
                    url,
                    len(jobs),
                )

                print(
                    "INSERTED SOURCE:",
                    source_id,
                )

            mark_batch_promoted(
                conn,
                row["id"],
                url,
                len(jobs),
                collection_score,
            )

            promoted.append(
                {
                    "name": name,
                    "employer_id": employer_id,
                    "source_id": source_id,
                    "jobs": len(jobs),
                    "score": collection_score,
                }
            )

        conn.commit()

    print()
    print("=" * 100)
    print("AUTO PROMOTION SUMMARY")
    print("=" * 100)

    for item in promoted:
        print(
            f"PROMOTED | "
            f"{item['score']:>3} | "
            f"JOBS={item['jobs']:<4} | "
            f"{item['name']} | "
            f"EMPLOYER={item['employer_id']} | "
            f"SOURCE={item['source_id']}"
        )

    print()
    print(
        "PROMOTED:",
        len(promoted),
    )
    print(
        "SKIPPED:",
        len(skipped),
    )


if __name__ == "__main__":
    main()
