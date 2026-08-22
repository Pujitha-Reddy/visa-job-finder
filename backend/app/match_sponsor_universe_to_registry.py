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


# Explicit parent/legal-entity aliases.
#
# Keep these intentionally small and auditable.
# These represent known legal-entity -> operational-brand mappings,
# not fuzzy guesses.
MANUAL_ALIASES = {
    # Amazon
    "amazon com services": "Amazon",
    "amazon web services": "Amazon",
    "amazon development center u s": "Amazon",
    "amazon data services": "Amazon",

    # Apple
    "apple": "Apple",

    # Cognizant
    "cognizant technology solutions us": "Cognizant",

    # Google
    "google": "Google",

    # Microsoft
    "microsoft": "Microsoft",

    # Meta
    "meta platforms": "Meta",

    # Consulting / IT services
    "infosys": "Infosys",
    "tata consultancy services": "Tata Consultancy Services",
    "wipro": "Wipro",
    "capgemini america": "Capgemini",
    "accenture": "Accenture",
    "hcl america": "HCLTech",

    # JPMorgan
    "jpmorgan chase": "JPMorgan Chase",

    # NVIDIA
    "nvidia": "NVIDIA",

    # PayPal
    "paypal": "PayPal",

    # Salesforce
    "salesforce": "Salesforce",

    # Walmart
    "wal mart associates": "Walmart Global Tech",

    # Adobe
    "adobe": "Adobe",

    # Cisco
    "cisco systems": "Cisco",

    # IBM
    "ibm": "IBM",

    # Citi
    "citibank": "Citi",

    # Goldman Sachs
    "goldman sachs": "Goldman Sachs",
    "goldman sachs co": "Goldman Sachs",
    "goldman sachs services": "Goldman Sachs",
    "goldman sachs bank usa": "Goldman Sachs",

    # Oracle
    "oracle america": "Oracle",

    # Capital One
    "capital one services": "Capital One",
    "capital one national association": "Capital One",

    # Intuit
    "intuit": "Intuit",

    # Ford
    "ford motor": "Ford",

    # GM
    "general motors": "General Motors",

    # Morgan Stanley
    "morgan stanley services group": "Morgan Stanley",

    # AT&T
    "at t services": "AT&T",

    # Wells Fargo
    "wells fargo bank": "Wells Fargo",

    # Rivian
    "rivian automotive": "Rivian",

    # AMD
    "advanced micro devices": "AMD",

    # U.S. Bank
    "u s bank national association": "U.S. Bank",

    # Palo Alto Networks
    "palo alto networks": "Palo Alto Networks",

    # Elevance
    "elevance health": "Elevance Health",

    # CVS
    "cvs shared services resources": "CVS Health",

    # T-Mobile
    "t mobile usa": "T-Mobile",

    # Cigna / Evernorth
    "cigna evernorth services": "Evernorth",

    # Kforce
    "kforce": "Kforce",

    # Fidelity
    "fidelity technology group d b a fidelity investments": "Fidelity",

    # Schwab
    "charles schwab company": "Charles Schwab",

    # Optum
    "optum services": "Optum",

    # Bank of America
    "bank of america": "Bank of America",

    # American Express
    "american express travel related services": "American Express",

    # FedEx
    "federal express": "FedEx",

    # Lowe's
    "lowe s companies": "Lowe's",

    # Zoom
    "zoom communications": "Zoom",

    # Comcast
    "comcast cable communications": "Comcast",
}


