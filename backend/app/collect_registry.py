from .registry.repository import init_registry, list_enabled_sources, mark_source_result
from .collectors.factory import get_collector
from .classifiers.pipeline import analyze_job
from .jobs_repository import save_jobs

def main():
    init_registry()
    sources = list_enabled_sources()
    totals = {"sources": len(sources), "found": 0, "added": 0, "updated": 0, "errors": 0}

    for source in sources:
        collector = get_collector(source["ats"])
        if not collector:
            totals["errors"] += 1
            continue
        try:
            raw_jobs = collector.fetch(source)
            analyzed = [analyze_job(job) for job in raw_jobs]
            saved = save_jobs(analyzed)

            totals["found"] += saved["found"]
            totals["added"] += saved["added"]
            totals["updated"] += saved["updated"]
            totals["errors"] += saved["errors"]

            mark_source_result(source["source_id"], len(raw_jobs), True)
            print(
                f"{source['employer_name']} [{source['ats']}]: "
                f"{len(raw_jobs)} found / {saved['added']} added / {saved['updated']} updated"
            )
        except Exception as exc:
            totals["errors"] += 1
            mark_source_result(source["source_id"], 0, False)
            print(f"[ERROR] {source['employer_name']} [{source['ats']}]: {exc}")

    print(totals)

if __name__ == "__main__":
    main()
