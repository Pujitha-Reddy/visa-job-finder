from __future__ import annotations

from pathlib import Path
import pandas as pd

from .repository import add_sponsor_record


def _first_existing(columns, candidates):
    mapping = {str(c).strip().upper(): c for c in columns}
    for candidate in candidates:
        if candidate.upper() in mapping:
            return mapping[candidate.upper()]
    return None


def _to_int(value) -> int:
    try:
        if pd.isna(value):
            return 0
        return int(float(value))
    except Exception:
        return 0


def import_dol_lca_csv(path: str | Path, source_year: int | None = None) -> dict:
    """
    Flexible DOL LCA importer.

    The disclosure-file schemas can vary by fiscal year. We identify common
    employer-name and status fields instead of hard-coding one year's schema.
    """
    df = pd.read_csv(path, low_memory=False)

    employer_col = _first_existing(
        df.columns,
        ["EMPLOYER_NAME", "EMPLOYER_NAME_BUSINESS_NAME", "EMPLOYER"]
    )
    status_col = _first_existing(df.columns, ["CASE_STATUS", "STATUS"])

    if employer_col is None:
        raise ValueError("Could not locate an employer-name column in the DOL file.")

    if status_col is not None:
        statuses = df[status_col].astype(str).str.upper()
        df = df[statuses.str.contains("CERTIFIED", na=False)]

    grouped = df.groupby(employer_col, dropna=True).size()

    imported = 0
    for employer, count in grouped.items():
        name = str(employer).strip()
        if not name:
            continue
        add_sponsor_record(
            company_name=name,
            source="DOL",
            source_year=source_year,
            filings_count=int(count),
        )
        imported += 1

    return {"source": "DOL", "employers_imported": imported, "rows": len(df)}


def import_uscis_h1b_csv(path: str | Path, source_year: int | None = None) -> dict:
    """
    Flexible USCIS H-1B Employer Data Hub CSV importer.
    """
    df = pd.read_csv(path, low_memory=False)

    employer_col = _first_existing(
        df.columns,
        ["Employer", "Employer Name", "Employer_Name", "Petitioner Name"]
    )

    initial_approvals = _first_existing(
        df.columns,
        ["Initial Approval", "Initial Approvals", "Initial_Approval"]
    )
    continuing_approvals = _first_existing(
        df.columns,
        ["Continuing Approval", "Continuing Approvals", "Continuing_Approval"]
    )
    initial_denials = _first_existing(
        df.columns,
        ["Initial Denial", "Initial Denials", "Initial_Denial"]
    )
    continuing_denials = _first_existing(
        df.columns,
        ["Continuing Denial", "Continuing Denials", "Continuing_Denial"]
    )

    if employer_col is None:
        raise ValueError("Could not locate an employer-name column in the USCIS file.")

    imported = 0
    for employer, group in df.groupby(employer_col, dropna=True):
        name = str(employer).strip()
        if not name:
            continue

        approved = 0
        denied = 0
        for col in (initial_approvals, continuing_approvals):
            if col is not None:
                approved += int(group[col].map(_to_int).sum())

        for col in (initial_denials, continuing_denials):
            if col is not None:
                denied += int(group[col].map(_to_int).sum())

        filings = approved + denied

        add_sponsor_record(
            company_name=name,
            source="USCIS",
            source_year=source_year,
            filings_count=filings,
            approved_count=approved,
            denied_count=denied,
        )
        imported += 1

    return {"source": "USCIS", "employers_imported": imported, "rows": len(df)}
