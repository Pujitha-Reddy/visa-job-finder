from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches


class RadancySearchServiceCollector(BaseCollector):
    ats_name = "RADANCY_SAS"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
    }

    SEARCH_TERMS = [
        "software engineer",
        "software developer",
        "full stack",
        "frontend",
        "backend",
        "platform engineer",
        "devops",
        "site reliability",
        "cloud engineer",
        "machine learning engineer",
    ]

    @staticmethod
    def _text(node):
        if not node:
            return ""

        return " ".join(
            node.stripped_strings
        ).strip()

    @staticmethod
    def _parse_date(value):
        value = (
            value
            or ""
        ).strip()

        if not value:
            return None

        for fmt in (
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(
                    value,
                    fmt,
                )

                if dt.tzinfo is None:
                    dt = dt.replace(
                        tzinfo=timezone.utc
                    )

                return dt.astimezone(
                    timezone.utc
                ).isoformat()

            except ValueError:
                pass

        # Arm JSON-LD currently uses values such as:
        # 2026-8-14
        try:
            parts = value.split("-")

            if len(parts) == 3:
                year, month, day = map(
                    int,
                    parts,
                )

                return datetime(
                    year,
                    month,
                    day,
                    tzinfo=timezone.utc,
                ).isoformat()

        except Exception:
            pass

        return None

    @staticmethod
    def _jsonld_jobposting(soup):
        for script in soup.find_all(
            "script",
            attrs={
                "type":
                    "application/ld+json"
            },
        ):
            raw = (
                script.string
                or script.get_text()
                or ""
            ).strip()

            if not raw:
                continue

            try:
                payload = json.loads(
                    raw
                )
            except Exception:
                continue

            objects = (
                payload
                if isinstance(
                    payload,
                    list,
                )
                else [payload]
            )

            for obj in objects:
                if not isinstance(
                    obj,
                    dict,
                ):
                    continue

                if (
                    obj.get("@type")
                    == "JobPosting"
                ):
                    return obj

        return {}

    def _search_params(
        self,
        keyword,
        page,
    ):
        return {
            "CurrentPage":
                page,

            "RecordsPerPage":
                15,

            "SearchType":
                5,

            "SearchResultsModuleName":
                "Search Results",

            "Keywords":
                keyword,

            "Location":
                "",

            "LocationPath":
                "",

            "LocationType":
                "",

            "Latitude":
                "",

            "Longitude":
                "",

            "Distance":
                50,

            "ShowRadius":
                "false",

            "PostalCode":
                "",

            "OrganizationIds":
                "",

            "SortCriteria":
                0,

            "SortDirection":
                1,

            "FacetType":
                0,

            "FacetTerm":
                "",

            "ActiveFacetId":
                0,

            "ResultsType":
                0,

            "KeywordType":
                "",

            "CustomFacetName":
                "",
        }

    def _detail(
        self,
        session,
        url,
        employer_name,
        title,
    ):
        try:
            r = session.get(
                url,
                timeout=30,
            )

            r.raise_for_status()

            soup = BeautifulSoup(
                r.text,
                "html.parser",
            )

            data = self._jsonld_jobposting(
                soup
            )

            description = ""

            if data.get(
                "description"
            ):
                description = BeautifulSoup(
                    str(
                        data[
                            "description"
                        ]
                    ),
                    "html.parser",
                ).get_text(
                    " ",
                    strip=True,
                )

            if not description:
                description = self._text(
                    soup.select_one(
                        ".job-description"
                    )
                )

            posted_at = self._parse_date(
                str(
                    data.get(
                        "datePosted"
                    )
                    or ""
                )
            )

            return {
                "description":
                    description,

                "posted_at":
                    posted_at,
            }

        except Exception as exc:
            print(
                "[RADANCY_SAS DETAIL WARNING]",
                employer_name,
                "/",
                title,
                ":",
                exc,
            )

            return {
                "description": "",
                "posted_at": None,
            }

    def fetch(
        self,
        source,
    ):
        careers_url = (
            source.get(
                "careers_url"
            )
            or ""
        ).strip()

        if not careers_url:
            return []

        employer_name = (
            source.get(
                "employer_name"
            )
            or ""
        )

        # Arm source:
        # https://careers.arm.com/en/search-jobs

        base = careers_url.rstrip("/")

        if base.endswith(
            "/search-jobs"
        ):
            search_url = (
                base
                + "/results"
            )
        else:
            search_url = (
                base
                + "/results"
            )

        session = requests.Session()

        headers = dict(
            self.HEADERS
        )

        headers["Referer"] = (
            careers_url
        )

        session.headers.update(
            headers
        )

        jobs = {}
        seen_search_cards = set()

        for keyword in (
            self.SEARCH_TERMS
        ):
            print()
            print(
                f"[RADANCY_SAS SEARCH] "
                f"{employer_name}: "
                f"{keyword}"
            )

            page = 1
            total_pages = None

            while True:
                r = session.get(
                    search_url,
                    params=self._search_params(
                        keyword,
                        page,
                    ),
                    timeout=30,
                )

                r.raise_for_status()

                payload = r.json()

                html = (
                    payload.get(
                        "results"
                    )
                    or ""
                )

                if not html:
                    break

                soup = BeautifulSoup(
                    html,
                    "html.parser",
                )

                root = soup.select_one(
                    "#search-results"
                )

                if not root:
                    break

                if total_pages is None:
                    try:
                        total_pages = int(
                            root.get(
                                "data-total-pages"
                            )
                            or 1
                        )
                    except Exception:
                        total_pages = 1

                cards = soup.select(
                    "#search-results-jobs "
                    ".job-card"
                )

                if not cards:
                    break

                accepted = 0
                new_count = 0

                for card in cards:
                    link = card.select_one(
                        "a.job-card__title[href]"
                    )

                    if not link:
                        continue

                    title = self._text(
                        link
                    )

                    href = (
                        link.get("href")
                        or ""
                    ).strip()

                    job_id = (
                        link.get(
                            "data-job-id"
                        )
                        or ""
                    ).strip()

                    if not title or not href:
                        continue

                    url = urljoin(
                        careers_url,
                        href,
                    )

                    search_key = (
                        job_id
                        or url
                    )

                    if (
                        search_key
                        in seen_search_cards
                    ):
                        continue

                    seen_search_cards.add(
                        search_key
                    )

                    if not title_matches(
                        title
                    ):
                        continue

                    accepted += 1

                    location = self._text(
                        card.select_one(
                            ".location"
                        )
                    )

                    category = self._text(
                        card.select_one(
                            ".category"
                        )
                    )

                    intro = self._text(
                        card.select_one(
                            ".job-card__intro"
                        )
                    )

                    detail = self._detail(
                        session,
                        url,
                        employer_name,
                        title,
                    )

                    description = (
                        detail[
                            "description"
                        ]
                        or intro
                    )

                    jobs[
                        search_key
                    ] = {
                        "company_name_raw":
                            employer_name,

                        "title":
                            title,

                        "location_raw":
                            location,

                        "description_raw":
                            description,

                        "source_url":
                            url,

                        "source_job_id":
                            job_id
                            or url,

                        "posted_at":
                            detail[
                                "posted_at"
                            ],

                        "posted_at_confidence":
                            (
                                "HIGH"
                                if detail[
                                    "posted_at"
                                ]
                                else "UNKNOWN"
                            ),

                        "posted_at_source":
                            (
                                "RADANCY_JSONLD_DATE"
                                if detail[
                                    "posted_at"
                                ]
                                else "UNKNOWN"
                            ),

                        "source":
                            self.ats_name,

                        "radancy_category":
                            category,
                    }

                    new_count += 1

                print(
                    f"[RADANCY_SAS] "
                    f"{keyword!r} "
                    f"page {page}: "
                    f"{len(cards)} cards / "
                    f"{accepted} accepted / "
                    f"{new_count} new"
                )

                if (
                    page >= (
                        total_pages
                        or 1
                    )
                ):
                    break

                page += 1

        print()
        print(
            f"[RADANCY_SAS TOTAL] "
            f"{employer_name}: "
            f"{len(jobs)} unique target jobs"
        )

        return list(
            jobs.values()
        )