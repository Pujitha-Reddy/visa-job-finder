from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .common import title_matches


STRONG_JOB_PATTERNS = (
    # Deloitte / Taleo-style
    r"/jobdetail/",

    # Generic /job/<slug>
    r"/job/[^/?#]+",

    # Generic numeric job IDs
    r"/jobs/\d+(?:/|$)",
    r"/position/\d+(?:/|$)",
    r"/positions/\d+(?:/|$)",
    r"/opening/\d+(?:/|$)",
    r"/openings/\d+(?:/|$)",
    r"/vacancy/\d+(?:/|$)",

    # MathWorks-style:
    # /company/jobs/opportunities/36842-some-role
    r"/company/jobs/opportunities/\d+-[^/?#]+",
)


NEGATIVE_URL_TERMS = (
    "privacy",
    "benefits",
    "culture",
    "login",
    "signin",
    "sign-in",
    "talent-community",
    "jointalentcommunity",
    "job-alert",
    "saved-jobs",
    "candidate-privacy",
    "faq",
    "accessibility",
    "application-process",
    "fraud",
    "terms",
)


NEGATIVE_TITLES = {
    "careers",
    "jobs",
    "search jobs",
    "view jobs",
    "find jobs",
    "apply",
    "apply now",
    "learn more",
    "view more",
    "read more",
    "job search",
    "open positions",
    "skip to content",
    "skip to main content",
    "reset",
    "next",
    "next >>",
    "previous",
    "<< previous",
    "entry level",
    "experienced",
    "global careers site",

    # Generic navigation/filter labels
    "learn",
    "company",
    "office locations",
    "students and new careers",
    "engineering development group",
    "internships",
    "how we hire",
    "resources",
    "careers faq",
    "clear",
    "new career",
}


