from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.ingestion.models import JobObservation


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; "
        "VisaJobFinder/1.0; "
        "+structured-job-discovery)"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,*/*;q=0.8"
    ),
}


JOB_URL_HINTS = (
    "/job/",
    "/jobs/",
    "/jobdetail/",
    "/job-detail/",
    "/positions/",
    "/position/",
    "/careers/job/",
    "/opportunities/",
)


NON_JOB_HINTS = (
    "/privacy",
    "/benefits",
    "/culture",
    "/login",
    "/signin",
    "/talent-community",
    "/job-alert",
    "/saved-jobs",
    "/faq",
    "/terms",
)


@dataclass
class StructuredWebResult:
    observations: list[JobObservation]
    pages_fetched: int
    jsonld_jobs: int
    sitemap_urls: int
    detail_urls: int
    errors: list[str]


def clean_text(value):
    if value is None:
        return None

    soup = BeautifulSoup(
        str(value),
        "html.parser",
    )

    text = soup.get_text(
        " ",
        strip=True,
    )

    return re.sub(
        r"\s+",
        " ",
        unescape(text),
    ).strip()


def domain(url):
    try:
        return urlparse(url).hostname
    except Exception:
        return None


def absolute_url(base, value):
    if not value:
        return None

    try:
        return urljoin(
            base,
            value,
        )
    except Exception:
        return value


def looks_like_job_url(url):
    value = (
        url
        or ""
    ).lower()

    if any(
        bad in value
        for bad in NON_JOB_HINTS
    ):
        return False

    return any(
        hint in value
        for hint in JOB_URL_HINTS
    )


def iter_jsonld_objects(value):
    if isinstance(value, list):
        for item in value:
            yield from iter_jsonld_objects(
                item
            )
        return

    if not isinstance(
        value,
        dict,
    ):
        return

    graph = value.get("@graph")

    if isinstance(graph, list):
        for item in graph:
            yield from iter_jsonld_objects(
                item
            )

    yield value


def is_jobposting(obj):
    type_value = obj.get("@type")

    if isinstance(
        type_value,
        list,
    ):
        values = {
            str(v).lower()
            for v in type_value
        }

        return (
            "jobposting"
            in values
        )

    return (
        str(type_value).lower()
        == "jobposting"
    )


def extract_company(obj):
    hiring = obj.get(
        "hiringOrganization"
    )

    if isinstance(
        hiring,
        dict,
    ):
        return hiring.get(
            "name"
        )

    return None


def extract_location(obj):
    value = obj.get(
        "jobLocation"
    )

    if isinstance(value, list):
        locations = []

        for item in value:
            loc = extract_location(
                {
                    "jobLocation": item
                }
            )

            if loc:
                locations.append(
                    loc
                )

        return " | ".join(
            locations
        ) or None

    if not isinstance(
        value,
        dict,
    ):
        return None

    address = value.get(
        "address"
    )

    if not isinstance(
        address,
        dict,
    ):
        return clean_text(
            value.get("name")
        )

    parts = []

    for key in (
        "addressLocality",
        "addressRegion",
        "postalCode",
        "addressCountry",
    ):
        val = address.get(key)

        if isinstance(
            val,
            dict,
        ):
            val = (
                val.get("name")
                or val.get("@id")
            )

        if val:
            parts.append(
                str(val)
            )

    return ", ".join(
        parts
    ) or None


def jsonld_to_observation(
    obj,
    *,
    page_url,
    default_company,
    provider_source_id=None,
):
    title = clean_text(
        obj.get("title")
        or obj.get("name")
    )

    company = clean_text(
        extract_company(obj)
        or default_company
    )

    if not title or not company:
        return None

    identifier = obj.get(
        "identifier"
    )

    provider_job_id = None

    if isinstance(
        identifier,
        dict,
    ):
        provider_job_id = (
            identifier.get("value")
            or identifier.get("@id")
        )

    elif identifier:
        provider_job_id = str(
            identifier
        )

    apply_url = (
        obj.get("url")
        or page_url
    )

    return JobObservation(
        provider="STRUCTURED_WEB",

        provider_source_id=(
            provider_source_id
        ),

        provider_job_id=(
            str(provider_job_id)
            if provider_job_id
            is not None
            else None
        ),

        source_type=(
            "DIRECT_EMPLOYER"
        ),

        transport_type=(
            "JSON_LD"
        ),

        source_url=page_url,

        apply_url=absolute_url(
            page_url,
            apply_url,
        ),

        company_name_raw=company,

        company_domain=domain(
            page_url
        ),

        title_raw=title,

        location_raw=(
            extract_location(obj)
        ),

        description_raw=clean_text(
            obj.get("description")
        ),

        posted_at=(
            obj.get("datePosted")
        ),

        source_confidence_score=90,

        raw_payload=obj,
    )


def parse_jsonld_jobs(
    html,
    *,
    page_url,
    default_company,
    provider_source_id=None,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    observations = []

    for script in soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json"
        },
    ):
        raw = script.string

        if not raw:
            raw = script.get_text(
                strip=True
            )

        if not raw:
            continue

        try:
            payload = json.loads(
                raw
            )
        except Exception:
            continue

        for obj in iter_jsonld_objects(
            payload
        ):
            if not is_jobposting(
                obj
            ):
                continue

            observation = (
                jsonld_to_observation(
                    obj,
                    page_url=page_url,
                    default_company=(
                        default_company
                    ),
                    provider_source_id=(
                        provider_source_id
                    ),
                )
            )

            if observation:
                observations.append(
                    observation
                )

    return observations


def extract_detail_links(
    html,
    page_url,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    found = set()

    host = domain(
        page_url
    )

    for a in soup.find_all(
        "a",
        href=True,
    ):
        url = absolute_url(
            page_url,
            a.get("href"),
        )

        if not url:
            continue

        if (
            host
            and domain(url)
            and domain(url) != host
        ):
            continue

        if looks_like_job_url(
            url
        ):
            found.add(url)

    return sorted(found)


def fetch_sitemap_urls(
    session,
    seed_url,
    *,
    max_sitemaps=10,
    max_urls=500,
):
    parsed = urlparse(
        seed_url
    )

    if not parsed.scheme or not parsed.netloc:
        return []

    root = (
        f"{parsed.scheme}://"
        f"{parsed.netloc}"
    )

    queue = [
        root + "/sitemap.xml",
        root + "/sitemap_index.xml",
    ]

    seen_sitemaps = set()
    job_urls = set()

    while (
        queue
        and len(
            seen_sitemaps
        ) < max_sitemaps
        and len(
            job_urls
        ) < max_urls
    ):
        sitemap = queue.pop(0)

        if sitemap in seen_sitemaps:
            continue

        seen_sitemaps.add(
            sitemap
        )

        try:
            r = session.get(
                sitemap,
                timeout=15,
            )

            if not r.ok:
                continue

        except Exception:
            continue

        content = r.text

        try:
            soup = BeautifulSoup(
                content,
                "xml",
            )
        except Exception:
            continue

        for loc in soup.find_all(
            "loc"
        ):
            value = loc.get_text(
                strip=True
            )

            if not value:
                continue

            lower = value.lower()

            if (
                lower.endswith(
                    ".xml"
                )
                or "sitemap"
                in lower
            ):
                if (
                    value
                    not in seen_sitemaps
                ):
                    queue.append(
                        value
                    )

                continue

            if looks_like_job_url(
                value
            ):
                job_urls.add(
                    value
                )

            if len(
                job_urls
            ) >= max_urls:
                break

    return sorted(
        job_urls
    )


def collect_structured_web(
    *,
    employer_name,
    seed_url,
    provider_source_id=None,
    max_detail_pages=100,
):
    session = requests.Session()

    session.headers.update(
        HEADERS
    )

    observations = []

    errors = []

    pages_fetched = 0
    jsonld_jobs = 0

    detail_urls = set()

    # ======================================================
    # Seed page
    # ======================================================

    try:
        r = session.get(
            seed_url,
            timeout=20,
        )

        r.raise_for_status()

        pages_fetched += 1

        final_url = r.url

        seed_jobs = parse_jsonld_jobs(
            r.text,
            page_url=final_url,
            default_company=(
                employer_name
            ),
            provider_source_id=(
                provider_source_id
            ),
        )

        observations.extend(
            seed_jobs
        )

        jsonld_jobs += len(
            seed_jobs
        )

        detail_urls.update(
            extract_detail_links(
                r.text,
                final_url,
            )
        )

    except Exception as exc:
        errors.append(
            f"seed:{repr(exc)}"
        )

        final_url = seed_url

    # ======================================================
    # Sitemap discovery
    # ======================================================

    sitemap_urls = (
        fetch_sitemap_urls(
            session,
            final_url,
        )
    )

    detail_urls.update(
        sitemap_urls
    )

    # ======================================================
    # Detail pages
    # ======================================================

    for url in list(
        detail_urls
    )[:max_detail_pages]:

        try:
            r = session.get(
                url,
                timeout=15,
            )

            r.raise_for_status()

            pages_fetched += 1

            jobs = parse_jsonld_jobs(
                r.text,
                page_url=r.url,
                default_company=(
                    employer_name
                ),
                provider_source_id=(
                    provider_source_id
                ),
            )

            observations.extend(
                jobs
            )

            jsonld_jobs += len(
                jobs
            )

        except Exception as exc:
            errors.append(
                f"{url}:{repr(exc)}"
            )

    # ======================================================
    # Dedupe inside this provider batch
    # ======================================================

    unique = {}

    for job in observations:
        key = (
            job.provider_job_id
            or job.apply_url
            or job.source_url
        )

        if key and key not in unique:
            unique[key] = job

    return StructuredWebResult(
        observations=list(
            unique.values()
        ),

        pages_fetched=(
            pages_fetched
        ),

        jsonld_jobs=(
            jsonld_jobs
        ),

        sitemap_urls=len(
            sitemap_urls
        ),

        detail_urls=len(
            detail_urls
        ),

        errors=errors,
    )
