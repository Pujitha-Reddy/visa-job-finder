from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector
from .common import title_matches


class EightfoldCollector(BaseCollector):
    ats_name = "EIGHTFOLD"

    @staticmethod
    def _text(value):
        return BeautifulSoup(
            str(value or ""),
            "html.parser",
        ).get_text(" ", strip=True)

    @staticmethod
    def _timestamp(value):
        if value in (None, ""):
            return None

        try:
            ts = float(value)
            return datetime.fromtimestamp(
                ts,
                tz=timezone.utc,
            ).isoformat()
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _csrf(html):
        soup = BeautifulSoup(html or "", "html.parser")
        meta = soup.find("meta", attrs={"name": "_csrf"})

        if meta:
            value = meta.get("content")
            if value:
                return value.strip()

        return None

    @staticmethod
    def _domain(source):
        # Store Eightfold's domain parameter in token.
        #
        # Examples:
        # Microsoft      -> microsoft.com
        # Morgan Stanley -> morganstanley.com
        # PayPal         -> paypal.com
        # John Deere     -> johndeere.com

        token = (source.get("token") or "").strip()

        if not token:
            raise RuntimeError(
                f"EIGHTFOLD source {source.get('employer_name')} "
                "requires token=domain."
            )

        return token

    def _session(self):
        session = requests.Session()

        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })

        return session

    def fetch(self, source):
        careers_url = (source.get("careers_url") or "").rstrip("/")

        if not careers_url:
            return []

        domain = self._domain(source)

        # careers_url should be the Eightfold /careers URL.
        if careers_url.endswith("/careers"):
            base = careers_url[:-8]
        else:
            base = careers_url
            careers_url = base + "/careers"

        session = self._session()

        # --------------------------------------------------
        # Bootstrap session + CSRF
        # --------------------------------------------------

        page = session.get(careers_url, timeout=30)
        page.raise_for_status()

        csrf = self._csrf(page.text)

        if not csrf:
            raise RuntimeError(
                f"EIGHTFOLD CSRF token not found for "
                f"{source.get('employer_name')}"
            )

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": careers_url,
            "X-CSRF-Token": csrf,
        }

        jobs = []
        start = 0

        while True:
            # ----------------------------------------------
            # Search
            # ----------------------------------------------

            response = session.get(
                base + "/api/pcsx/search",
                params={
                    "domain": domain,
                    "query": "software engineer",
                    "location": "",
                    "start": start,
                    "sort_by": "relevance",
                },
                headers=headers,
                timeout=30,
            )

            response.raise_for_status()

            # Eightfold may rotate the CSRF token.
            rotated = response.headers.get("x-csrf-token")

            if rotated:
                csrf = rotated
                headers["X-CSRF-Token"] = rotated

            payload = response.json()
            data = payload.get("data") or {}

            positions = data.get("positions") or []
            total = int(data.get("count") or 0)

            if not positions:
                break

            for raw in positions:
                title = (raw.get("name") or "").strip()

                if not title_matches(title):
                    continue

                position_id = raw.get("id")

                if position_id is None:
                    continue

                # ------------------------------------------
                # Detail enrichment
                # ------------------------------------------

                detail_data = {}

                try:
                    detail = session.get(
                        base + "/api/pcsx/position_details",
                        params={
                            "position_id": position_id,
                            "domain": domain,
                            "hl": "en",
                        },
                        headers={
                            "Accept": "application/json, text/plain, */*",
                            "Referer": (
                                base
                                + f"/careers/job/{position_id}"
                            ),
                            "X-CSRF-Token": csrf,
                        },
                        timeout=30,
                    )

                    detail.raise_for_status()

                    rotated = detail.headers.get("x-csrf-token")

                    if rotated:
                        csrf = rotated
                        headers["X-CSRF-Token"] = rotated

                    detail_payload = detail.json()
                    detail_data = detail_payload.get("data") or {}

                except Exception as exc:
                    print(
                        "[EIGHTFOLD DETAIL WARNING] "
                        f"{source.get('employer_name')} / "
                        f"{title}: {exc}"
                    )

                info = detail_data or raw

                # ------------------------------------------
                # Dates
                # ------------------------------------------

                posted_ts = (
                    info.get("postedTs")
                    or raw.get("postedTs")
                )

                published = self._timestamp(posted_ts)

                # ------------------------------------------
                # Location
                # ------------------------------------------

                standardized = (
                    info.get("standardizedLocations")
                    or raw.get("standardizedLocations")
                    or []
                )

                locations = (
                    info.get("locations")
                    or raw.get("locations")
                    or []
                )

                if standardized:
                    location = " | ".join(
                        str(x) for x in standardized if x
                    )
                elif locations:
                    location = " | ".join(
                        str(x) for x in locations if x
                    )
                else:
                    location = str(
                        info.get("location") or ""
                    ).strip()

                # ------------------------------------------
                # Description
                # ------------------------------------------

                description = self._text(
                    info.get("jobDescription") or ""
                )

                # Preserve useful Eightfold custom work
                # arrangement fields in the description so
                # downstream eligibility can inspect them.
                work_bits = []

                work_option = info.get("workLocationOption")
                if work_option:
                    work_bits.append(
                        f"Work location option: {work_option}"
                    )

                flexibility = info.get("locationFlexibility")
                if flexibility:
                    work_bits.append(
                        f"Location flexibility: {flexibility}"
                    )

                for key, value in info.items():
                    low = str(key).lower()

                    if (
                        key.startswith("efcustom")
                        and (
                            "work" in low
                            or "site" in low
                            or "remote" in low
                            or "location" in low
                        )
                    ):
                        if isinstance(value, list):
                            text = " ".join(
                                str(x) for x in value if x
                            )
                        else:
                            text = str(value or "").strip()

                        if text:
                            work_bits.append(text)

                if work_bits:
                    description = (
                        description
                        + "\n\n"
                        + " | ".join(work_bits)
                    ).strip()

                # ------------------------------------------
                # URLs
                # ------------------------------------------

                position_url = (
                    info.get("publicUrl")
                    or info.get("positionUrl")
                    or raw.get("positionUrl")
                    or f"/careers/job/{position_id}"
                )

                source_url = urljoin(
                    base + "/",
                    str(position_url).lstrip("/"),
                )

                apply_url = source_url

                actions = info.get("positionUserActions") or {}
                apply_action = actions.get("applyAction") or {}

                if apply_action.get("applyUrl"):
                    apply_url = apply_action["applyUrl"]

                # ------------------------------------------
                # External ID
                # ------------------------------------------

                external_id = str(
                    info.get("atsJobId")
                    or info.get("displayJobId")
                    or raw.get("atsJobId")
                    or raw.get("displayJobId")
                    or position_id
                )

                jobs.append({
                    "external_id": external_id,
                    "source": "EIGHTFOLD",
                    "source_url": source_url,
                    "apply_url": apply_url,
                    "company_name_raw": source["employer_name"],
                    "source_type": source.get("source_type"),
                    "ats": "EIGHTFOLD",
                    "title": title,
                    "description": description,
                    "location_raw": location,
                    "posted_at": published,
                    "source_published_at": published,
                    "source_updated_at": None,
                    "effective_posted_at": published,
                    "freshness_confidence": (
                        "HIGH" if published else "UNKNOWN"
                    ),
                    "freshness_source": (
                        "EIGHTFOLD_POSTED_TS"
                        if published
                        else "UNKNOWN"
                    ),
                })

            start += len(positions)

            if start >= total:
                break

        return jobs
