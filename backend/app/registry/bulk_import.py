from pathlib import Path
import csv
import yaml
from .repository import init_registry, upsert_employer, upsert_source

VALID_TYPES = {
    "DIRECT_EMPLOYER","STARTUP","STAFFING_AGENCY","RECRUITING_AGENCY","CONSULTING"
}
VALID_ATS = {
    "GREENHOUSE","LEVER","ASHBY","WORKABLE","SMARTRECRUITERS","WORKDAY","CUSTOM"
}

def _normalize(row):
    item = {str(k).strip().lower(): v for k, v in row.items()}
    company = (item.get("company") or item.get("name") or "").strip()
    if not company:
        return None

    source_type = (item.get("source_type") or "DIRECT_EMPLOYER").strip().upper()
    ats = (item.get("ats") or "CUSTOM").strip().upper()
    if source_type not in VALID_TYPES:
        source_type = "DIRECT_EMPLOYER"
    if ats not in VALID_ATS:
        ats = "CUSTOM"

    enabled_raw = item.get("enabled", False)
    if isinstance(enabled_raw, str):
        enabled = enabled_raw.strip().lower() in {"1","true","yes","y"}
    else:
        enabled = bool(enabled_raw)

    return {
        "company": company,
        "source_type": source_type,
        "ats": ats,
        "token": (item.get("token") or "").strip() or None,
        "careers_url": (item.get("careers_url") or "").strip() or None,
        "enabled": enabled,
        "notes": (item.get("notes") or "").strip() or None,
    }

def load_entries(path):
    path = Path(path)
    if path.suffix.lower() in {".yaml",".yml"}:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        rows = payload.get("companies", payload if isinstance(payload, list) else [])
    elif path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    else:
        raise ValueError("Registry file must be YAML or CSV")
    return [x for r in rows if (x := _normalize(r))]

def import_registry_file(path):
    init_registry()
    entries = load_entries(path)
    stats = {"rows":len(entries),"enabled":0,"disabled":0}
    for item in entries:
        employer_id = upsert_employer(
            item["company"], item["source_type"], item["careers_url"]
        )
        upsert_source(
            employer_id, item["ats"], item["token"], item["careers_url"],
            item["enabled"], item["notes"]
        )
        stats["enabled" if item["enabled"] else "disabled"] += 1
    return stats
