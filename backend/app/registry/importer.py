from pathlib import Path
import yaml
from .repository import init_registry, upsert_employer, upsert_source

def import_yaml(path):
    init_registry()
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    count = 0
    for item in payload.get("companies", []):
        employer_id = upsert_employer(
            item["company"],
            item.get("source_type", "DIRECT_EMPLOYER"),
            item.get("careers_url"),
        )
        upsert_source(
            employer_id,
            item.get("ats", "CUSTOM"),
            item.get("token"),
            item.get("careers_url"),
            item.get("enabled", True),
            item.get("notes"),
        )
        count += 1
    return {"imported": count}
