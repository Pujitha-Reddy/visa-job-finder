from __future__ import annotations

import argparse

import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.database import get_connection


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


CAREER_HINTS = (
    "career",
    "careers",
    "jobs",
    "job-search",
    "join-us",
    "work-with-us",
    "opportunities",
)


def normalize_company(value: str) -> str:
    value = (value or "").lower()

    # Remove common legal/entity words.
    value = re.sub(
        r"\b("
        r"incorporated|corporation|corp|inc|llc|ltd|limited|"
        r"company|co|americas|usa|us"
        r")\b",
        " ",
        value,
    )

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(
        value.split()
    )


def domain_slug(name: str) -> str:
    """
    Conservative initial domain guess.

    Examples:
        Qualcomm -> qualcomm
        MathWorks -> mathworks
        ByteDance -> bytedance
    """
    text = normalize_company(name)

    return "".join(
        text.split()
    )


def candidate_homepages(name: str) -> list[str]:
    slug = domain_slug(name)

    if not slug:
        return []

    candidates = [
        f"https://www.{slug}.com",
        f"https://{slug}.com",
    ]

    return list(
        dict.fromkeys(candidates)
    )


def fetch(session, url):
    try:
        r = session.get(
            url,
            timeout=15,
            allow_redirects=True,
        )

        if r.status_code >= 400:
            return None

        return r

    except requests.RequestException:
        return None


def discover_career_links(
    html: str,
    base_url: str,
):
    soup = BeautifulSoup(
        html or "",
        "html.parser",
    )

    results = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        href = (
            anchor.get("href")
            or ""
        ).strip()

        text = " ".join(
            anchor.stripped_strings
        ).strip()

        blob = (
            href
            + " "
            + text
        ).lower()

        if not any(
            hint in blob
            for hint in CAREER_HINTS
        ):
            continue

        try:
            full = urljoin(
                base_url,
                href,
            )
        except Exception:
            continue

        if not full.startswith(
            ("http://", "https://")
        ):
            continue

        results.append(full)

    return list(
        dict.fromkeys(results)
    )


def score_careers_url(url: str) -> int:
    low = (url or "").lower()

    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.lower()
    except Exception:
        host = ""
        path = ""

    score = 0

    # ======================================================
    # Strong host signals
    # ======================================================

    if host.startswith("jobs."):
        score += 70

    if host.startswith("careers."):
        score += 65

    # ======================================================
    # Strong job-search/listing signals
    # ======================================================

    strong_positive = (
        "search-results",
        "search-jobs",
        "searchjobs",
        "job-search",
        "searchjobs",
        "/jobs",
        "/opportunities/search",
        "find-your-job",
        "searchjob",
    )

    for term in strong_positive:
        if term in low:
            score += 70

    # Careers landing pages are useful, but below actual
    # search/listing pages.
    if "/careers" in path:
        score += 30

    if "opportunities" in path:
        score += 25

    # ======================================================
    # Known ATS / recruiting-host signals
    # ======================================================

    if any(
        platform in low
        for platform in (
            "myworkdayjobs.com",
            "greenhouse.io",
            "lever.co",
            "eightfold.ai",
            "smartrecruiters.com",
            "ashbyhq.com",
            "phenompeople.com",
        )
    ):
        score += 80

    # ======================================================
    # Strong negative intent signals
    #
    # These may be careers-related but are NOT job feeds.
    # ======================================================

    negative = {
        "jointalentcommunity": -150,
        "talent-community": -150,
        "talentcommunity": -150,

        "/application": -140,
        "/apply": -120,

        "saved-jobs": -100,
        "jobcart": -100,

        "how-we-hire": -70,
        "how-we-work": -70,
        "our-culture": -70,
        "our-benefits": -70,

        "earlycareers": -50,
        "early-careers": -50,

        "faq": -60,
        "privacy": -100,
        "login": -100,
        "sign-in": -100,
        "signin": -100,
        "register": -100,
    }

    for term, penalty in negative.items():
        if term in low:
            score += penalty

    return score