class GenericJobCollector:
    ats_name = "GENERIC"
    name = "GENERIC"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            self.HEADERS
        )

    # ======================================================
    # HTTP helpers
    # ======================================================

    def _request(
        self,
        url: str,
        referer: str | None = None,
    ):
        headers = {}

        if referer:
            headers["Referer"] = referer

        return self.session.get(
            url,
            headers=headers,
            timeout=30,
            allow_redirects=True,
        )

    def _bootstrap_origin(
        self,
        url: str,
    ):
        """
        Warm the session before accessing a search surface.

        Some career sites reject a cold request but allow
        navigation after the site root has been visited.
        """

        parsed = urlparse(
            url
        )

        if not parsed.scheme or not parsed.netloc:
            return

        origin = (
            f"{parsed.scheme}://"
            f"{parsed.netloc}/"
        )

        try:
            self._request(
                origin
            )
        except requests.RequestException:
            pass

    # ======================================================
    # Main collector
    # ======================================================

    def fetch(
        self,
        source,
    ):
        url = (
            source.get("careers_url")
            or source.get("url")
        )

        if not url:
            return []

        # Warm session first.
        self._bootstrap_origin(
            url
        )

        response = self._request(
            url
        )

        # One controlled retry for access-restricted sites.
        if response.status_code == 403:
            self._bootstrap_origin(
                url
            )

            parsed = urlparse(
                url
            )

            referer = (
                f"{parsed.scheme}://"
                f"{parsed.netloc}/"
            )

            response = self._request(
                url,
                referer=referer,
            )

        response.raise_for_status()

        final_url = response.url
        html = response.text

        jobs = []

        # --------------------------------------------------
        # Method 1:
        # Structured JobPosting objects present directly on
        # the listing/search page.
        # --------------------------------------------------

        jobs.extend(
            self._extract_json_ld(
                html,
                final_url,
            )
        )

        # --------------------------------------------------
        # Method 2:
        # Stable job-detail links from the listing page.
        # --------------------------------------------------

        jobs.extend(
            self._extract_links(
                html,
                final_url,
            )
        )

        # --------------------------------------------------
        # Deduplicate listing-page discoveries.
        # --------------------------------------------------

        jobs = self._dedupe(
            jobs
        )

        # --------------------------------------------------
        # IMPORTANT:
        # Apply the same software-role title boundary used
        # by the rest of the collector ecosystem BEFORE
        # fetching individual detail pages.
        #
        # This prevents dozens/hundreds of irrelevant detail
        # requests for HR, finance, sales, tax, etc.
        # --------------------------------------------------

        jobs = [
            job
            for job in jobs
            if title_matches(
                job.get("title")
                or ""
            )
        ]

        # --------------------------------------------------
        # Detail-page enrichment.
        #
        # Fetch only jobs that survived title matching.
        # --------------------------------------------------

        enriched_jobs = []

        for job in jobs:
            enriched_jobs.append(
                self._enrich_job(
                    job
                )
            )

        jobs = enriched_jobs

        # --------------------------------------------------
        # Required canonical raw-job fields.
        # --------------------------------------------------

        employer_name = (
            source.get("employer_name")
            or source.get("display_name")
            or source.get("company_name")
        )

        for job in jobs:
            job["source"] = (
                self.ats_name
            )

            job["ats"] = (
                self.ats_name
            )

            job["company_name_raw"] = (
                employer_name
            )

        return self._dedupe(
            jobs
        )

    # ======================================================
    # Listing-page JSON-LD JobPosting extraction
    # ======================================================

    def _extract_json_ld(
        self,
        html,
        base_url,
    ):
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        jobs = []

        scripts = soup.find_all(
            "script",
            attrs={
                "type": "application/ld+json"
            },
        )

        for script in scripts:
            raw = (
                script.string
                or script.get_text()
            )

            if not raw:
                continue

            try:
                payload = json.loads(
                    raw
                )
            except Exception:
                continue

            for obj in self._walk_json(
                payload
            ):
                if not isinstance(
                    obj,
                    dict,
                ):
                    continue

                if not self._is_jobposting(
                    obj
                ):
                    continue

                title = (
                    obj.get("title")
                    or obj.get("name")
                )

                if not title:
                    continue

                source_url = (
                    obj.get("url")
                    or obj.get("@id")
                    or base_url
                )

                source_url = urljoin(
                    base_url,
                    str(source_url),
                )

                source_job_id = (
                    self._json_identifier(
                        obj
                    )
                    or self._job_id_from_url(
                        source_url
                    )
                )

                date_posted = obj.get(
                    "datePosted"
                )

                location = (
                    self._json_location(
                        obj
                    )
                )

                jobs.append({
                    "title":
                        self._clean(
                            title
                        ),

                    "source_url":
                        source_url,

                    "source_job_id":
                        source_job_id,

                    "location":
                        location,

                    "location_raw":
                        location,

                    "description":
                        self._clean(
                            obj.get(
                                "description"
                            )
                        ),

                    "date_posted":
                        date_posted,

                    "posted_raw":
                        date_posted,

                    "posted_at":
                        date_posted,

                    "employment_type":
                        obj.get(
                            "employmentType"
                        ),

                    "_generic_method":
                        "JSON_LD",
                })

        return jobs

    def _walk_json(
        self,
        value,
    ):
        found = []

        if isinstance(
            value,
            dict,
        ):
            found.append(
                value
            )

            for child in (
                value.values()
            ):
                found.extend(
                    self._walk_json(
                        child
                    )
                )

        elif isinstance(
            value,
            list,
        ):
            for child in value:
                found.extend(
                    self._walk_json(
                        child
                    )
                )

        return found

    @staticmethod
    def _is_jobposting(
        obj,
    ):
        object_type = obj.get(
            "@type"
        )

        if isinstance(
            object_type,
            list,
        ):
            return any(
                str(value).lower()
                == "jobposting"
                for value in object_type
            )

        return (
            str(
                object_type
                or ""
            ).lower()
            == "jobposting"
        )

    @staticmethod
    def _json_identifier(
        obj,
    ):
        identifier = obj.get(
            "identifier"
        )

        if isinstance(
            identifier,
            dict,
        ):
            value = (
                identifier.get("value")
                or identifier.get("@id")
                or identifier.get("name")
            )

            if value:
                return str(
                    value
                ).strip()

        elif identifier:
            return str(
                identifier
            ).strip()

        return None

    # ======================================================
    # Listing-page job links
    # ======================================================

    def _extract_links(
        self,
        html,
        base_url,
    ):
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        jobs = []

        for anchor in soup.find_all(
            "a",
            href=True,
        ):
            href = (
                anchor.get("href")
                or ""
            ).strip()

            if not href:
                continue

            title = self._clean(
                anchor.get_text(
                    " ",
                    strip=True,
                )
            )

            if not title:
                continue

            absolute = urljoin(
                base_url,
                href,
            )

            if not self._looks_like_job_url(
                absolute
            ):
                continue

            if not self._looks_like_title(
                title
            ):
                continue

            jobs.append({
                "title":
                    title,

                "source_url":
                    absolute,

                "source_job_id":
                    self._job_id_from_url(
                        absolute
                    ),

                "location":
                    None,

                "location_raw":
                    None,

                "description":
                    None,

                "date_posted":
                    None,

                "posted_raw":
                    None,

                "posted_at":
                    None,

                "employment_type":
                    None,

                "_generic_method":
                    "JOB_LINK",
            })

        return jobs

    # ======================================================
    # Detail-page enrichment
    # ======================================================

    def _extract_jobposting_jsonld(
        self,
        html,
        source_url,
    ):
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        scripts = soup.find_all(
            "script",
            attrs={
                "type": "application/ld+json"
            },
        )

        for script in scripts:
            raw = (
                script.string
                or script.get_text()
            )

            if not raw:
                continue

            try:
                payload = json.loads(
                    raw
                )
            except Exception:
                continue

            for obj in self._walk_json(
                payload
            ):
                if not isinstance(
                    obj,
                    dict,
                ):
                    continue

                if not self._is_jobposting(
                    obj
                ):
                    continue

                title = self._clean(
                    obj.get("title")
                    or obj.get("name")
                )

                description = (
                    self._clean(
                        obj.get(
                            "description"
                        )
                    )
                )

                location = (
                    self._json_location(
                        obj
                    )
                )

                date_posted = (
                    obj.get(
                        "datePosted"
                    )
                )

                source_job_id = (
                    self._json_identifier(
                        obj
                    )
                    or self._job_id_from_url(
                        source_url
                    )
                )

                return {
                    "title":
                        title,

                    "description":
                        description,

                    "location_raw":
                        location,

                    "location":
                        location,

                    "date_posted":
                        date_posted,

                    "posted_raw":
                        date_posted,

                    "posted_at":
                        date_posted,

                    "employment_type":
                        obj.get(
                            "employmentType"
                        ),

                    "source_job_id":
                        source_job_id,

                    "_detail_method":
                        "JSON_LD",
                }

        return None

    def _extract_dom_detail(
        self,
        html,
    ):
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        # --------------------------------------------------
        # Description
        # --------------------------------------------------

        description = ""

        description_candidates = [
            soup.select_one(
                ".job-description"
            ),
            soup.select_one(
                ".job-description-content"
            ),
            soup.select_one(
                ".job-details"
            ),
            soup.select_one(
                "[class*='job-description']"
            ),
            soup.select_one(
                "[class*='description']"
            ),
            soup.select_one(
                "main"
            ),
        ]

        for node in (
            description_candidates
        ):
            if not node:
                continue

            text = self._clean(
                node.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                text
                and len(text)
                > len(description)
            ):
                description = text

        # --------------------------------------------------
        # Location
        # --------------------------------------------------

        location = None

        location_selectors = (
            ".job-location",
            "[class*='job-location']",
            "[data-automation-id='locations']",
            "[class*='location']",
        )

        for selector in (
            location_selectors
        ):
            node = soup.select_one(
                selector
            )

            if not node:
                continue

            value = self._clean(
                node.get_text(
                    " ",
                    strip=True,
                )
            )

            if value:
                location = value
                break

        # --------------------------------------------------
        # Posting date
        # --------------------------------------------------

        date_posted = None

        date_selectors = (
            "time[datetime]",
            "[class*='date-posted']",
            "[class*='posted-date']",
            "[class*='posting-date']",
        )

        for selector in (
            date_selectors
        ):
            node = soup.select_one(
                selector
            )

            if not node:
                continue

            if node.name == "time":
                value = (
                    node.get(
                        "datetime"
                    )
                    or node.get_text(
                        " ",
                        strip=True,
                    )
                )
            else:
                value = node.get_text(
                    " ",
                    strip=True,
                )

            value = self._clean(
                value
            )

            if value:
                date_posted = value
                break

        return {
            "description":
                description
                or None,

            "location_raw":
                location,

            "location":
                location,

            "date_posted":
                date_posted,

            "posted_raw":
                date_posted,

            "posted_at":
                date_posted,

            "_detail_method":
                "DOM",
        }

    def _enrich_job(
        self,
        job,
    ):
        source_url = job.get(
            "source_url"
        )

        if not source_url:
            return job

        try:
            response = self._request(
                source_url
            )

            # Some sites expect normal navigation from their
            # listing/search page or home domain.
            if response.status_code == 403:
                self._bootstrap_origin(
                    source_url
                )

                parsed = urlparse(
                    source_url
                )

                referer = (
                    f"{parsed.scheme}://"
                    f"{parsed.netloc}/"
                )

                response = (
                    self._request(
                        source_url,
                        referer=referer,
                    )
                )

            response.raise_for_status()

        except Exception as exc:
            job[
                "_detail_error"
            ] = str(exc)

            # Preserve a URL-derived job ID even when
            # enrichment fails.
            if not job.get(
                "source_job_id"
            ):
                job[
                    "source_job_id"
                ] = (
                    self._job_id_from_url(
                        source_url
                    )
                )

            return job

        # Prefer structured JobPosting data.
        detail = (
            self._extract_jobposting_jsonld(
                response.text,
                response.url,
            )
        )

        # Fall back to DOM extraction.
        if detail is None:
            detail = (
                self._extract_dom_detail(
                    response.text
                )
            )

        for key, value in (
            detail
            or {}
        ).items():
            if value not in (
                None,
                "",
            ):
                job[key] = value

        # Preserve the canonical URL after redirects.
        job["source_url"] = (
            response.url
        )

        if not job.get(
            "source_job_id"
        ):
            job[
                "source_job_id"
            ] = self._job_id_from_url(
                response.url
            )

        # Keep downstream aliases synchronized.
        if job.get(
            "location_raw"
        ):
            job["location"] = (
                job[
                    "location_raw"
                ]
            )

        if job.get(
            "date_posted"
        ):
            job["posted_raw"] = (
                job[
                    "date_posted"
                ]
            )

            job["posted_at"] = (
                job[
                    "date_posted"
                ]
            )

        return job

    # ======================================================
    # URL validation
    # ======================================================

    def _looks_like_job_url(
        self,
        url,
    ):
        lower = (
            url
            or ""
        ).lower()

        if any(
            term in lower
            for term in NEGATIVE_URL_TERMS
        ):
            return False

        parsed = urlparse(
            lower
        )

        path = (
            parsed.path
            or ""
        )

        for pattern in (
            STRONG_JOB_PATTERNS
        ):
            if re.search(
                pattern,
                path,
                flags=re.I,
            ):
                return True

        # Generic ID-bearing job URL fallback.
        if re.search(
            (
                r"(?:job|position|opening)"
                r"[-_/]?[a-z]*[-_/]?"
                r"\d{4,}"
            ),
            path,
            flags=re.I,
        ):
            return True

        return False

    # ======================================================
    # Title validation
    # ======================================================

    def _looks_like_title(
        self,
        title,
    ):
        title = (
            title
            or ""
        ).strip()

        if len(title) < 4:
            return False

        if len(title) > 180:
            return False

        lower = (
            title.lower()
        )

        if lower in NEGATIVE_TITLES:
            return False

        if lower.startswith(
            (
                "next ",
                "previous ",
                "skip ",
                "view all ",
                "search ",
            )
        ):
            return False

        if not re.search(
            r"[a-zA-Z]",
            title,
        ):
            return False

        return True

    # ======================================================
    # JSON-LD location
    # ======================================================

    def _json_location(
        self,
        obj,
    ):
        location = obj.get(
            "jobLocation"
        )

        if not location:
            return None

        if isinstance(
            location,
            list,
        ):
            locations = []

            for item in location:
                value = (
                    self._single_json_location(
                        item
                    )
                )

                if (
                    value
                    and value not in locations
                ):
                    locations.append(
                        value
                    )

            return (
                " | ".join(
                    locations
                )
                or None
            )

        return (
            self._single_json_location(
                location
            )
        )

    def _single_json_location(
        self,
        location,
    ):
        if not isinstance(
            location,
            dict,
        ):
            return None

        address = location.get(
            "address"
        )

        if not isinstance(
            address,
            dict,
        ):
            return None

        country = address.get(
            "addressCountry"
        )

        if isinstance(
            country,
            dict,
        ):
            country = (
                country.get("name")
                or country.get(
                    "@id"
                )
            )

        pieces = [
            address.get(
                "addressLocality"
            ),
            address.get(
                "addressRegion"
            ),
            country,
        ]

        pieces = [
            str(value).strip()
            for value in pieces
            if value
        ]

        return (
            ", ".join(
                pieces
            )
            or None
        )

    # ======================================================
    # Job ID extraction
    # ======================================================

    @staticmethod
    def _job_id_from_url(
        url,
    ):
        if not url:
            return None

        path = urlparse(
            url
        ).path

        patterns = (
            # Deloitte:
            # /JobDetail/foo/363629
            r"/jobdetail/[^/]+/(\d+)",

            # MathWorks:
            # /opportunities/36842-title
            r"/opportunities/(\d+)-",

            # Generic job ID endings
            r"/(?:jobs?|positions?|openings?)/(\d+)(?:/|$)",
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                path,
                flags=re.I,
            )

            if match:
                return match.group(
                    1
                )

        return None

    # ======================================================
    # Helpers
    # ======================================================

    def _clean(
        self,
        value,
    ):
        if value is None:
            return None

        value = str(
            value
        )

        # Only parse when the input actually resembles HTML.
        if (
            "<" in value
            and ">" in value
        ):
            value = BeautifulSoup(
                value,
                "html.parser",
            ).get_text(
                " ",
                strip=True,
            )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    def _dedupe(
        self,
        jobs,
    ):
        seen = set()
        result = []

        for job in jobs:
            title = (
                job.get("title")
                or ""
            ).strip()

            url = (
                job.get("source_url")
                or ""
            ).strip()

            if not title or not url:
                continue

            clean_url = (
                url.split("#")[0]
            )

            # Prefer source job ID when present.
            source_job_id = (
                job.get(
                    "source_job_id"
                )
                or self._job_id_from_url(
                    clean_url
                )
            )

            if source_job_id:
                key = (
                    "ID",
                    str(
                        source_job_id
                    ),
                )
            else:
                key = (
                    "URL",
                    clean_url,
                    title.lower(),
                )

            if key in seen:
                continue

            seen.add(
                key
            )

            job["source_url"] = (
                clean_url
            )

            if (
                source_job_id
                and not job.get(
                    "source_job_id"
                )
            ):
                job[
                    "source_job_id"
                ] = source_job_id

            result.append(
                job
            )

        return result
