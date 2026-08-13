from __future__ import annotations

import argparse
from pathlib import Path
import yaml

from .collectors.greenhouse import fetch_greenhouse_jobs
from .collectors.lever import fetch_lever_jobs
from .database import init_db
from .repository import save_jobs
from .analyzers.pipeline import analyze_job


ROOT = Path(__file__).resolve().parents[2]
COMPANIES_CONFIG = ROOT / "config" / "companies.yaml"


def load_companies() -> list[dict]:
    if not COMPANIES_CONFIG.exists():
        return []
    data = yaml.safe_load(COMPANIES_CONFIG.read_text(encoding="utf-8")) or {}
    return [c for c in data.get("companies", []) if c.get("enabled", True)]


def collect_all(target_titles_only: bool = True) -> dict:
    init_db()
    totals = {"boards": 0, "found": 0, "added": 0, "updated": 0, "errors": 0}

    for company in load_companies():
        ats = (company.get("ats") or "").lower()
        token = company.get("token")
        company_name = company.get("company")

        if not ats or not token or not company_name:
            totals["errors"] += 1
            continue

        try:
            if ats == "greenhouse":
                jobs = fetch_greenhouse_jobs(
                    token,
                    company_name,
                    target_titles_only=target_titles_only,
                )
            elif ats == "lever":
                jobs = fetch_lever_jobs(
                    token,
                    company_name,
                    target_titles_only=target_titles_only,
                )
            else:
                totals["errors"] += 1
                continue

            jobs = [analyze_job(job) for job in jobs]
            result = save_jobs(jobs)
            totals["boards"] += 1
            totals["found"] += result["found"]
            totals["added"] += result["added"]
            totals["updated"] += result["updated"]
            totals["errors"] += result["errors"]

        except Exception as exc:
            totals["boards"] += 1
            totals["errors"] += 1
            print(f"[ERROR] {company_name}: {exc}")

    return totals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--all-titles",
        action="store_true",
        help="Collect every title instead of only target software-engineering titles.",
    )
    args = parser.parse_args()

    result = collect_all(target_titles_only=not args.all_titles)
    print(result)


if __name__ == "__main__":
    main()
