from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin, urlencode, urlparse, parse_qsl

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches


class RadancyCollector(BaseCollector):
    ats_name = "RADANCY"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    @staticmethod
    def _text(node):
        if not node:
            return ""

        return " ".join(
            node.stripped_strings
        ).strip()

    @staticmethod
    def _parse_date(value):
        value = (value or "").strip()

        if not value:
            return None

        for fmt in (
            "%m/%d/%Y",
            "%Y-%m-%d",
            "%B %d, %Y",
            "%b %d, %Y",
        ):
            try:
                dt = datetime.strptime(
                    value,
                    fmt,
                ).replace(
                    tzinfo=timezone.utc
                )

                return dt.isoformat()

            except ValueError:
                pass

        return None

    @staticmethod
    def _strip_label(node, label):
        """
        Example:
            <span>
                <strong>Posted:</strong>
                08/17/2026
            </span>

        returns:
            08/17/2026
        """
        text = RadancyCollector._text(node)

        if not text:
            return ""

        if text.lower().startswith(
            label.lower()
        ):
            text = text[len(label):].strip()

        return text

    @staticmethod
    def _page_url(base_url, page):
        """
        Preserve any existing query parameters and add p=N.

        Page 1 uses the original URL.
        """
        if page <= 1:
            return base_url

        parsed = urlparse(
            base_url
        )

        query = dict(
            parse_qsl(
                parsed.query,
                keep_blank_values=True,
            )
        )

        query["p"] = str(page)

        return parsed._replace(
            query=urlencode(query),
        ).geturl()

    def _parse_card(
        self,
        card,
        base_url,
    ):
        link = card.select_one(
            "a.sr-job-link[href*='/job/']"
        )

        if not link:
            return None

        href = (
            link.get("href")
            or ""
        ).strip()

        if not href:
            return None

        title_node = link.select_one(
            "h2"
        )

        location_node = link.select_one(
            ".job-location"
        )

        date_node = link.select_one(
            ".job-date-posted"
        )

        job_id_node = link.select_one(
            ".jobId"
        )

        title = self._text(
            title_node
        )

        location = self._text(
            location_node
        )

        posted_raw = self._strip_label(
            date_node,
            "Posted:",
        )

        job_id = self._strip_label(
            job_id_node,
            "Job ID:",
        )

        if not title:
            return None

        source_url = urljoin(
            base_url,
            href,
        )

        return {
            "title": title,
            "location_raw": location,
            "posted_raw": posted_raw,
            "source_job_id": job_id,
            "source_url": source_url,
        }

    def _detail_description(
        self,
        session,
        source_url,
        employer_name,
        title,
    ):
        try:
            r = session.get(
                source_url,
                timeout=30,
            )

            r.raise_for_status()

            soup = BeautifulSoup(
                r.text,
                "html.parser",
            )

            candidates = [
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
                    "main"
                ),
            ]

            best = ""

            for candidate in candidates:
                text = self._text(
                    candidate
                )

                if len(text) > len(best):
                    best = text

            return best

        except Exception as exc:
            print(
                "[RADANCY DETAIL WARNING]",
                employer_name,
                "/",
                title,
                ":",
                exc,
            )

            return ""

    def fetch(self, source):
        careers_url = (
            source.get("careers_url")
            or ""
            ).strip()

        if not careers_url:
            return []

        employer_name = source.get(
            "employer_name"
            )

        session = requests.Session()
        session.headers.update(
            self.HEADERS
            )

        jobs = []
        seen_urls = set()

    # Radancy search supports ?k=<keyword>.
    #
    # Use several controlled software-role searches,
    # then dedupe by source URL.
        searches = [
            "software engineer",
            "software developer",
            "full stack",
            "frontend",
            "backend",
            "platform engineer",
            "site reliability",
            "devops",
            "cloud engineer",
            "application engineer",
        ]

        for search_text in searches:
            print()
            print(
                f"[RADANCY SEARCH] "
                f"{employer_name}: "
                f"{search_text}"
                )

            page = 1

            while True:
                parsed = urlparse(
                    careers_url
                    )
                query = dict(
                    parse_qsl(
                        parsed.query,
                        keep_blank_values=True,
                        )
                    )

                query["k"] = search_text

                if page > 1:
                    query["p"] = str(page)

                page_url = parsed._replace(
                    query=urlencode(query),
                ).geturl()

                response = session.get(
                    page_url,
                    timeout=30,
                    allow_redirects=True,
            )

                response.raise_for_status()
                soup = BeautifulSoup(
                    response.text,
                    "html.parser",
            )

                cards = soup.select(
                    "li.search-results-list__list-item"
            )

                if not cards:
                    break

                new_urls_this_page = 0
                accepted_this_page = 0

                for card in cards:
                    parsed_job = self._parse_card(
                        card,
                        response.url,
                )
                    if not parsed_job:
                        continue

                    source_url = parsed_job[
                        "source_url"
                ]

                    if source_url in seen_urls:
                        continue

                # Mark it seen before title filtering so
                # repeated searches don't cause extra work.
                    seen_urls.add(
                        source_url
                )

                    new_urls_this_page += 1
                    title = parsed_job[
                        "title"
                ]

                    if not title_matches(
                        title
                ):
                        continue

                    description = (
                        self._detail_description(
                            session,
                            source_url,
                            employer_name,
                            title,
                    )
                )

                    jobs.append({
                        "company_name_raw":
                        employer_name,

                        "title":
                        title,

                        "location_raw":
                        parsed_job[
                            "location_raw"
                        ],

                        "description_raw":
                        description,

                        "source_url":
                        source_url,

                        "source_job_id":
                        parsed_job[
                            "source_job_id"
                        ],

                        "posted_at":
                        self._parse_date(
                            parsed_job[
                                "posted_raw"
                            ]
                        ),

                        "posted_at_confidence":
                        (
                            "HIGH"
                            if parsed_job[
                                "posted_raw"
                            ]
                            else "UNKNOWN"
                        ),

                         "posted_at_source":
                        (
                            "RADANCY_SOURCE_DATE"
                            if parsed_job[
                                "posted_raw"
                            ]
                            else "UNKNOWN"
                        ),

                         "source":
                         self.ats_name,
                })

                    accepted_this_page += 1

                print(
                    f"[RADANCY] "
                    f"{search_text!r} "
                    f"page {page}: "
                    f"{len(cards)} cards / "
                    f"{new_urls_this_page} new / "
                    f"{accepted_this_page} accepted"
            )

            # Repeated page / no new records.
                if new_urls_this_page == 0:
                    break

            # Safety cap.
                if page >= 30:
                    break

                page += 1

        print()
        print(
            f"[RADANCY TOTAL] "
            f"{employer_name}: "
            f"{len(jobs)} unique software jobs"
            )
        return jobs
