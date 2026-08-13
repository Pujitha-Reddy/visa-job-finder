from __future__ import annotations

import argparse
from .database import init_db
from .sponsorship.importers import import_dol_lca_csv, import_uscis_h1b_csv
from .sponsorship.enrich import enrich_all_jobs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dol", help="Path to a DOL LCA CSV file")
    parser.add_argument("--uscis", help="Path to a USCIS H-1B Employer Data Hub CSV file")
    parser.add_argument("--year", type=int, help="Fiscal year represented by the input file")
    parser.add_argument("--enrich", action="store_true", help="Recalculate sponsor history for stored jobs")
    args = parser.parse_args()

    init_db()

    if args.dol:
        print(import_dol_lca_csv(args.dol, source_year=args.year))

    if args.uscis:
        print(import_uscis_h1b_csv(args.uscis, source_year=args.year))

    if args.enrich:
        print(enrich_all_jobs())


if __name__ == "__main__":
    main()
