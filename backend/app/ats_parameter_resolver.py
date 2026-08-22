from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests


@dataclass
class ResolvedATSParameters:
    ats: str
    careers_url: str
    token: str | None = None
    confidence: int = 0
    evidence: list[str] | None = None


class ATSParameterResolver:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/150.0 Safari/537.36"
                )
            }
        )

    def _fetch(self, url: str):
        try:
            response = self.session.get(
                url,
                timeout=20,
                allow_redirects=True,
            )
            return response
        except requests.RequestException:
            return None

    def resolve(
        self,
        ats: str,
        careers_url: str,
    ) -> ResolvedATSParameters | None:

        ats = (ats or "").upper()

        if ats == "EIGHTFOLD":
            return self._resolve_eightfold(careers_url)

        if ats == "WORKDAY":
            return self._resolve_workday(careers_url)

        if ats == "GREENHOUSE":
            return self._resolve_greenhouse(careers_url)

        if ats == "LEVER":
            return self._resolve_lever(careers_url)

        return None

    # =========================================================
    # Eightfold
    # =========================================================

    def _resolve_eightfold(
        self,
        careers_url: str,
    ):
        response = self._fetch(careers_url)

        if not response:
            return None

        final_url = response.url
        text = response.text

        parsed = urlparse(final_url)

        host = parsed.netloc.lower()

        evidence = []

        # Native Eightfold hosted career site.
        if "eightfold.ai" in host or "eightfold" in host:
            evidence.append(f"Eightfold hosted domain: {host}")

            return ResolvedATSParameters(
                ats="EIGHTFOLD",
                careers_url=final_url,
                token=host,
                confidence=100,
                evidence=evidence,
            )

        patterns = [
            r"https?://([a-zA-Z0-9.-]+\.eightfold\.ai)",
            r'["\']([^"\']+\.eightfold\.ai)["\']',
            r"https?://([a-zA-Z0-9.-]+)/(?:careers|career-site)",
        ]

        for pattern in patterns:
            matches = re.findall(
                pattern,
                text,
                flags=re.I,
            )

            for match in matches:
                value = match if isinstance(match, str) else match[0]

                if "eightfold" not in value.lower():
                    continue

                value = value.strip("/")

                evidence.append(f"Eightfold domain found: {value}")

                return ResolvedATSParameters(
                    ats="EIGHTFOLD",
                    careers_url=final_url,
                    token=value,
                    confidence=95,
                    evidence=evidence,
                )

        # Some branded Eightfold deployments use the
        # branded careers hostname as the domain parameter.
        lower = text.lower()

        if "eightfold" in lower or "eightfold.ai" in lower:
            evidence.append("Eightfold fingerprint present")
            evidence.append(f"Using branded host: {host}")

            return ResolvedATSParameters(
                ats="EIGHTFOLD",
                careers_url=final_url,
                token=host,
                confidence=75,
                evidence=evidence,
            )

        return None

    # =========================================================
    # Workday
    # =========================================================

    def _resolve_workday(
        self,
        careers_url: str,
    ):
        response = self._fetch(careers_url)

        if not response:
            return None

        text = response.text

        patterns = [
            (
                r"https?://"
                r"([a-zA-Z0-9-]+)\."
                r"(?:wd\d+|myworkdayjobs)\."
                r"com/"
                r"([a-zA-Z0-9_-]+)"
            ),
            (
                r"https?://"
                r"([a-zA-Z0-9-]+)\."
                r"myworkdayjobs\.com/"
                r"([a-zA-Z0-9_-]+)"
            ),
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.I,
            )

            if not match:
                continue

            tenant = match.group(1)
            site = match.group(2)

            discovered_url = match.group(0)

            token = f"{tenant}|{site}"

            return ResolvedATSParameters(
                ats="WORKDAY",
                careers_url=discovered_url,
                token=token,
                confidence=100,
                evidence=[
                    f"Workday tenant: {tenant}",
                    f"Workday site: {site}",
                ],
            )

        return None

    # =========================================================
    # Greenhouse
    # =========================================================

    def _resolve_greenhouse(
        self,
        careers_url: str,
    ):
        response = self._fetch(careers_url)

        if not response:
            return None

        text = response.text

        patterns = [
            r"boards\.greenhouse\.io/([a-zA-Z0-9_-]+)",
            r"job-boards\.greenhouse\.io/([a-zA-Z0-9_-]+)",
            r"boards-api\.greenhouse\.io/v1/boards/([a-zA-Z0-9_-]+)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.I,
            )

            if match:
                token = match.group(1)

                return ResolvedATSParameters(
                    ats="GREENHOUSE",
                    careers_url=careers_url,
                    token=token,
                    confidence=100,
                    evidence=[f"Greenhouse board token: {token}"],
                )

        return None

    # =========================================================
    # Lever
    # =========================================================

    def _resolve_lever(
        self,
        careers_url: str,
    ):
        response = self._fetch(careers_url)

        if not response:
            return None

        text = response.text

        patterns = [
            r"jobs\.lever\.co/([a-zA-Z0-9_-]+)",
            r"api\.lever\.co/v0/postings/([a-zA-Z0-9_-]+)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                text,
                flags=re.I,
            )

            if match:
                token = match.group(1)

                return ResolvedATSParameters(
                    ats="LEVER",
                    careers_url=careers_url,
                    token=token,
                    confidence=100,
                    evidence=[f"Lever token: {token}"],
                )

        return None