def fallback_career_candidates(
    session,
    employer_name,
    homepage_urls,
):
    """
    Second-stage discovery when the corporate homepage
    does not expose a usable careers link.

    This is generic — no employer-specific mappings.
    """

    results = []

    # First derive domains from successfully resolved homepages.
    domains = set()

    for homepage in homepage_urls:
        r = fetch(
            session,
            homepage,
        )

        if not r:
            continue

        host = urlparse(
            r.url
        ).netloc.lower()

        if host.startswith("www."):
            host = host[4:]

        if host:
            domains.add(host)

    # Also retain the guessed company domain.
    slug = domain_slug(
        employer_name
    )

    if slug:
        domains.add(
            f"{slug}.com"
        )

    for domain in domains:

        probes = [
            f"https://careers.{domain}",
            f"https://jobs.{domain}",
            f"https://{domain}/careers",
            f"https://{domain}/jobs",
            f"https://www.{domain}/careers",
            f"https://www.{domain}/jobs",
        ]

        for probe in probes:

            r = fetch(
                session,
                probe,
            )

            if not r:
                continue

            final_url = r.url

            text = (
                r.text
                or ""
            ).lower()

            # Require actual career/job evidence.
            signals = sum(
                term in text
                for term in (
                    "search jobs",
                    "search careers",
                    "open positions",
                    "job opportunities",
                    "career opportunities",
                    "job search",
                    "careers",
                    "jobs",
                )
            )

            if signals < 2:
                continue

            results.append(
                final_url
            )

            # A careers page can itself expose the real
            # ATS/search surface.
            results.extend(
                discover_career_links(
                    r.text,
                    final_url,
                )
            )

    # Normalize/dedupe.
    unique = []

    seen = set()

    for url in results:

        parsed = urlparse(
            url
        )

        normalized = parsed._replace(
            fragment=""
        ).geturl()

        if normalized in seen:
            continue

        seen.add(
            normalized
        )

        unique.append(
            normalized
        )

    return unique

def verify_job_surface(
    session,
    url: str,
):
    """
    Determine whether URL is a real job search/listing surface,
    rather than merely a careers-related page.
    """

    r = fetch(
        session,
        url,
    )

    if not r:
        return None

    final_url = r.url
    html = r.text or ""
    low = html.lower()

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    score = score_careers_url(
        final_url
    )

    evidence = []

    # ======================================================
    # Job-search UI signals
    # ======================================================

    positive_terms = (
        "search jobs",
        "search for jobs",
        "job search",
        "open positions",
        "view jobs",
        "find jobs",
        "search opportunities",
        "job results",
        "search results",
    )

    for term in positive_terms:
        if term in low:
            score += 15
            evidence.append(
                f"text:{term}"
            )

    # ======================================================
    # Repeated job-like links
    # ======================================================

    job_links = []

    for a in soup.find_all(
        "a",
        href=True,
    ):
        href = (
            a.get("href")
            or ""
        ).strip()

        text = " ".join(
            a.stripped_strings
        ).strip()

        full = urljoin(
            final_url,
            href,
        )

        blob = (
            href
            + " "
            + text
        ).lower()

        if any(
            pattern in blob
            for pattern in (
                "/job/",
                "/jobs/",
                "jobid=",
                "job-id",
                "position/",
                "positions/",
            )
        ):
            job_links.append(full)

    unique_jobs = set(
        job_links
    )

    if len(unique_jobs) >= 3:
        score += 40
        evidence.append(
            f"job_links:{len(unique_jobs)}"
        )

    elif len(unique_jobs) >= 1:
        score += 10
        evidence.append(
            f"job_links:{len(unique_jobs)}"
        )

    # ======================================================
    # Structured JobPosting data
    # ======================================================

    if '"jobposting"' in low:
        score += 40
        evidence.append(
            "jsonld_jobposting"
        )

    # ======================================================
    # ATS fingerprints
    # ======================================================

    ats_terms = (
        "myworkdayjobs.com",
        "greenhouse",
        "lever.co",
        "eightfold",
        "phenom",
        "talentbrew",
        "smartrecruiters",
        "ashbyhq",
    )

    for term in ats_terms:
        if term in low:
            score += 25
            evidence.append(
                f"ats:{term}"
            )
            break

    # ======================================================
    # Page-purpose negatives
    # ======================================================

    negative_terms = (
        "join our talent community",
        "talent community",
        "submit application",
        "application status",
        "saved jobs",
        "sign in",
    )

    for term in negative_terms:
        if term in low:
            score -= 40
            evidence.append(
                f"negative:{term}"
            )

    return {
        "url": final_url,
        "score": score,
        "evidence": evidence,
        "job_links": len(
            unique_jobs
        ),
    }