def simplified(value: str) -> str:
    """
    Normalize a company name further for legal-entity comparison.

    Example:
        "Apple Inc." -> "apple"
        "Capital One Services, LLC" -> "capital one services"
    """
    value = normalize_company_name(value or "")

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
    Conservative parent/brand containment matching.

    Examples:
        "Charles Schwab & Company, Inc."
            -> "Charles Schwab"

        "American Express Travel Related Services Company, Inc."
            -> "American Express"

    This intentionally avoids aggressive fuzzy matching.
    """
    sponsor_simple = simplified(
        sponsor_name
    )

    candidates = []

    for employer in employers:
        employer_simple = simplified(
            employer["display_name"]
        )

        if not employer_simple:
            continue

        # Avoid extremely short names.
        if len(employer_simple) < 4:
            continue

        employer_tokens = (
            employer_simple.split()
        )

        # --------------------------------------------------
        # Single-token brands
        # --------------------------------------------------

        if len(employer_tokens) == 1:
            # Five-character minimum protects against
            # overly broad matches such as short acronyms.
            if len(employer_simple) < 5:
                continue

            pattern = (
                r"\b"
                + re.escape(employer_simple)
                + r"\b"
            )

            if re.search(
                pattern,
                sponsor_simple,
            ):
                candidates.append(
                    (
                        len(employer_simple),
                        employer,
                    )
                )

        # --------------------------------------------------
        # Multi-word brands
        # --------------------------------------------------

        else:
            pattern = (
                r"\b"
                + re.escape(employer_simple)
                + r"\b"
            )

            if re.search(
                pattern,
                sponsor_simple,
            ):
                candidates.append(
                    (
                        len(employer_simple),
                        employer,
                    )
                )

    if not candidates:
        return None

    # Prefer the longest / most specific employer name.
    candidates.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    best_length, best = candidates[0]

    # If two different employers have equally specific
    # matches, refuse to guess.
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
    # Operational employer registry
    # ======================================================

    with registry_conn() as c:
        employers = [
            dict(r)
            for r in c.execute(
                """
                SELECT
                    id,
                    canonical_name,
                    display_name
                FROM employers
                WHERE enabled=1
                ORDER BY id
                """
            ).fetchall()
        ]

    exact = {}
    simple = {}
    by_display = {}

    for employer in employers:
        display = (
            employer["display_name"]
            or ""
        )

        canonical = (
            employer.get("canonical_name")
            or normalize_company_name(
                display
            )
        )

        by_display[
            display.lower()
        ] = employer

        exact[
            canonical
        ] = employer

        exact[
            normalize_company_name(
                display
            )
        ] = employer

        simp = simplified(display)

        if simp:
            simple[simp] = employer

    print(
        "REGISTRY EMPLOYERS:",
        len(employers),
    )

    # ======================================================
    # Sponsor universe
    # ======================================================

    with get_connection() as c:
        sponsors = [
            dict(r)
            for r in c.execute(
                """
                SELECT
                    normalized_name,
                    display_name,
                    priority_band,
                    priority_score,
                    recent_filings
                FROM sponsor_employer_universe
                ORDER BY
                    priority_score DESC,
                    recent_filings DESC
                """
            ).fetchall()
        ]

        counts = {
            "EXACT": 0,
            "SIMPLIFIED": 0,
            "MANUAL_ALIAS": 0,
            "PARENT_NAME": 0,
            "UNMATCHED": 0,
        }

        examples = []

        for sponsor in sponsors:
            raw_name = (
                sponsor["display_name"]
                or ""
            )

            norm = normalize_company_name(
                raw_name
            )

            simp = simplified(
                raw_name
            )

            match = None
            method = None

            # ==============================================
            # 1. Exact canonical match
            # ==============================================

            match = exact.get(norm)

            if match:
                method = "EXACT"

            # ==============================================
            # 2. Corporate suffix-normalized match
            # ==============================================

            if not match:
                match = simple.get(simp)

                if match:
                    method = "SIMPLIFIED"

            # ==============================================
            # 3. Explicit audited alias
            # ==============================================

            if not match:
                alias_display = (
                    MANUAL_ALIASES.get(
                        simp
                    )
                )

                if alias_display:
                    match = by_display.get(
                        alias_display.lower()
                    )

                    if match:
                        method = (
                            "MANUAL_ALIAS"
                        )

            # ==============================================
            # 4. Conservative parent/brand containment
            # ==============================================

            if not match:
                match = parent_name_match(
                    raw_name,
                    employers,
                )

                if match:
                    method = (
                        "PARENT_NAME"
                    )

            # ==============================================
            # MATCHED
            # ==============================================

            if match:
                counts[method] += 1

                note = (
                    f"Registry match: "
                    f"{method}"
                )

                # Avoid appending the same note every time
                # the matcher is rerun.
                c.execute(
                    """
                    UPDATE sponsor_employer_universe

                    SET matched_employer_id=?,
                        already_in_registry=1,

                        notes=CASE
                            WHEN notes IS NULL
                              OR notes=''
                            THEN ?

                            WHEN instr(
                                notes,
                                ?
                            ) > 0
                            THEN notes

                            ELSE
                                notes
                                || ' | '
                                || ?
                        END

                    WHERE normalized_name=?
                    """,
                    (
                        match["id"],
                        note,
                        note,
                        note,
                        sponsor[
                            "normalized_name"
                        ],
                    ),
                )

                if len(examples) < 75:
                    examples.append(
                        (
                            raw_name,
                            match[
                                "display_name"
                            ],
                            method,
                        )
                    )

            # ==============================================
            # UNMATCHED
            # ==============================================

            else:
                counts[
                    "UNMATCHED"
                ] += 1

                c.execute(
                    """
                    UPDATE sponsor_employer_universe

                    SET matched_employer_id=NULL,
                        already_in_registry=0

                    WHERE normalized_name=?
                    """,
                    (
                        sponsor[
                            "normalized_name"
                        ],
                    ),
                )

        c.commit()

    # ======================================================
    # Output
    # ======================================================

    print()
    print(
        "=== MATCH COUNTS ==="
    )

    for key, value in counts.items():
        print(
            f"{key:<14}",
            value,
        )

    print()
    print(
        "=== MATCH EXAMPLES ==="
    )

    for (
        sponsor,
        employer,
        method,
    ) in examples:
        print(
            f"{method:<14} | "
            f"{sponsor:<60} "
            f"-> {employer}"
        )

    total_matched = (
        counts["EXACT"]
        + counts["SIMPLIFIED"]
        + counts["MANUAL_ALIAS"]
        + counts["PARENT_NAME"]
    )

    print()
    print(
        "TOTAL MATCHED:",
        total_matched,
    )

    print(
        "TOTAL UNMATCHED:",
        counts["UNMATCHED"],
    )


if __name__ == "__main__":
    main()