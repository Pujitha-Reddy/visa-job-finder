from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
import requests

from .registry.repository import conn, init_registry, upsert_source

CACHE_PATH = Path(__file__).resolve().parents[1] / "data" / "source_discovery_cache.json"

def load_cache():
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}

def save_cache(cache):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

def slug_candidates(company: str) -> list[str]:
    cleaned = re.sub(r"[^a-z0-9]+", " ", company.lower()).strip()
    words = cleaned.split()
    drop = {"inc","llc","corp","corporation","company","co","group","technologies","technology"}
    reduced = [w for w in words if w not in drop]
    variants = {
        "".join(words),
        "-".join(words),
        "".join(reduced),
        "-".join(reduced),
    }
    return [v for v in variants if v]

def _get_json(url, params=None):
    r = requests.get(url, params=params, timeout=12, headers={"User-Agent":"visa-job-finder/1.0"})
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except Exception:
        return None

def probe_greenhouse(token):
    data = _get_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        count = len(data["jobs"])
        if count == 0:
            return None
        return {"ats":"GREENHOUSE","token":token,"jobs":count}
    return None

def probe_lever(token):
    data = _get_json(f"https://api.lever.co/v0/postings/{token}", {"mode":"json"})
    if isinstance(data, list):
        count = len(data)
        if count == 0:
            return None
        return {"ats":"LEVER","token":token,"jobs":count}
    return None

def probe_ashby(token):
    data = _get_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    if isinstance(data, dict) and isinstance(data.get("jobs"), list):
        count = len(data["jobs"])
        if count == 0:
            return None
        return {"ats":"ASHBY","token":token,"jobs":count}
    return None

def probe_workable(token):
    data = _get_json(f"https://www.workable.com/api/accounts/{token}")
    if isinstance(data, dict) and isinstance(data.get("jobs"), list) and len(data["jobs"]) > 0:
        return {"ats":"WORKABLE","token":token,"jobs":len(data["jobs"])}
    return None

def probe_smartrecruiters(token):
    data = _get_json(
        f"https://api.smartrecruiters.com/v1/companies/{token}/postings",
        {"limit": 1, "offset": 0, "destination": "PUBLIC"},
    )

    if (
        isinstance(data, dict)
        and isinstance(data.get("content"), list)
        and int(data.get("totalFound") or 0) > 0
    ):
        return {
            "ats": "SMARTRECRUITERS",
            "token": token,
            "jobs": int(data.get("totalFound") or len(data["content"])),
        }

    return None

PROBES = [probe_greenhouse, probe_lever, probe_ashby, probe_workable, probe_smartrecruiters]

def discover_for_company(company, cache, pause=0.10):
    key = company.lower()
    if key in cache:
        return cache[key]

    found = []
    for token in slug_candidates(company):
        for probe in PROBES:
            try:
                result = probe(token)
                if result:
                    found.append(result)
            except Exception:
                pass
            time.sleep(pause)

    unique = {(r["ats"], r["token"]): r for r in found}
    cache[key] = list(unique.values())
    return cache[key]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--refresh-cache", action="store_true")
    args = parser.parse_args()

    init_registry()
    cache = {} if args.refresh_cache else load_cache()

    with conn() as c:
        employers = [dict(r) for r in c.execute("""
            SELECT id, display_name, source_type
            FROM employers
            ORDER BY display_name
        """).fetchall()]

    batch = employers[args.offset:args.offset + args.batch_size]
    stats = {"checked":0,"companies_with_source":0,"verified_sources":0,"offset":args.offset}

    for employer in batch:
        company = employer["display_name"]
        stats["checked"] += 1
        found = discover_for_company(company, cache)

        if not found:
            print(f"UNRESOLVED: {company}")
            continue

        stats["companies_with_source"] += 1
        for src in found:
            upsert_source(
                employer["id"], src["ats"], src["token"], None, True,
                "Auto-discovered by successful public ATS API probe."
            )
            with conn() as c:
                c.execute("""
                    UPDATE employer_sources
                    SET source_verified=1, enabled=1, active_jobs=?,
                        last_checked_at=CURRENT_TIMESTAMP,
                        last_success_at=CURRENT_TIMESTAMP
                    WHERE employer_id=? AND ats=? AND token=?
                """, (src["jobs"], employer["id"], src["ats"], src["token"]))
                c.commit()
            stats["verified_sources"] += 1
            print(f"VERIFIED: {company} -> {src['ats']} / {src['token']} ({src['jobs']} jobs)")

    save_cache(cache)
    print(stats)

if __name__ == "__main__":
    main()
