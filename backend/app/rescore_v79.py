from .sponsorship.enrich_v2 import enrich_all_jobs_v2
from .repository import recalculate_all_scores

if __name__ == "__main__":
    print("Sponsor enrichment:", enrich_all_jobs_v2())
    print("Overall scoring:", recalculate_all_scores())