def discover_for_employer(
    session,
    employer_name,
):
    print()
    print("=" * 100)
    print("EMPLOYER:", employer_name)

    candidates = []

    homepages = candidate_homepages(
        employer_name
    )

    # Stage 1:
    # Inspect corporate homepages for careers/job links.
    for homepage in homepages:
        r = fetch(
            session,
            homepage,
        )

        if not r:
            continue

        print(
            "HOME:",
            homepage,
            "=>",
            r.status_code,
            r.url,
        )

        links = discover_career_links(
            r.text,
            r.url,
        )

        for link in links:
            candidates.append(link)

    # Deduplicate after checking ALL homepages.
    candidates = list(
        dict.fromkeys(candidates)
    )

    # Stage 2:
    # If the corporate homepage exposed no careers links,
    # run generic fallback discovery.
    if not candidates:
        print(
            "PRIMARY DISCOVERY EMPTY "
            "- RUNNING FALLBACK"
        )

        candidates.extend(
            fallback_career_candidates(
                session,
                employer_name,
                homepages,
            )
        )

        candidates = list(
            dict.fromkeys(candidates)
        )

    # Rank discovered career surfaces.
    ranked = sorted(
        candidates,
        key=lambda url: (
            -score_careers_url(url),
            len(url),
        ),
    )

    if not ranked:
        print("CAREERS: NOT FOUND")
        return {
            "status": "NOT_FOUND",
            "url": None,
            "score": 0,
    }

    print(
        "CAREERS CANDIDATES:",
        len(ranked),
    )

    for url in ranked[:10]:
        print(
            f"{score_careers_url(url):>3}",
            "|",
            url,
        )

    # ======================================================
    # Verify and rank actual job-search surfaces
    # ======================================================
    verified = []

    for url in ranked:
        result = verify_job_surface(
            session,
            url,
        )

        if not result:
            continue

        verified.append(
            result
        )

    # ======================================================
    # Rank verified surfaces
    # ======================================================
    verified.sort(
        key=lambda x: (
            -x["score"],
            -x["job_links"],
            len(x["url"]),
        )
    )

    print()
    print("=== VERIFIED SURFACES ===")

    for item in verified[:5]:
        print(
            f"{item['score']:>4} | "
            f"JOBS={item['job_links']:<4} | "
            f"{item['url']}"
        )

        if item["evidence"]:
            print(
                "     ",
                ", ".join(
                    item["evidence"][:8]
                )
            )

    # ======================================================
    # Careers discovery result
    #
    # Finding the employer's hiring surface and proving
    # that we can collect jobs from it are separate stages.
    # ======================================================

    if verified:
        winner = verified[0]

        if winner["score"] >= 70:
            print(
                "CAREERS DISCOVERY: VERIFIED"
            )
            print(
                "CAREERS URL:",
                winner["url"],
            )

            return {
                "status": "VERIFIED",
                "url": winner["url"],
                "score": winner["score"],
            }

        print(
            "CAREERS DISCOVERY: "
            "DISCOVERED_UNVERIFIED"
        )
        print(
            "CAREERS URL:",
            winner["url"],
        )

        return {
            "status":
                "DISCOVERED_UNVERIFIED",
            "url":
                winner["url"],
            "score":
                winner["score"],
        }

    # No verified surface, but we still found a plausible
    # careers candidate. Preserve it for source discovery.
    if ranked:
        best_url = ranked[0]
        best_score = score_careers_url(
            best_url
        )

        print(
            "CAREERS DISCOVERY: "
            "DISCOVERED_UNVERIFIED"
        )
        print(
            "CAREERS URL:",
            best_url,
        )

        return {
            "status":
                "DISCOVERED_UNVERIFIED",
            "url":
                best_url,
            "score":
                best_score,
        }

    print(
        "CAREERS DISCOVERY: NOT_FOUND"
    )

    return {
        "status": "NOT_FOUND",
        "url": None,
        "score": 0,
    }



