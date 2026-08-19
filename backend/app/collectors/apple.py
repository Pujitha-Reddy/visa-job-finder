from __future__ import annotations

import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches


class AppleCollector(BaseCollector):
    """
    Production-safe Apple collector.

    Strategy
    --------
    1. Discover jobs from Apple's public search pages.
    2. Filter software titles BEFORE doing detail requests.
    3. Keep title/location/date/search excerpt as the baseline record.
    4. Attempt Apple's structured jobDetails API only as enrichment.
    5. If Apple responds with 429/436, stop detail enrichment for the
       remainder of the run and preserve baseline jobs.

    Detail enrichment is optional. Discovery must never depend on it.
    """

    ats_name = "APPLE"

    BASE = "https://jobs.apple.com"
    SEARCH = "https://jobs.apple.com/en-us/search"
    DETAIL_API = "https://jobs.apple.com/api/v1/jobDetails/{job_id}"

    # We only care about fresh jobs, not Apple's entire historical catalog.
    MAX_PAGES = 12

    # Don't hammer protected detail APIs.
    DETAIL_DELAY_SECONDS = 1.25

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

        self.detail_enrichment_available = True

    # ---------------------------------------------------------
    # PUBLIC ENTRYPOINT
    # ---------------------------------------------------------

    def fetch(self, source: dict) -> list[dict]:
        baseline_jobs = self._discover_jobs(source)

        print(
            f"Apple discovery: {len(baseline_jobs)} "
            "software jobs before detail enrichment"
        )

        final_jobs = []

        for index, job in enumerate(baseline_jobs):
            # Once Apple indicates that detail enrichment is being blocked,
            # stop making detail calls for the remainder of this source run.
            if not self.detail_enrichment_available:
                final_jobs.append(job)
                continue

            job_id = job.get("_apple_job_id")

            if not job_id:
                final_jobs.append(job)
                continue

            try:
                # Slow down detail requests.
                if index > 0:
                    time.sleep(self.DETAIL_DELAY_SECONDS)

                detail = self._fetch_detail(job_id)

                if detail:
                    job = self._merge_detail(
                        baseline=job,
                        detail=detail,
                    )

            except requests.HTTPError as exc:
                status = (
                    exc.response.status_code
                    if exc.response is not None
                    else None
                )

                # Apple uses nonstandard 436 responses under request
                # protection. 429 is the normal rate-limit equivalent.
                if status in {429, 436}:
                    print(
                        "[APPLE] Detail enrichment blocked "
                        f"(HTTP {status}). "
                        "Continuing with search-page metadata."
                    )

                    self.detail_enrichment_available = False

                else:
                    print(
                        "[APPLE DETAIL ERROR]",
                        job_id,
                        exc,
                    )

            except Exception as exc:
                print(
                    "[APPLE DETAIL ERROR]",
                    job_id,
                    exc,
                )

            final_jobs.append(job)

        # Internal implementation metadata should not escape collector.
        for job in final_jobs:
            job.pop("_apple_job_id", None)

        unique = {}

        for job in final_jobs:
            url = job.get("source_url")

            if url:
                unique[url] = job

        return list(unique.values())

    # ---------------------------------------------------------
    # DISCOVERY
    # ---------------------------------------------------------

    def _discover_jobs(self, source: dict) -> list[dict]:
        found = {}

        for page in range(1, self.MAX_PAGES + 1):
            response = self.session.get(
                self.SEARCH,
                params={
                    "location": "united-states-USA",
                    "page": page,
                },
                timeout=30,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                },
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            page_role_urls = 0
            page_software_jobs = 0

            for anchor in soup.find_all("a", href=True):
                href = anchor.get("href") or ""

                if "/details/" not in href:
                    continue

                parsed = self._parse_role_url(
                    urljoin(self.BASE, href)
                )

                if not parsed:
                    continue

                page_role_urls += 1

                title = anchor.get_text(
                    " ",
                    strip=True,
                )

                if not title:
                    continue

                # Critical optimization:
                # reject non-software jobs BEFORE detail API enrichment.
                if not title_matches(title):
                    continue

                page_software_jobs += 1

                container = self._find_result_container(anchor)

                text = (
                    container.get_text(
                        " ",
                        strip=True,
                    )
                    if container is not None
                    else title
                )

                location = self._extract_location(text)
                posted = self._extract_date(text)
                excerpt = self._extract_excerpt(
                    text=text,
                    title=title,
                )

                source_url = parsed["url"]

                found[source_url] = {
                    "external_id": parsed["job_number"],
                    "source": "APPLE",
                    "source_url": source_url,
                    "apply_url": source_url,

                    "company_name_raw": source["employer_name"],
                    "source_type": source.get(
                        "source_type",
                        "DIRECT_EMPLOYER",
                    ),

                    "ats": "APPLE",

                    "title": title,
                    "description": excerpt,
                    "location_raw": location,

                    "posted_at": posted,
                    "source_published_at": posted,

                    "freshness_confidence": (
                        "HIGH"
                        if posted
                        else "UNKNOWN"
                    ),
                    "freshness_source": (
                        "APPLE_SEARCH_PAGE"
                        if posted
                        else "UNKNOWN"
                    ),

                    "_apple_job_id": parsed["job_id"],
                }

            print(
                f"Apple page {page}: "
                f"{page_role_urls} roles / "
                f"{page_software_jobs} software"
            )

            # Apple's pagination is exhausted.
            if page_role_urls == 0:
                break

        return list(found.values())

    # ---------------------------------------------------------
    # SEARCH PAGE PARSING
    # ---------------------------------------------------------

    @staticmethod
    def _find_result_container(anchor):
        """
        Walk upward until we get a useful result-card-sized block.

        Apple has changed class names before, so avoid relying on one
        brittle CSS selector.
        """

        node = anchor

        for _ in range(8):
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

            if (
                "Role Number:" in text
                and "Location" in text
            ):
                return node

        return anchor.parent

    @staticmethod
    def _extract_location(text: str) -> str:
        """
        Apple result text normally resembles:

            Software and Services Aug 18, 2026
            Location Cupertino
            Actions
            ...
        """

        patterns = [
            r"\bLocation\s+(.+?)\s+Actions\b",
            r"\bLocation\s+(.+?)\s+See full role description\b",
            r"\bLocation\s+(.+?)\s+Share\b",
            r"\bLocation\s+(.+?)\s+Role Number:",
        ]

        for pattern in patterns:
            m = re.search(
                pattern,
                text,
                flags=re.I,
            )

            if m:
                value = re.sub(
                    r"\s+",
                    " ",
                    m.group(1),
                ).strip()

                if value:
                    return value

        return ""

    @staticmethod
    def _extract_date(text: str) -> str | None:
        m = re.search(
            r"\b("
            r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
            r")\s+\d{1,2},\s+\d{4}\b",
            text,
        )

        if not m:
            return None

        value = m.group(0)

        # Normalize to ISO rather than keeping display text.
        try:
            dt = datetime.strptime(
                value,
                "%b %d, %Y",
            )

            return dt.replace(
                tzinfo=timezone.utc
            ).isoformat()

        except ValueError:
            return value

    @staticmethod
    def _extract_excerpt(
        text: str,
        title: str,
    ) -> str:

        cleaned = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        # Remove obvious repeated UI labels where possible.
        cleaned = cleaned.replace(
            "See full role description",
            " ",
        )

        cleaned = cleaned.replace(
            "Submit Resume",
            " ",
        )

        cleaned = re.sub(
            r"\s+",
            " ",
            cleaned,
        ).strip()

        # Keep enough context for experience/work-arrangement analysis.
        return cleaned[:8000]

    @staticmethod
    def _parse_role_url(
        url: str,
    ) -> dict | None:

        # Preserve the full Apple job number including posting/location
        # suffix where present.
        m = re.search(
            r"/details/([^/]+)/",
            url,
            flags=re.I,
        )

        if not m:
            return None

        job_number = m.group(1)

        base = re.match(
            r"(\d+)",
            job_number,
        )

        if not base:
            return None

        req_number = base.group(1)

        return {
            "url": url,
            "job_number": job_number,
            "job_id": f"REQ-{req_number}",
        }

    # ---------------------------------------------------------
    # OPTIONAL STRUCTURED ENRICHMENT
    # ---------------------------------------------------------

    def _fetch_detail(
        self,
        job_id: str,
    ) -> dict | None:

        response = self.session.get(
            self.DETAIL_API.format(
                job_id=job_id
            ),
            timeout=30,
            headers={
                "Accept": "application/json",
                "Referer": self.SEARCH,
            },
        )

        response.raise_for_status()

        payload = response.json()

        detail = payload.get("res")

        return (
            detail
            if isinstance(detail, dict)
            else None
        )

    # ---------------------------------------------------------
    # STRUCTURED DATA NORMALIZATION
    # ---------------------------------------------------------

    @staticmethod
    def _detail_location(
        detail: dict,
    ) -> str:

        values = []

        for loc in detail.get("locations") or []:
            if not isinstance(loc, dict):
                continue

            parts = [
                loc.get("city"),
                loc.get("stateProvince"),
                loc.get("countryName"),
            ]

            value = ", ".join(
                str(x).strip()
                for x in parts
                if x and str(x).strip()
            )

            if value and value not in values:
                values.append(value)

        return "; ".join(values)

    @staticmethod
    def _detail_description(
        detail: dict,
    ) -> str:

        parts = []

        for field in (
            "jobSummary",
            "description",
            "responsibilities",
            "minimumQualifications",
            "preferredQualifications",
            "additionalRequirements",
            "educationExperience",
        ):
            value = detail.get(field)

            if not isinstance(value, str):
                continue

            value = value.strip()

            if value and value not in parts:
                parts.append(value)

        return "\n\n".join(parts)

    def _merge_detail(
        self,
        baseline: dict,
        detail: dict,
    ) -> dict:

        job = dict(baseline)

        title = (
            detail.get("postingTitle")
            or ""
        ).strip()

        if title:
            job["title"] = title

        location = self._detail_location(
            detail
        )

        if location:
            job["location_raw"] = location

        description = self._detail_description(
            detail
        )

        if description:
            job["description"] = description

        published = (
            detail.get("longPostingDate")
            or detail.get("postDateInGMT")
            or detail.get("postingDateMeta")
        )

        if published:
            job["posted_at"] = published
            job["source_published_at"] = published
            job["freshness_confidence"] = "HIGH"
            job["freshness_source"] = "APPLE_DETAIL_API"

        external_id = (
            detail.get("jobNumber")
            or detail.get("reqId")
            or detail.get("id")
        )

        if external_id:
            job["external_id"] = external_id

        return job
