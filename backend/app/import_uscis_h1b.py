from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

from .database import get_connection
from .sponsorship.normalize import normalize_company_name


def clean(value) -> str:
    return str(value or "").strip()


def number(value) -> int:
    value = clean(value).replace(",", "")

    if not value:
        return 0

    try:
        return int(float(value))
    except (ValueError, TypeError):
        return 0


def parse_year(value) -> int | None:
    try:
        year = int(clean(value))
    except Exception:
        return None

    return year if 2000 <= year <= 2100 else None


def normalized_row(raw: dict) -> dict:
    return {
        clean(k): v
        for k, v in raw.items()
        if k is not None
    }


def fingerprint(values: dict) -> str:
    payload = json.dumps(
        values,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def import_file(path: Path) -> dict:
    stats = {
        "rows": 0,
        "imported": 0,
        "blank_employer": 0,
        "bad_year": 0,
        "exact_duplicates": 0,
        "errors": 0,
    }

    with path.open(
        "r",
        encoding="utf-16",
        newline="",
    ) as f:
        reader = csv.DictReader(
            f,
            delimiter="\t",
        )

        with get_connection() as conn:
            for source_row_number, raw in enumerate(
                reader,
                start=2,
            ):
                stats["rows"] += 1

                try:
                    row = normalized_row(raw)

                    employer = clean(
                        row.get("Employer (Petitioner) Name")
                    )

                    if not employer:
                        stats["blank_employer"] += 1
                        continue

                    year = parse_year(
                        row.get("Fiscal Year")
                    )

                    if year is None:
                        stats["bad_year"] += 1
                        continue

                    normalized_name = normalize_company_name(
                        employer
                    )

                    city = clean(
                        row.get("Petitioner City")
                    ) or None

                    state = clean(
                        row.get("Petitioner State")
                    ) or None

                    zipcode = clean(
                        row.get("Petitioner Zip Code")
                    ) or None

                    tax_id = clean(
                        row.get("Tax ID")
                    ) or None

                    naics = clean(
                        row.get("Industry (NAICS) Code")
                    ) or None

                    new_a = number(row.get("New Employment Approval"))
                    new_d = number(row.get("New Employment Denial"))

                    cont_a = number(row.get("Continuation Approval"))
                    cont_d = number(row.get("Continuation Denial"))

                    same_a = number(
                        row.get("Change with Same Employer Approval")
                    )
                    same_d = number(
                        row.get("Change with Same Employer Denial")
                    )

                    concurrent_a = number(
                        row.get("New Concurrent Approval")
                    )
                    concurrent_d = number(
                        row.get("New Concurrent Denial")
                    )

                    change_a = number(
                        row.get("Change of Employer Approval")
                    )
                    change_d = number(
                        row.get("Change of Employer Denial")
                    )

                    amended_a = number(row.get("Amended Approval"))
                    amended_d = number(row.get("Amended Denial"))

                    total_a = (
                        new_a
                        + cont_a
                        + same_a
                        + concurrent_a
                        + change_a
                        + amended_a
                    )

                    total_d = (
                        new_d
                        + cont_d
                        + same_d
                        + concurrent_d
                        + change_d
                        + amended_d
                    )

                    fingerprint_values = {
                        "normalized_name": normalized_name,
                        "fiscal_year": year,
                        "city": city,
                        "state": state,
                        "zip": zipcode,
                        "tax_id": tax_id,
                        "naics": naics,
                        "new_a": new_a,
                        "new_d": new_d,
                        "cont_a": cont_a,
                        "cont_d": cont_d,
                        "same_a": same_a,
                        "same_d": same_d,
                        "concurrent_a": concurrent_a,
                        "concurrent_d": concurrent_d,
                        "change_a": change_a,
                        "change_d": change_d,
                        "amended_a": amended_a,
                        "amended_d": amended_d,
                    }

                    row_fingerprint = fingerprint(
                        fingerprint_values
                    )

                    before = conn.total_changes

                    conn.execute("""
                        INSERT OR IGNORE INTO uscis_h1b_employer_history (
                            normalized_name,
                            display_name,
                            fiscal_year,

                            employer_city,
                            employer_state,
                            employer_zip,

                            tax_id,
                            naics_code,

                            new_employment_approvals,
                            new_employment_denials,

                            continuation_approvals,
                            continuation_denials,

                            same_employer_approvals,
                            same_employer_denials,

                            new_concurrent_approvals,
                            new_concurrent_denials,

                            change_employer_approvals,
                            change_employer_denials,

                            amended_approvals,
                            amended_denials,

                            initial_approvals,
                            initial_denials,

                            continuing_approvals,
                            continuing_denials,

                            total_approvals,
                            total_denials,

                            source,
                            source_file,
                            source_row_number,
                            row_fingerprint
                        )
                        VALUES (
                            ?, ?, ?,
                            ?, ?, ?,
                            ?, ?,
                            ?, ?,
                            ?, ?,
                            ?, ?,
                            ?, ?,
                            ?, ?,
                            ?, ?,
                            ?, ?,
                            ?, ?,
                            ?, ?,
                            'USCIS_H1B_EMPLOYER_DATA_HUB',
                            ?, ?, ?
                        )
                    """, (
                        normalized_name,
                        employer,
                        year,

                        city,
                        state,
                        zipcode,

                        tax_id,
                        naics,

                        new_a,
                        new_d,

                        cont_a,
                        cont_d,

                        same_a,
                        same_d,

                        concurrent_a,
                        concurrent_d,

                        change_a,
                        change_d,

                        amended_a,
                        amended_d,

                        new_a,
                        new_d,

                        cont_a,
                        cont_d,

                        total_a,
                        total_d,

                        path.name,
                        source_row_number,
                        row_fingerprint,
                    ))

                    if conn.total_changes > before:
                        stats["imported"] += 1
                    else:
                        stats["exact_duplicates"] += 1

                except Exception as exc:
                    stats["errors"] += 1

                    if stats["errors"] <= 10:
                        print(
                            "[USCIS IMPORT ERROR]",
                            source_row_number,
                            repr(exc),
                        )

            conn.commit()

    return stats


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Usage: python -m app.import_uscis_h1b "
            "data/uscis_h1b/<file>"
        )

    path = Path(sys.argv[1])

    if not path.exists():
        raise SystemExit(
            f"File not found: {path}"
        )

    result = import_file(path)

    print()
    print("=== USCIS IMPORT ===")

    for key, value in result.items():
        print(f"{key.upper():<20}", value)


if __name__ == "__main__":
    main()
