from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches


class OracleHCMCollector(BaseCollector):
    ats_name = "ORACLE_HCM"

    VERSION = "11.13.18.05"

    @staticmethod
    def _text(value):
        text = str(value or "").strip()

        if not text:
            return ""

        # Oracle often returns ordinary plain text rather than HTML.
        # Avoid BeautifulSoup's MarkupResemblesLocatorWarning for
        # strings that resemble filenames/paths.
        if "<" not in text or ">" not in text:
            return text

        return BeautifulSoup(
            text,
            "html.parser",
        ).get_text(" ", strip=True)

    @staticmethod
    def _parse_date(value):
        if not value:
            return None

        raw = str(value).strip()

        for fmt in (
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ):
            try:
                dt = datetime.strptime(
                    raw.replace("Z", ""),
                    fmt,
                ).replace(
                    tzinfo=timezone.utc,
                )

                return dt.isoformat()

            except ValueError:
                pass

        try:
            dt = datetime.fromisoformat(
                raw.replace("Z", "+00:00")
            )

            if dt.tzinfo is None:
                dt = dt.replace(
                    tzinfo=timezone.utc
                )

            return dt.astimezone(
                timezone.utc
            ).isoformat()

        except Exception:
            return None

    @staticmethod
    def _config(source):
        """
        token format:

            <oracle-host>|<site-number>

        Examples:

            efds.fa.em5.oraclecloud.com|CX_1
            ibqbjb.fa.ocs.oraclecloud.com|CX_1
            jpmc.fa.oraclecloud.com|CX_1001
        """

        token = (
            source.get("token")
            or ""
        ).strip()

        if "|" not in token:
            raise RuntimeError(
                f"ORACLE_HCM source "
                f"{source.get('employer_name')} "
                "requires token=<host>|<site>."
            )

        host, site = token.split(
            "|",
            1,
        )

        host = host.strip()
        site = site.strip()

        if not host or not site:
            raise RuntimeError(
                "Invalid ORACLE_HCM token."
            )

        return host, site

    @staticmethod
    def _work_text(row):
        bits = []

        workplace = (
            row.get("WorkplaceType")
            or ""
        ).strip()

        if workplace:
            bits.append(
                f"Workplace type: {workplace}"
            )

        code = (
            row.get("WorkplaceTypeCode")
            or ""
        ).strip()

        if code:
            bits.append(
                f"Workplace type code: {code}"
            )

        return " | ".join(bits)

    def fetch(self, source):
        host, site = self._config(
            source
        )

        origin = f"https://{host}"

        endpoint = (
            origin
            + f"/hcmRestApi/resources/{self.VERSION}/"
              "recruitingCEJobRequisitions"
        )

        session = requests.Session()

        session.headers.update({
            "User-Agent": "visa-job-finder/1.0",
            "Accept": "application/json",
        })

        jobs = []

        # Oracle keyword search is intentionally broad/fuzzy.
        # We use a small query set, then apply title_matches()
        # locally and dedupe by requisition ID.
        keywords = (
            "software engineer",
            "software developer",
            "java developer",
        )

        limit = 25

        seen_external_ids = set()

        for keyword in keywords:
            offset = 0
            seen_page_signatures = set()

            while True:
                # Oracle finder variables after siteNumber use
                # commas, not semicolons.
                finder = (
                    "findReqs;"
                    f"siteNumber={site},"
                    f"keyword={keyword},"
                    f"offset={offset},"
                    f"limit={limit},"
                    "sortBy=POSTING_DATES_DESC"
                )

                response = session.get(
                    endpoint,
                    params={
                        "finder": finder,
                        "expand": "requisitionList",
                        "onlyData": "true",
                    },
                    timeout=30,
                )

                response.raise_for_status()

                payload = response.json()

                parents = (
                    payload.get("items")
                    or []
                )

                if not parents:
                    break

                parent = parents[0]

                rows = (
                    parent.get("requisitionList")
                    or []
                )

                total = int(
                    parent.get("TotalJobsCount")
                    or 0
                )

                if not rows:
                    break

                page_signature = tuple(
                    str(row.get("Id") or "")
                    for row in rows
                )

                if page_signature in seen_page_signatures:
                    print(
                        "[ORACLE_HCM PAGINATION WARNING] "
                        f"{source.get('employer_name')} / "
                        f"{keyword}: repeated page "
                        f"at offset={offset}; stopping."
                    )
                    break

                seen_page_signatures.add(
                    page_signature
                )

                for row in rows:
                    title = (
                        row.get("Title")
                        or ""
                    ).strip()

                    if not title_matches(title):
                        continue

                    external_id = str(
                        row.get("Id")
                        or ""
                    ).strip()

                    if not external_id:
                        continue

                    # The same requisition will often appear for
                    # multiple Oracle keyword searches.
                    if external_id in seen_external_ids:
                        continue

                    seen_external_ids.add(
                        external_id
                    )

                    posted = self._parse_date(
                        row.get("PostedDate")
                    )

                    location = (
                        row.get("PrimaryLocation")
                        or ""
                    ).strip()

                    country = (
                        row.get(
                            "PrimaryLocationCountry"
                        )
                        or ""
                    ).strip()

                    if (
                        country
                        and country.lower()
                        not in location.lower()
                    ):
                        location = (
                            f"{location}, {country}"
                            if location
                            else country
                        )

                    description_parts = []

                    short = self._text(
                        row.get(
                            "ShortDescriptionStr"
                        )
                    )

                    if short:
                        description_parts.append(
                            short
                        )

                    responsibilities = self._text(
                        row.get(
                            "ExternalResponsibilitiesStr"
                        )
                    )

                    if responsibilities:
                        description_parts.append(
                            responsibilities
                        )

                    qualifications = self._text(
                        row.get(
                            "ExternalQualificationsStr"
                        )
                    )

                    if qualifications:
                        description_parts.append(
                            qualifications
                        )

                    work_text = self._work_text(
                        row
                    )

                    if work_text:
                        description_parts.append(
                            work_text
                        )

                    description = "\n\n".join(
                        x
                        for x in description_parts
                        if x
                    )

                    public_url = (
                        origin
                        + "/hcmUI/CandidateExperience/"
                          f"en/sites/{site}/job/{external_id}"
                    )

                    jobs.append({
                        "external_id": external_id,
                        "source": "ORACLE_HCM",
                        "source_url": public_url,
                        "apply_url": public_url,
                        "company_name_raw":
                            source["employer_name"],
                        "source_type":
                            source.get("source_type"),
                        "ats": "ORACLE_HCM",
                        "title": title,
                        "description": description,
                        "location_raw": location,
                        "country": country,
                        "posted_at": posted,
                        "source_published_at": posted,
                        "source_updated_at": None,
                        "effective_posted_at": posted,
                        "freshness_confidence": (
                            "HIGH"
                            if posted
                            else "UNKNOWN"
                        ),
                        "freshness_source": (
                            "ORACLE_HCM_POSTED_DATE"
                            if posted
                            else "UNKNOWN"
                        ),
                    })

                offset += len(rows)

                if offset >= total:
                    break

        return jobs
