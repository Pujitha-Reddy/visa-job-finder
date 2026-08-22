from __future__ import annotations

import re

from .database import get_connection
from .registry.repository import conn as registry_conn
from .sponsorship.normalize import normalize_company_name


CORPORATE_SUFFIXES = {
    "inc",
    "incorporated",
    "llc",
    "llp",
    "lp",
    "ltd",
    "limited",
    "corp",
    "corporation",
    "company",
    "co",
    "plc",
    "na",
}


# Explicit legal-entity/brand relationships.
#
# Keep this conservative and auditable.
REGISTRY_ALIASES = {
    # Citi
    "citibank n a": "Citi",
    "citibank": "Citi",

    # Amazon
    "amazon com services": "Amazon",
    "amazon com services inc": "Amazon",
    "amazon development center u s": "Amazon",
    "amazon development center u s inc": "Amazon",
    "amazon data services": "Amazon",
    "amazon data services inc": "Amazon",
    "amazon web services": "Amazon",

    # Google
    "google": "Google",

    # Microsoft
    "microsoft": "Microsoft",

    # Apple
    "apple": "Apple",

    # Meta
    "meta platforms": "Meta",

    # JPMorgan
    "jpmorgan chase": "JPMorgan Chase",

    # Walmart
    "wal mart associates": "Walmart Global Tech",

    # Oracle
    "oracle america": "Oracle",

    # Fidelity
    "fidelity technology group d b a fidelity investments": "Fidelity",

    # Goldman Sachs
    "goldman sachs": "Goldman Sachs",
    "goldman sachs co": "Goldman Sachs",
    "goldman sachs services": "Goldman Sachs",
    "goldman sachs bank usa": "Goldman Sachs",

    # Bank of America
    "bank of america n a": "Bank of America",
    "bank of america": "Bank of America",

    # American Express
    "american express travel related services": "American Express",

    # Capital One
    "capital one services": "Capital One",
    "capital one national association": "Capital One",

    # U.S. Bank
    "u s bank national association": "U.S. Bank",

    # Salesforce
    "salesforce": "Salesforce",

    # Adobe
    "adobe": "Adobe",

    # NVIDIA
    "nvidia": "NVIDIA",

    # AMD
    "advanced micro devices": "AMD",

    # Ford
    "ford motor": "Ford",

    # T-Mobile
    "t mobile usa": "T-Mobile",

    # Cisco
    "cisco systems": "Cisco",

    # IBM
    "ibm": "IBM",

    # CVS
    "cvs shared services resources": "CVS Health",

    # Evernorth
    "cigna evernorth services": "Evernorth",

    # Comcast
    "comcast cable communications": "Comcast",

    # FedEx
    "federal express": "FedEx",

    # Lowe's
    "lowe s companies": "Lowe's",

    # Zoom
    "zoom communications": "Zoom",

    # Morgan Stanley
    "morgan stanley services group": "Morgan Stanley",

    # Wells Fargo
    "wells fargo bank": "Wells Fargo",

    # AT&T
    "at t services": "AT&T",

    # Charles Schwab
    "charles schwab company": "Charles Schwab",

    # Optum
    "optum services": "Optum",

    # Rivian
    "rivian automotive": "Rivian",

    # HCLTech
    "hcl america": "HCLTech",

    # Capgemini
    "capgemini america": "Capgemini",

    # Cognizant
    "cognizant technology solutions us": "Cognizant",

    # Walmart
    "walmart": "Walmart Global Tech",
}


def simplified(value: str) -> str:
    value = normalize_company_name(
        value or ""
    )

    tokens = re.findall(
        r"[a-z0-9]+",
        value.lower(),
    )

    while (
        tokens
        and tokens[-1] in CORPORATE_SUFFIXES
    ):
        tokens.pop()

    return " ".join(tokens)


