from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches


class ADPCollector(BaseCollector):
    ats_name = "ADP"

    FEED_URL = (
        "https://jobs.adp.com/en/jobs/xml/?rss=true"
    )

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "application/xml,"
            "text/xml,"
            "*/*"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    @staticmethod
    def _value(
        job,
        field: str,
    ) -> str:
        node = job.find(field)

        if (
            node is None
            or node.text is None
        ):
            return ""

        return node.text.strip()

    @staticmethod
    def _clean_html(
        value: str,
    ) -> str:
        if not value:
            return ""

        return BeautifulSoup(
            value,
            "html.parser",
        ).get_text(
            " ",
            strip=True,
        )

    @staticmethod
    def _parse_date(
        value: str,
    ):
        value = (
            value
            or ""
        ).strip()

        if not value:
            return None

        formats = (
            "%a, %d %b %Y %H:%M:%S GMT",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d",
        )

        for fmt in formats:
            try:
                dt = datetime.strptime(
                    value,
                    fmt,
                )

                if dt.tzinfo is None:
                    dt = dt.replace(
                        tzinfo=timezone.utc
                    )

                return (
                    dt.astimezone(
                        timezone.utc
                    ).isoformat()
                )

            except ValueError:
                continue

        return None

    @staticmethod
    def _location(
        row: dict,
    ) -> str:
        city = (
            row.get("city")
            or ""
        ).strip()

        state = (
            row.get("state")
            or ""
        ).strip()

        country = (
            row.get("country")
            or ""
        ).strip()

        pieces = []

        if city:
            pieces.append(city)

        if (
            state
            and state.lower()
            not in {
                city.lower(),
                country.lower(),
            }
        ):
            pieces.append(state)

        if country:
            pieces.append(country)

        return ", ".join(
            pieces
        )

    @staticmethod
    def _location_priority(
        row: dict,
    ):
        """
        Deterministic representative location selection.

        Prefer:
        1. U.S. location
        2. Explicit city rather than Home Office
        3. Location with state/country populated

        This is NOT the eligibility gate.
        It only chooses the best source representation
        for a canonical multi-location posting.
        """

        country = (
            row.get("country")
            or ""
        ).strip().lower()

        city = (
            row.get("city")
            or ""
        ).strip().lower()

        state = (
            row.get("state")
            or ""
        ).strip()

        us = country in {
            "united states",
            "united states of america",
            "usa",
            "us",
        }

        home_office = (
            "home office" in city
        )

        return (
            1 if us else 0,
            0 if home_office else 1,
            1 if state else 0,
            1 if country else 0,
        )

    @staticmethod
    def _all_locations_text(
        rows: list[dict],
    ) -> str:
        values = []

        for row in rows:
            location = ADPCollector._location(
                row
            )

            if (
                location
                and location not in values
            ):
                values.append(
                    location
                )

        return " | ".join(
            values
        )

    def _fetch_feed(
        self,
    ):
        r = requests.get(
            self.FEED_URL,
            headers=self.HEADERS,
            timeout=90,
        )

        r.raise_for_status()

        content_type = (
            r.headers.get(
                "content-type",
                "",
            ).lower()
        )

        if (
            "xml" not in content_type
            and not r.content.lstrip().startswith(
                b"<?xml"
            )
        ):
            raise RuntimeError(
                "ADP job feed did not return XML."
            )

        return r.content

    def fetch(
        self,
        source,
    ):
        employer_name = (
            source.get("employer_name")
            or "ADP"
        )

        content = self._fetch_feed()

        root = ET.fromstring(
            content
        )

        raw_nodes = root.findall(
            ".//job"
        )

        print(
            f"[ADP] feed records: "
            f"{len(raw_nodes)}"
        )

        # --------------------------------------------------
        # Parse all XML rows.
        # --------------------------------------------------

        rows = []

        for node in raw_nodes:
            row = {
                "title":
                    self._value(
                        node,
                        "title",
                    ),

                "date":
                    self._value(
                        node,
                        "date",
                    ),

                "lastactivitydate":
                    self._value(
                        node,
                        "lastactivitydate",
                    ),

                "requisitionid":
                    self._value(
                        node,
                        "requisitionid",
                    ),

                "referencenumber":
                    self._value(
                        node,
                        "referencenumber",
                    ),

                "apijobid":
                    self._value(
                        node,
                        "apijobid",
                    ),

                "url":
                    self._value(
                        node,
                        "url",
                    ),

                "company":
                    self._value(
                        node,
                        "company",
                    ),

                "city":
                    self._value(
                        node,
                        "city",
                    ),

                "state":
                    self._value(
                        node,
                        "state",
                    ),

                "country":
                    self._value(
                        node,
                        "country",
                    ),

                "postalcode":
                    self._value(
                        node,
                        "postalcode",
                    ),

                "description":
                    self._value(
                        node,
                        "description",
                    ),

                "jobtype":
                    self._value(
                        node,
                        "jobtype",
                    ),

                "category":
                    self._value(
                        node,
                        "category",
                    ),

                "remotetype":
                    self._value(
                        node,
                        "remotetype",
                    ),

                "sourcename":
                    self._value(
                        node,
                        "sourcename",
                    ),
            }

            if (
                not row["title"]
                or not row["url"]
            ):
                continue

            rows.append(
                row
            )

        # --------------------------------------------------
        # Group multi-location variants.
        #
        # API job ID is canonical where available.
        # Fall back to URL.
        # --------------------------------------------------

        groups = defaultdict(
            list
        )

        for row in rows:
            canonical_key = (
                row["apijobid"]
                or row["url"]
            )

            groups[
                canonical_key
            ].append(
                row
            )

        print(
            f"[ADP] canonical jobs: "
            f"{len(groups)}"
        )

        jobs = []

        title_rejected = 0

        for canonical_key, variants in groups.items():

            # ----------------------------------------------
            # All variants represent the same underlying
            # posting. Choose a deterministic primary row.
            # ----------------------------------------------

            variants.sort(
                key=self._location_priority,
                reverse=True,
            )

            primary = variants[0]

            title = (
                primary["title"]
                or ""
            ).strip()

            # Use the same application-wide title filter
            # as every other collector.
            if not title_matches(
                title
            ):
                title_rejected += 1
                continue

            description = (
                self._clean_html(
                    primary[
                        "description"
                    ]
                )
            )

            all_locations = (
                self._all_locations_text(
                    variants
                )
            )

            # Preserve all source locations in description
            # while giving the classifier one deterministic
            # primary location_raw.
            if (
                len(variants) > 1
                and all_locations
            ):
                description = (
                    description
                    + "\n\n"
                    + "ADP source locations: "
                    + all_locations
                ).strip()

            posted_raw = (
                primary[
                    "date"
                ]
            )

            posted_at = (
                self._parse_date(
                    posted_raw
                )
            )

            # If date is absent/unparseable, use the feed's
            # activity timestamp as a secondary source.
            posted_source = (
                "ADP_SOURCE_DATE"
            )

            if not posted_at:
                posted_at = (
                    self._parse_date(
                        primary[
                            "lastactivitydate"
                        ]
                    )
                )

                if posted_at:
                    posted_source = (
                        "ADP_LAST_ACTIVITY_DATE"
                    )

            location = (
                self._location(
                    primary
                )
            )

            jobs.append({
                "company_name_raw":
                    employer_name,

                "title":
                    title,

                "location_raw":
                    location,

                "description_raw":
                    description,

                "source_url":
                    primary[
                        "url"
                    ],

                # API job ID is canonical across
                # multi-location records.
                "source_job_id":
                    primary[
                        "apijobid"
                    ]
                    or primary[
                        "requisitionid"
                    ]
                    or primary[
                        "referencenumber"
                    ],

                "posted_at":
                    posted_at,

                "posted_at_confidence":
                    (
                        "HIGH"
                        if posted_at
                        else "UNKNOWN"
                    ),

                "posted_at_source":
                    (
                        posted_source
                        if posted_at
                        else "UNKNOWN"
                    ),

                "source":
                    self.ats_name,

                # Extra source metadata is harmless:
                # save_jobs() only persists schema fields
                # it understands.
                "adp_requisition_id":
                    primary[
                        "requisitionid"
                    ],

                "adp_reference_number":
                    primary[
                        "referencenumber"
                    ],

                "adp_job_type":
                    primary[
                        "jobtype"
                    ],

                "adp_category":
                    primary[
                        "category"
                    ],

                "adp_remote_type":
                    primary[
                        "remotetype"
                    ],

                "adp_location_count":
                    len(
                        variants
                    ),
            })

        print(
            f"[ADP] title-matched jobs: "
            f"{len(jobs)}"
        )

        print(
            f"[ADP] title rejected: "
            f"{title_rejected}"
        )

        return jobs