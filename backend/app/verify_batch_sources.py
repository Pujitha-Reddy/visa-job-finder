from __future__ import annotations

from urllib.parse import urlparse

import requests

from app.database import get_connection
from app.collectors.common import title_matches


BATCH_NAME = "SPONSOR_EXPANSION_V1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def candidate_rows():
    with get_connection() as c:
        return [
            dict(r)
            for r in c.execute(
                """
                SELECT *
                FROM source_discovery_batches
                WHERE batch_name=?
                  AND resolution_status='ATS_CANDIDATE'
                  AND verification_status='UNVERIFIED'
                ORDER BY
                    source_discovery_score DESC,
                    combined_sponsor_score DESC
                """,
                (BATCH_NAME,),
            ).fetchall()
        ]


# ==========================================================
# Workday
# ==========================================================

def normalize_workday_url(url: str):
    parsed = urlparse(url or "")

    host = parsed.netloc

    parts = [
        p
        for p in parsed.path.split("/")
        if p
    ]

    if (
        not host
        or "myworkdayjobs.com" not in host
        or not parts
    ):
        raise RuntimeError(
            f"Invalid Workday URL: {url}"
        )

    site = parts[0]
    tenant = host.split(".")[0]

    careers_url = (
        f"https://{host}/{site}"
    )

    endpoint = (
        f"https://{host}"
        f"/wday/cxs/{tenant}/{site}/jobs"
    )

    return {
        "host": host,
        "tenant": tenant,
        "site": site,
        "careers_url": careers_url,
        "endpoint": endpoint,
    }


def workday_search(endpoint: str, search_text: str):
    r = requests.post(
        endpoint,
        headers={
            **HEADERS,
            "Content-Type": "application/json",
        },
        json={
            "appliedFacets": {},
            "limit": 20,
            "offset": 0,
            "searchText": search_text,
        },
        timeout=30,
    )

    result = {
        "status": r.status_code,
        "content_type": r.headers.get(
            "content-type",
            "",
        ),
        "total": 0,
        "rows": 0,
    }

    if not r.ok:
        return result

    try:
        payload = r.json()
    except Exception:
        return result

    postings = (
        payload.get("jobPostings")
        or []
    )

    result["total"] = int(
        payload.get("total")
        or len(postings)
    )

    result["rows"] = len(postings)

    return result


def verify_workday(row):
    info = normalize_workday_url(
        row["discovered_careers_url"]
    )

    # First prove the source has an active inventory.
    all_jobs = workday_search(
        info["endpoint"],
        "",
    )

    # Then separately see whether software jobs exist.
    software = workday_search(
        info["endpoint"],
        "software engineer",
    )

    verified = (
        all_jobs["status"] == 200
        and "json" in all_jobs["content_type"].lower()
        and all_jobs["total"] > 0
    )

    return {
        "verified": verified,
        "ats": "WORKDAY",
        "careers_url": info["careers_url"],
        "token": None,
        "all_jobs": all_jobs["total"],
        "software_jobs": software["total"],
        "endpoint_status": all_jobs["status"],
        "notes": (
            "Verified Workday CXS source. "
            f"Host={info['host']}; "
            f"tenant={info['tenant']}; "
            f"site={info['site']}; "
            f"all_jobs={all_jobs['total']}; "
            f"software_search={software['total']}."
        ),
    }


# ==========================================================
# Lever
# ==========================================================

def normalize_lever(url: str):
    parsed = urlparse(url or "")

    if parsed.netloc.lower() != "jobs.lever.co":
        raise RuntimeError(
            f"Invalid Lever URL: {url}"
        )

    parts = [
        p
        for p in parsed.path.split("/")
        if p
    ]

    if not parts:
        raise RuntimeError(
            f"Lever token missing: {url}"
        )

    token = parts[0]

    return {
        "token": token,
        "careers_url": (
            f"https://jobs.lever.co/{token}"
        ),
        "api_url": (
            f"https://api.lever.co/v0/postings/"
            f"{token}?mode=json"
        ),
    }


def verify_lever(row):
    info = normalize_lever(
        row["discovered_careers_url"]
    )

    r = requests.get(
        info["api_url"],
        headers=HEADERS,
        timeout=30,
    )

    total = 0
    software_jobs = 0
    valid_json = False

    if r.ok:
        try:
            payload = r.json()

            if isinstance(payload, list):
                valid_json = True
                total = len(payload)

                software_jobs = sum(
                    1
                    for job in payload
                    if title_matches(
                        str(
                            job.get("text")
                            or ""
                        )
                    )
                )

        except Exception:
            pass

    verified = (
        r.status_code == 200
        and valid_json
        and total > 0
    )

    return {
        "verified": verified,
        "ats": "LEVER",
        "careers_url": info["careers_url"],
        "token": info["token"],
        "all_jobs": total,
        "software_jobs": software_jobs,
        "endpoint_status": r.status_code,
        "notes": (
            "Verified Lever public postings API. "
            f"token={info['token']}; "
            f"all_jobs={total}; "
            f"software_titles={software_jobs}."
        ),
    }

