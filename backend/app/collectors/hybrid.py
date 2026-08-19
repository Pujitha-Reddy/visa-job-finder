from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches
from .hybrid_config import HYBRID_CONFIGS


def dot_get(data, path, default=None):
    if not path:
        return data

    current = data

    for piece in path.split("."):
        if not isinstance(current, dict):
            return default

        current = current.get(piece)

        if current is None:
            return default

    return current


class HybridCollector(BaseCollector):
    """
    Configuration-driven collector for employers that do not fit one
    of the standard public ATS collectors.

    Current supported strategy:

        HTML_LINKS discovery
              ↓
        baseline metadata
              ↓
        optional JSON_API detail enrichment
              ↓
        fallback to baseline if detail is unavailable/blocked

    The design intentionally separates discovery from enrichment.

    A detail failure MUST NOT automatically mean source failure.
    """

    ats_name = "HYBRID"

    def __init__(self):
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })

    # ---------------------------------------------------------
    # PUBLIC ENTRYPOINT
    # ---------------------------------------------------------

    def fetch(self, source: dict) -> list[dict]:
        employer = source.get("employer_name")

        config = HYBRID_CONFIGS.get(employer)

        if not config:
            raise RuntimeError(
                f"No HYBRID configuration for {employer}"
            )

        discovery = config.get("discovery") or {}

        discovery_type = discovery.get("type")

        if discovery_type == "HTML_LINKS":
            jobs = self._discover_html_links(
                source,
                discovery,
            )
        else:
            raise RuntimeError(
                f"Unsupported HYBRID discovery strategy: "
                f"{discovery_type}"
            )

        print(
            f"{employer} hybrid discovery: "
            f"{len(jobs)} software jobs"
        )

        detail = config.get("detail")

        if detail:
            jobs = self._enrich_jobs(
                jobs,
                detail,
                employer,
            )

        # Remove private implementation metadata.
        for job in jobs:
            for key in list(job):
                if key.startswith("_hybrid_"):
                    job.pop(key, None)

        # URL dedupe.
        unique = {}

        for job in jobs:
            url = job.get("source_url")

            if url:
                unique[url] = job

        return list(unique.values())

    # ---------------------------------------------------------
    # HTML DISCOVERY
    # ---------------------------------------------------------

    def _discover_html_links(
        self,
        source: dict,
        config: dict,
    ) -> list[dict]:

        base_url = config["url"]

        max_pages = int(
            config.get("max_pages") or 1
        )

        link_contains = (
            config.get("link_contains")
            or ""
        )

        found = {}

        for page in range(1, max_pages + 1):
            params = {}

            for key, value in (
                config.get("params") or {}
            ).items():
                if isinstance(value, str):
                    value = value.replace(
                        "{page}",
                        str(page),
                    )

                params[key] = value

            response = self.session.get(
                base_url,
                params=params,
                timeout=30,
                headers={
                    "Accept": (
                        "text/html,"
                        "application/xhtml+xml"
                    ),
                },
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            page_roles = 0
            page_software = 0

            for anchor in soup.find_all(
                "a",
                href=True,
            ):
                href = anchor.get("href") or ""

                if (
                    link_contains
                    and link_contains not in href
                ):
                    continue

                url = urljoin(
                    base_url,
                    href,
                )

                ids = self._extract_ids(
                    url,
                    config,
                )

                if not ids:
                    continue

                page_roles += 1

                title = anchor.get_text(
                    " ",
                    strip=True,
                )

                if not title:
                    continue

                # Critical:
                # filter before any expensive enrichment.
                if not title_matches(title):
                    continue

                page_software += 1

                container = self._find_container(
                    anchor,
                    config.get(
                        "container_markers"
                    ) or [],
                )

                text = (
                    container.get_text(
                        " ",
                        strip=True,
                    )
                    if container is not None
                    else title
                )

                location = self._extract_first(
                    text,
                    config.get(
                        "location_patterns"
                    ) or [],
                )

                published = self._extract_date(
                    text,
                    config,
                )

                excerpt = re.sub(
                    r"\s+",
                    " ",
                    text,
                ).strip()

                excerpt_limit = int(
                    config.get(
                        "excerpt_limit"
                    )
                    or 8000
                )

                excerpt = excerpt[
                    :excerpt_limit
                ]

                found[url] = {
                    "external_id": ids[
                        "external_id"
                    ],
                    "source": "HYBRID",
                    "source_url": url,
                    "apply_url": url,

                    "company_name_raw": source[
                        "employer_name"
                    ],

                    "source_type": source.get(
                        "source_type",
                        "DIRECT_EMPLOYER",
                    ),

                    "ats": "HYBRID",

                    "title": title,
                    "description": excerpt,
                    "location_raw": location,
                    "country": config.get("fixed_country"),

                    "posted_at": published,
                    "source_published_at": published,

                    "freshness_confidence": (
                        "HIGH"
                        if published
                        else "UNKNOWN"
                    ),

                    "freshness_source": (
                        "HYBRID_DISCOVERY"
                        if published
                        else "UNKNOWN"
                    ),

                    "_hybrid_id": ids["id"],
                }

            print(
                f"{source['employer_name']} "
                f"page {page}: "
                f"{page_roles} roles / "
                f"{page_software} software"
            )

            if page_roles == 0:
                break

        return list(found.values())

    @staticmethod
    def _find_container(
        anchor,
        markers,
    ):
        node = anchor

        for _ in range(10):
            node = node.parent

            if node is None:
                break

            try:
                text = node.get_text(
                    " ",
                    strip=True,
                )
            except Exception:
                continue

            if markers and all(
                marker in text
                for marker in markers
            ):
                return node

        return anchor.parent

    @staticmethod
    def _extract_ids(
        url,
        config,
    ):
        id_regex = config.get(
            "id_regex"
        )

        if not id_regex:
            return None

        match = re.search(
            id_regex,
            url,
            flags=re.I,
        )

        if not match:
            return None

        internal_id = match.group(1)

        external_id = internal_id

        external_regex = config.get(
            "external_id_regex"
        )

        if external_regex:
            ext_match = re.search(
                external_regex,
                url,
                flags=re.I,
            )

            if ext_match:
                external_id = ext_match.group(1)

        return {
            "id": internal_id,
            "external_id": external_id,
        }

    @staticmethod
    def _extract_first(
        text,
        patterns,
    ):
        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.I,
            )

            if match:
                return re.sub(
                    r"\s+",
                    " ",
                    match.group(1),
                ).strip()

        return ""

    @staticmethod
    def _extract_date(
        text,
        config,
    ):
        date_regex = config.get(
            "date_regex"
        )

        if not date_regex:
            return None

        match = re.search(
            date_regex,
            text,
        )

        if not match:
            return None

        value = match.group(0)

        fmt = config.get(
            "date_format"
        )

        if not fmt:
            return value

        try:
            parsed = datetime.strptime(
                value,
                fmt,
            )

            return parsed.replace(
                tzinfo=timezone.utc,
            ).isoformat()

        except ValueError:
            return value

    # ---------------------------------------------------------
    # OPTIONAL ENRICHMENT
    # ---------------------------------------------------------

    def _enrich_jobs(
        self,
        jobs,
        config,
        employer,
    ):
        detail_type = config.get(
            "type"
        )

        if detail_type != "JSON_API":
            raise RuntimeError(
                f"Unsupported HYBRID detail strategy: "
                f"{detail_type}"
            )

        blocked = False

        output = []

        delay = float(
            config.get(
                "delay_seconds"
            )
            or 0
        )

        blocked_statuses = set(
            config.get(
                "blocked_statuses"
            )
            or []
        )

        for index, baseline in enumerate(jobs):
            job = dict(baseline)

            if blocked:
                output.append(job)
                continue

            raw_id = job.get(
                "_hybrid_id"
            )

            if not raw_id:
                output.append(job)
                continue

            template = config.get(
                "job_id_template",
                "{id}",
            )

            job_id = template.replace(
                "{id}",
                str(raw_id),
            )

            if index and delay:
                time.sleep(delay)

            try:
                detail = self._fetch_json_detail(
                    config,
                    job_id,
                )

                if detail:
                    job = self._merge_detail(
                        job,
                        detail,
                        config,
                    )

            except requests.HTTPError as exc:
                status = (
                    exc.response.status_code
                    if exc.response is not None
                    else None
                )

                if status in blocked_statuses:
                    print(
                        f"[{employer}] "
                        "Detail enrichment blocked "
                        f"(HTTP {status}). "
                        "Using discovery metadata "
                        "for remainder of run."
                    )

                    blocked = True

                else:
                    print(
                        f"[{employer} DETAIL ERROR] "
                        f"{job_id}: {exc}"
                    )

            except Exception as exc:
                print(
                    f"[{employer} DETAIL ERROR] "
                    f"{job_id}: {exc}"
                )

            output.append(job)

        return output

    def _fetch_json_detail(
        self,
        config,
        job_id,
    ):
        url = config["url"].replace(
            "{job_id}",
            job_id,
        )

        method = (
            config.get("method")
            or "GET"
        ).upper()

        if method == "GET":
            response = self.session.get(
                url,
                timeout=30,
                headers={
                    "Accept": (
                        "application/json"
                    ),
                },
            )
        else:
            raise RuntimeError(
                f"Unsupported JSON detail "
                f"method: {method}"
            )

        response.raise_for_status()

        payload = response.json()

        root_path = config.get(
            "root_path"
        )

        detail = dot_get(
            payload,
            root_path,
            payload,
        )

        if not isinstance(
            detail,
            dict,
        ):
            return None

        return detail

    # ---------------------------------------------------------
    # DETAIL NORMALIZATION
    # ---------------------------------------------------------

    def _merge_detail(
        self,
        baseline,
        detail,
        config,
    ):
        job = dict(baseline)

        title_path = config.get(
            "title_path"
        )

        if title_path:
            title = dot_get(
                detail,
                title_path,
            )

            if isinstance(
                title,
                str,
            ) and title.strip():
                job["title"] = title.strip()

        for path in (
            config.get(
                "external_id_paths"
            )
            or []
        ):
            value = dot_get(
                detail,
                path,
            )

            if value:
                job[
                    "external_id"
                ] = value
                break

        for path in (
            config.get(
                "published_paths"
            )
            or []
        ):
            value = dot_get(
                detail,
                path,
            )

            if value:
                job["posted_at"] = value
                job[
                    "source_published_at"
                ] = value

                job[
                    "freshness_confidence"
                ] = "HIGH"

                job[
                    "freshness_source"
                ] = "HYBRID_JSON_DETAIL"

                break

        description_parts = []

        for path in (
            config.get(
                "description_paths"
            )
            or []
        ):
            value = dot_get(
                detail,
                path,
            )

            if (
                isinstance(value, str)
                and value.strip()
                and value.strip()
                not in description_parts
            ):
                description_parts.append(
                    value.strip()
                )

        if description_parts:
            job["description"] = (
                "\n\n".join(
                    description_parts
                )
            )

        location = self._detail_location(
            detail,
            config,
        )

        if location:
            job["location_raw"] = location

        return job

    @staticmethod
    def _detail_location(
        detail,
        config,
    ):
        path = config.get(
            "location_list_path"
        )

        locations = dot_get(
            detail,
            path,
            [],
        )

        if not isinstance(
            locations,
            list,
        ):
            return ""

        fields = config.get(
            "location_fields"
        ) or []

        values = []

        for location in locations:
            if not isinstance(
                location,
                dict,
            ):
                continue

            pieces = []

            for field in fields:
                value = dot_get(
                    location,
                    field,
                )

                if value:
                    pieces.append(
                        str(value).strip()
                    )

            text = ", ".join(
                x
                for x in pieces
                if x
            )

            if (
                text
                and text not in values
            ):
                values.append(text)

        return "; ".join(values)