def parent_name_match(
    sponsor_name: str,
    employers: list[dict],
):
    """
    Conservative containment match.

    This is only a fallback after exact and explicit
    alias matching.
    """
    sponsor = simplified(
        sponsor_name
    )

    candidates = []

    for employer in employers:
        candidate = simplified(
            employer["display_name"]
        )

        if not candidate:
            continue

        tokens = candidate.split()

        # Protect short ambiguous brands.
        if len(tokens) == 1:
            if len(candidate) < 5:
                continue

        pattern = (
            r"\b"
            + re.escape(candidate)
            + r"\b"
        )

        if re.search(pattern, sponsor):
            candidates.append(
                (
                    len(candidate),
                    employer,
                )
            )

    if not candidates:
        return None

    candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    best_length, best = candidates[0]

    if len(candidates) > 1:
        second_length, second = (
            candidates[1]
        )

        if (
            second_length == best_length
            and second["id"] != best["id"]
        ):
            return None

    return best


def main():
    # ======================================================
    # Registry
    # ======================================================

    with registry_conn() as c:
        employers = [
            dict(r)
            for r in c.execute("""
                SELECT
                    id,
                    canonical_name,
                    display_name
                FROM employers
                WHERE enabled=1
            """).fetchall()
        ]

    exact = {}
    simple = {}
    by_display = {}

    for employer in employers:
        display = employer["display_name"]

        exact[
            employer["canonical_name"]
        ] = employer

        exact[
            normalize_company_name(display)
        ] = employer

        simp = simplified(display)

        if simp:
            simple[simp] = employer

        by_display[
            display.lower()
        ] = employer

    counts = {
    "ALREADY_MATCHED": 0,
    "EXACT": 0,
    "SIMPLIFIED": 0,
    "ALIAS": 0,
    "UNMATCHED": 0,
}

    examples = []

    # ======================================================
    # Combined sponsor universe
    # ======================================================

    with get_connection() as c:
        rows = [
            dict(r)
            for r in c.execute("""
                SELECT *
                FROM combined_sponsor_universe
                ORDER BY
                    combined_sponsor_score DESC,
                    uscis_2025_approvals DESC,
                    dol_recent_filings DESC
            """).fetchall()
        ]

        for row in rows:
            if (
                row["already_in_registry"]
                and row["matched_employer_id"]
            ):
                counts["ALREADY_MATCHED"] += 1
                continue

            display = (
                row["display_name"]
                or ""
            )

            norm = normalize_company_name(
                display
            )

            simp = simplified(
                display
            )

            match = None
            method = None

            # ----------------------------------------------
            # 1. Exact normalized match
            # ----------------------------------------------

            match = exact.get(norm)

            if match:
                method = "EXACT"

            # ----------------------------------------------
            # 2. Simplified legal-name match
            # ----------------------------------------------

            if not match:
                match = simple.get(simp)

                if match:
                    method = "SIMPLIFIED"

            # ----------------------------------------------
            # 3. Audited aliases
            # ----------------------------------------------

            if not match:
                alias_display = REGISTRY_ALIASES.get(simp)

                if alias_display:
                    match = by_display.get(
                        alias_display.lower()
                    )

                    if match:
                        method = "ALIAS"

            # ----------------------------------------------
            # Persist deterministic match
            # ----------------------------------------------

            if match:
                counts[method] += 1

                c.execute("""
                    UPDATE combined_sponsor_universe
                    SET already_in_registry=1,
                        matched_employer_id=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE parent_key=?
                """, (
                    match["id"],
                    row["parent_key"],
                ))

                if len(examples) < 100:
                    examples.append(
                        (
                            display,
                            match["display_name"],
                            method,
                        )
                    )

            else:
                counts["UNMATCHED"] += 1

        c.commit()


    print(
        "REGISTRY EMPLOYERS:",
        len(employers),
    )

    print()
    print(
        "=== COMBINED SPONSOR MATCH COUNTS ==="
    )

    for key, value in counts.items():
        print(
            f"{key:<18}",
            value,
        )

    print()
    print(
        "=== NEW REGISTRY MATCHES ==="
    )

    for sponsor, employer, method in examples:
        print(
            f"{method:<14} | "
            f"{sponsor:<60} -> "
            f"{employer}"
        )


if __name__ == "__main__":
    main()