def parse_args():

    parser = argparse.ArgumentParser(
        description="Discover employer careers surfaces."
    )

    parser.add_argument(
        "--batch-name",
        default="SPONSOR_EXPANSION_V1",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help=(
            "Maximum number of employers to process "
            "during this invocation."
        ),
    )

    parser.add_argument(
        "--only-undiscovered",
        action="store_true",
        help=(
            "Only process pending employers that do not "
            "already have a careers discovery result."
        ),
    )

    return parser.parse_args()


def main():

    args = parse_args()

    session = requests.Session()
    session.headers.update(
        HEADERS
    )

    where_extra = ""

    if args.only_undiscovered:
        where_extra = """
          AND careers_discovery_status IS NULL
        """

    limit = max(
        1,
        int(args.limit),
    )

    with get_connection() as c:

        rows = c.execute(
            f"""
            SELECT
                id,
                display_name,
                source_discovery_score,
                careers_discovery_status,
                careers_candidate_url,
                careers_discovery_score
            FROM source_discovery_batches
            WHERE batch_name=?
              AND resolution_status='PENDING'
              {where_extra}
            ORDER BY
                source_discovery_score DESC,
                display_name
            LIMIT ?
            """,
            (
                args.batch_name,
                limit,
            ),
        ).fetchall()

    print(
        "EMPLOYERS SELECTED:",
        len(rows),
        "| limit=",
        limit,
        "| only_undiscovered=",
        args.only_undiscovered,
    )

    results = []

    for index, row in enumerate(
        rows,
        start=1,
    ):

        print()
        print(
            f"[{index}/{len(rows)}]",
            row["display_name"],
        )

        try:
            result = discover_for_employer(
                session,
                row["display_name"],
            )

        except Exception as exc:
            print(
                "[CAREERS DISCOVERY ERROR]",
                row["display_name"],
                "|",
                repr(exc),
            )

            result = {
                "status": "ERROR",
                "url": None,
                "score": 0,
            }

        if not result:
            result = {
                "status": "NOT_FOUND",
                "url": None,
                "score": 0,
            }

        stored = {
            "id": row["id"],
            "display_name":
                row["display_name"],
            "status":
                result["status"],
            "url":
                result["url"],
            "score":
                result["score"],
        }

        with get_connection() as c:

            c.execute(
                """
                UPDATE source_discovery_batches
                SET
                    careers_discovery_status=?,
                    careers_candidate_url=?,
                    careers_discovery_score=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (
                    stored["status"],
                    stored["url"],
                    stored["score"],
                    stored["id"],
                ),
            )

            c.commit()

        results.append(
            stored
        )

        print(
            "[PERSISTED]",
            stored["display_name"],
            "|",
            stored["status"],
            "| score=",
            stored["score"],
            "|",
            stored["url"] or "-",
        )

    print()
    print("=" * 100)
    print("CAREERS DISCOVERY STATE")
    print("=" * 100)

    counts = {}

    for result in results:

        status = result["status"]

        counts[status] = (
            counts.get(status, 0)
            + 1
        )

        print(
            f"{result['display_name']:<42} | "
            f"{status:<24} | "
            f"{result['score']:>6.1f} | "
            f"{result['url'] or '-'}"
        )

    print()
    print("=== COUNTS ===")

    for status, count in sorted(
        counts.items()
    ):

        print(
            f"{status:<24}",
            count,
        )

    print()
    print(
        "PROCESSED:",
        len(results),
    )


if __name__ == "__main__":
    main()