# ==========================================================
# Greenhouse
# ==========================================================

def normalize_greenhouse(url: str):
    parsed = urlparse(url or "")

    host = parsed.netloc.lower()

    if host not in {
        "job-boards.greenhouse.io",
        "boards.greenhouse.io",
    }:
        raise RuntimeError(
            f"Invalid Greenhouse URL: {url}"
        )

    parts = [
        p
        for p in parsed.path.split("/")
        if p
    ]

    if not parts:
        raise RuntimeError(
            f"Greenhouse board token missing: {url}"
        )

    token = parts[0]

    return {
        "token": token,
        "careers_url": (
            f"https://job-boards.greenhouse.io/{token}"
        ),
        "api_url": (
            f"https://boards-api.greenhouse.io/"
            f"v1/boards/{token}/jobs"
        ),
    }


def verify_greenhouse(row):
    info = normalize_greenhouse(
        row["discovered_careers_url"]
    )

    r = requests.get(
        info["api_url"],
        headers=HEADERS,
        timeout=30,
    )

    total = 0
    software_jobs = 0
    valid_json = False

    if r.ok:
        try:
            payload = r.json()

            jobs = (
                payload.get("jobs")
                or []
            )

            valid_json = isinstance(
                jobs,
                list,
            )

            total = len(jobs)

            software_jobs = sum(
                1
                for job in jobs
                if title_matches(
                    str(
                        job.get("title")
                        or ""
                    )
                )
            )

        except Exception:
            pass

    verified = (
        r.status_code == 200
        and valid_json
        and total > 0
    )

    return {
        "verified": verified,
        "ats": "GREENHOUSE",
        "careers_url": info["careers_url"],
        "token": info["token"],
        "all_jobs": total,
        "software_jobs": software_jobs,
        "endpoint_status": r.status_code,
        "notes": (
            "Verified Greenhouse public jobs API. "
            f"token={info['token']}; "
            f"all_jobs={total}; "
            f"software_titles={software_jobs}."
        ),
    }

# ==========================================================
# Persistence
# ==========================================================

def persist_success(row, result):
    with get_connection() as c:
        c.execute(
            """
            UPDATE source_discovery_batches
            SET
                resolution_status='RESOLVED',
                discovered_careers_url=?,
                discovered_ats=?,
                discovered_token=?,
                verification_status='VERIFIED',
                notes=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                result["careers_url"],
                result["ats"],
                result["token"],
                result["notes"],
                row["id"],
            ),
        )

        c.commit()


def persist_failure(row, message):
    # Keep the row as ATS_CANDIDATE.
    # A failed verification must never become VERIFIED.
    with get_connection() as c:
        c.execute(
            """
            UPDATE source_discovery_batches
            SET
                notes=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (
                message,
                row["id"],
            ),
        )

        c.commit()


# ==========================================================
# Main
# ==========================================================

def main():
    rows = candidate_rows()

    print(
        "ATS CANDIDATES:",
        len(rows),
    )

    for row in rows:
        name = row["display_name"]
        ats = (
            row["discovered_ats"]
            or ""
        ).upper()

        print()
        print("=" * 100)
        print("COMPANY:", name)
        print("ATS:", ats)
        print(
            "DISCOVERED URL:",
            row["discovered_careers_url"],
        )

        try:
            if ats == "WORKDAY":
                result = verify_workday(
                    row
                )

            elif ats == "LEVER":
                result = verify_lever(
                    row
                )

            elif ats == "GREENHOUSE":
                result = verify_greenhouse(
                    row
                )
            else:
                print(
                    "NO VERIFIER IMPLEMENTED:",
                    ats,
                )
                continue

        except Exception as exc:
            print(
                "VERIFICATION ERROR:",
                exc,
            )

            persist_failure(
                row,
                f"Verification error: {exc}",
            )

            continue

        print(
            "VERIFIED:",
            result["verified"],
        )
        print(
            "STATUS:",
            result["endpoint_status"],
        )
        print(
            "CAREERS:",
            result["careers_url"],
        )
        print(
            "TOKEN:",
            result["token"],
        )
        print(
            "ALL JOBS:",
            result["all_jobs"],
        )
        print(
            "SOFTWARE JOBS:",
            result["software_jobs"],
        )

        if result["verified"]:
            persist_success(
                row,
                result,
            )

            print(
                "RESULT: VERIFIED"
            )

        else:
            persist_failure(
                row,
                (
                    f"ATS verification failed. "
                    f"HTTP={result['endpoint_status']}; "
                    f"all_jobs={result['all_jobs']}."
                ),
            )

            print(
                "RESULT: NOT VERIFIED"
            )


if __name__ == "__main__":
    main()