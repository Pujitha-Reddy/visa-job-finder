from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import re
import requests
from bs4 import BeautifulSoup


@dataclass
class SourceCandidate:
    employer_name: str
    careers_url: str
    ats: Optional[str]
    token: Optional[str]
    confidence: int
    evidence: str
    source_type: str


class SourceDiscoveryEngine:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/150.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    ATS_PATTERNS = {
        "WORKDAY": [
            r"myworkdayjobs\.com",
        ],
        "GREENHOUSE": [
            r"greenhouse\.io",
            r"boards-api\.greenhouse\.io",
            r"job-boards\.greenhouse\.io",
        ],
        "LEVER": [
            r"jobs\.lever\.co",
        ],
        "EIGHTFOLD": [
            r"eightfold\.ai",
        ],
        "SMARTRECRUITERS": [
            r"smartrecruiters\.com",
        ],
        "ASHBY": [
            r"jobs\.ashbyhq\.com",
        ],
        "PHENOM": [
            r"phenompeople\.com",
            r"CareerConnectResources",
            r"widgetApiEndpoint",
        ],
        "RADANCY": [
            r"talentbrew",
            r"tbcdn\.talentbrew\.com",
        ],
    }

    STATIC_EXTENSIONS = {
        ".css",
        ".js",
        ".mjs",
        ".map",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".ico",
        ".webp",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".pdf",
    }

    NEGATIVE_PATH_TERMS = (
        "/assets/",
        "/static/",
        "/images/",
        "/fonts/",
        "/gen/js/",
        "/gen/css/",
        "/_next/static/",
        "careerconnectresources/",
    )

    JOB_DETAIL_PATTERNS = (
        "/job/",
        "/jobdetail/",
        "/jobs/",
        "/position/",
    )

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def fetch(self, url: str):
        r = self.session.get(
            url,
            timeout=30,
            allow_redirects=True,
        )

        r.raise_for_status()

        return r

    def detect_ats(
        self,
        html: str,
        final_url: str,
    ):
        blob = (final_url + "\n" + html).lower()

        matches = []

        for ats, patterns in self.ATS_PATTERNS.items():
            for pattern in patterns:
                if re.search(
                    pattern,
                    blob,
                    flags=re.I,
                ):
                    matches.append(ats)
                    break

        return matches

    @staticmethod
    def _is_static_asset(
        url: str,
    ) -> bool:
        try:
            parsed = urlparse(url)

            path = (parsed.path or "").lower()

        except Exception:
            return True

        if any(term in path for term in SourceDiscoveryEngine.NEGATIVE_PATH_TERMS):
            return True

        for extension in SourceDiscoveryEngine.STATIC_EXTENSIONS:
            if path.endswith(extension):
                return True

        return False

    @staticmethod
    def _looks_like_job_detail(
        url: str,
    ) -> bool:
        low = (url or "").lower()

        # Strong detail patterns.
        if "/jobdetail/" in low:
            return True

        if re.search(
            r"/job/[^/?#]+",
            low,
        ):
            return True

        if re.search(
            r"/jobs/[^/?#]+",
            low,
        ):
            return True

        if re.search(
            r"/position/\d+",
            low,
        ):
            return True

        return False

    @staticmethod
    def _looks_like_source_surface(
        url: str,
    ) -> bool:
        if not url:
            return False

        if SourceDiscoveryEngine._is_static_asset(url):
            return False

        if SourceDiscoveryEngine._looks_like_job_detail(url):
            return False

        low = url.lower()

        signals = (
            "search-results",
            "search-jobs",
            "searchjobs",
            "job-search",
            "/careers",
            "/jobs",
            "/opportunities",
            "myworkdayjobs.com",
            "greenhouse.io",
            "lever.co",
            "eightfold.ai",
            "smartrecruiters.com",
            "ashbyhq.com",
        )

        return any(signal in low for signal in signals)

    def extract_candidate_urls(
        self,
        html: str,
        base_url: str,
    ):
        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        source_urls = set()
        job_detail_urls = set()

        for tag in soup.find_all(
            ["a", "script", "link"],
        ):
            value = (tag.get("href") or tag.get("src") or "").strip()

            if not value:
                continue

            try:
                full = urljoin(
                    base_url,
                    value,
                )

            except Exception:
                continue

            if self._is_static_asset(full):
                continue

            if self._looks_like_job_detail(full):
                job_detail_urls.add(full)
                continue

            if self._looks_like_source_surface(full):
                source_urls.add(full)

        return {
            "sources": sorted(source_urls),
            "job_details": sorted(job_detail_urls),
        }

    def discover(
        self,
        employer_name: str,
        seed_url: str,
    ):
        candidates = []

        try:
            r = self.fetch(seed_url)

        except Exception as exc:
            return [
                SourceCandidate(
                    employer_name=employer_name,
                    careers_url=seed_url,
                    ats=None,
                    token=None,
                    confidence=0,
                    evidence=(f"Fetch failed: {exc}"),
                    source_type="ERROR",
                )
            ]

        final_url = r.url

        # ======================================================
        # ATS fingerprint from actual careers surface
        # ======================================================

        ats_matches = self.detect_ats(
            r.text,
            final_url,
        )

        for ats in ats_matches:
            candidates.append(
                SourceCandidate(
                    employer_name=employer_name,
                    careers_url=final_url,
                    ats=ats,
                    token=None,
                    confidence=85,
                    evidence=(
                        "ATS fingerprint detected "
                        "on employer careers surface: "
                        f"{ats}"
                    ),
                    source_type="ATS_FINGERPRINT",
                )
            )

        # ======================================================
        # Extract useful source and job-detail links
        # ======================================================

        extracted = self.extract_candidate_urls(
            r.text,
            final_url,
        )

        source_urls = extracted["sources"]

        job_details = extracted["job_details"]

        # ======================================================
        # ATS-specific source URLs
        # ======================================================

        for url in source_urls:
            ats_for_url = self.detect_ats(
                "",
                url,
            )

            for ats in ats_for_url:
                candidates.append(
                    SourceCandidate(
                        employer_name=employer_name,
                        careers_url=url,
                        ats=ats,
                        token=None,
                        confidence=90,
                        evidence=("ATS source/search URL " f"discovered: {url}"),
                        source_type="ATS_URL",
                    )
                )

        # ======================================================
        # Generic source/search surfaces
        # ======================================================

        for url in source_urls:
            if self.detect_ats(
                "",
                url,
            ):
                continue

            candidates.append(
                SourceCandidate(
                    employer_name=employer_name,
                    careers_url=url,
                    ats=None,
                    token=None,
                    confidence=55,
                    evidence=(
                        "Potential generic job-search " f"surface discovered: {url}"
                    ),
                    source_type="GENERIC_SOURCE",
                )
            )

        # ======================================================
        # Job-detail evidence
        #
        # Job details themselves are NOT sources.
        # Repeated detail URLs prove the seed surface may be
        # collectible generically.
        # ======================================================

        if job_details:
            sample = job_details[:3]

            candidates.append(
                SourceCandidate(
                    employer_name=employer_name,
                    careers_url=final_url,
                    ats=None,
                    token=None,
                    confidence=min(
                        80,
                        55 + len(job_details),
                    ),
                    evidence=(
                        f"Careers surface exposes "
                        f"{len(job_details)} "
                        f"job-detail URLs. "
                        f"Sample={sample}"
                    ),
                    source_type="GENERIC_JOB_LIST",
                )
            )

        # ======================================================
        # Preserve careers surface itself
        # ======================================================

        candidates.append(
            SourceCandidate(
                employer_name=employer_name,
                careers_url=final_url,
                ats=None,
                token=None,
                confidence=30,
                evidence=("Reachable careers surface"),
                source_type="CAREERS_PAGE",
            )
        )

        # ======================================================
        # Deduplicate candidates
        # ======================================================

        deduped = {}

        for candidate in candidates:
            key = (
                candidate.careers_url,
                candidate.ats,
                candidate.source_type,
            )

            existing = deduped.get(key)

            if existing is None or candidate.confidence > existing.confidence:
                deduped[key] = candidate

        # ======================================================
        # Rank
        #
        # ATS URLs and fingerprints are intentionally preferred
        # over arbitrary generic source URLs.
        # ======================================================

        type_rank = {
            "ATS_URL": 0,
            "ATS_FINGERPRINT": 1,
            "GENERIC_JOB_LIST": 2,
            "GENERIC_SOURCE": 3,
            "CAREERS_PAGE": 4,
            "ERROR": 9,
        }

        return sorted(
            deduped.values(),
            key=lambda x: (
                type_rank.get(
                    x.source_type,
                    8,
                ),
                -x.confidence,
                len(x.careers_url or ""),
            ),
        )
