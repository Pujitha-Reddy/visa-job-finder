from .collect_registry import main as collect_main
from .sponsorship.enrich_v11 import enrich_all_jobs_v11
from .repository import recalculate_all_scores
from .sync_jobs_to_postgres import sync

def main():
    print("=== COLLECT ===")
    collect_main()
    print("=== SPONSOR V11 ===")
    print(enrich_all_jobs_v11())
    print("=== SCORE ONLY ===")
    print(recalculate_all_scores())
    print("=== SYNC ===")
    print(sync())
    print("DONE. Do not run app.rescore_v79. Run app.sponsor_coverage only as a report.")

if __name__ == "__main__":
    main()
