import argparse
from .sponsorship.dol_local_import import import_local_files

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fy2026", required=True)
    parser.add_argument("--fy2025", required=True)
    args = parser.parse_args()

    print(import_local_files(args.fy2026, args.fy2025))
