from __future__ import annotations
import re
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

TRACKING_PARAMS = {
    "gh_src","lever-origin","lever-source","source","src","utm_source",
    "utm_medium","utm_campaign","utm_term","utm_content","ref","referrer"
}

def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    p = urlparse(url.strip())
    q = [(k,v) for k,v in parse_qsl(p.query, keep_blank_values=True)
         if k.lower() not in TRACKING_PARAMS]
    path = re.sub(r"/+$", "", p.path or "")
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(q), ""))

def normalize_text(value: str | None) -> str:
    s = (value or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def semantic_dedupe_key(job: dict) -> str:
    # Cross-ATS semantic key. Keep seniority words; don't merge Senior with non-Senior.
    return "|".join([
        normalize_text(job.get("company_name_raw")),
        normalize_text(job.get("title")),
        normalize_text(job.get("location_raw")),
    ])

def dedupe_key(job: dict) -> str:
    # Prefer semantic key so the same employer/title/location from two ATSs collapses.
    semantic = semantic_dedupe_key(job)
    if semantic.replace("|", ""):
        return semantic

    url = normalize_url(job.get("source_url") or job.get("apply_url"))
    if url:
        return f"url:{url}"

    ext = (job.get("external_id") or "").strip()
    company = normalize_text(job.get("company_name_raw"))
    return f"{company}|external:{ext}" if ext else ""

def source_priority(job: dict) -> int:
    st = (job.get("source_type") or "").upper()
    return {
        "DIRECT_EMPLOYER": 40,
        "STARTUP": 35,
        "CONSULTING": 20,
        "STAFFING_AGENCY": 10,
    }.get(st, 0)

def freshness_priority(job: dict) -> int:
    return {"HIGH":30, "MEDIUM":15, "UNKNOWN":0}.get(
        (job.get("freshness_confidence") or "").upper(), 0
    )

def authenticity_priority(job: dict) -> int:
    return {"VERIFIED_ORIGINAL":20, "HIGH_CONFIDENCE":10, "NEEDS_REVIEW":0}.get(
        (job.get("source_confidence_label") or "").upper(), 0
    )

def rank_bonus(job: dict) -> int:
    return source_priority(job) + freshness_priority(job) + authenticity_priority(job)
