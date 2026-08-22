from __future__ import annotations

import re

from .database import get_connection
from .sponsorship.normalize import normalize_company_name


SUFFIXES = {
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


def simplified(value: str) -> str:
    """
    Conservative normalization for legal-entity grouping.

    Removes punctuation and trailing corporate suffixes,
    but does NOT use substring/fuzzy matching.
    """
    value = normalize_company_name(
        value or ""
    )

    tokens = re.findall(
        r"[a-z0-9]+",
        value.lower(),
    )

    while (
        tokens
        and tokens[-1] in SUFFIXES
    ):
        tokens.pop()

    return " ".join(tokens)


# ==========================================================
# AUDITED EXACT LEGAL-ENTITY -> PARENT BRAND MAPPINGS
#
# Keys are simplified() values.
#
# IMPORTANT:
# Do not use arbitrary substring matching here.
# A key only matches when the entire simplified legal entity
# equals the configured key.
# ==========================================================

PARENT_ALIASES = {
    # Deloitte
    "deloitte consulting": "Deloitte",
    "deloitte touche": "Deloitte",
    "deloitte and touche": "Deloitte",
    "deloitte tax": "Deloitte",
    "deloitte touche tohmatsu services": "Deloitte",
    "deloitte": "Deloitte",

    # Visa
    "visa technology operations": "Visa",
    "visa technology and operations": "Visa",
    "visa u s a": "Visa",

    # EY
    "ernst young u s": "EY",
    "ernst and young u s": "EY",
    "ernst young": "EY",
    "ernst and young": "EY",

    # PwC
    "pricewaterhousecoopers advisory services": "PwC",
    "pricewaterhousecoopers advisory services": "PwC",
    "pricewaterhousecoopers": "PwC",

    # Citi
    "citibank": "Citi",

    # GEICO
    "government employee insurance": "GEICO",

    # Qualcomm
    "qualcomm technologies": "Qualcomm",
    "qualcomm": "Qualcomm",

    # HPE
    "hewlett packard enterprise": "HPE",

    # HP
    "hp": "HP",
    "hp development": "HP",

    # ByteDance
    "bytedance": "ByteDance",

    # BlackRock
    "blackrock financial management": "BlackRock",
    "blackrock": "BlackRock",

    # UBS
    "ubs business solutions us": "UBS",
    "ubs": "UBS",

    # First Citizens
    "first citizens bank and trust": "First Citizens",

    # Fiserv
    "fiserv solutions": "Fiserv",
    "fiserv": "Fiserv",

    # SAP
    "sap america": "SAP",
    "sap": "SAP",

    # Intel
    "intel": "Intel",

    # eBay
    "ebay": "eBay",

    # Expedia
    "expedia": "Expedia",

    # Netflix
    "netflix": "Netflix",

    # Arm
    #
    # Exact only. Never substring-match "arm".
    "arm": "Arm",
    "arm inc": "Arm",

    # ASML
    "asml us": "ASML",
    "asml": "ASML",

    # Bloomberg
    "bloomberg": "Bloomberg",

    # Applied Materials
    "applied materials": "Applied Materials",

    # Eli Lilly
    "eli lilly": "Eli Lilly",

    # American Airlines
    "american airlines": "American Airlines",

    # ADP
    "adp technology services": "ADP",
    "adp": "ADP",

    # Snap
    #
    # Exact only. Never substring-match "snap".
    "snap": "Snap",

    # Palantir
    "palantir technologies": "Palantir",

    # Zoox
    "zoox": "Zoox",

    # Amgen
    "amgen": "Amgen",

    # Truist
    "truist bank": "Truist",

    # Fidelity
    "fidelity technology group d b a fidelity investments": "Fidelity",

    # McKinsey
    "mckinsey": "McKinsey",
    "mckinsey united states": "McKinsey",

    # BCG
    "boston consulting group": "Boston Consulting Group",

    # Uber
    "uber technologies": "Uber",

    # Charter
    "charter communications": "Charter Communications",

    # Regeneron
    "regeneron pharmaceuticals": "Regeneron",

    # MathWorks
    "the mathworks": "MathWorks",
    "mathworks": "MathWorks",

    # Siemens software
    "siemens industry software": "Siemens",

    # Barclays
    "barclays services": "Barclays",

    # Cummins
    "cummins": "Cummins",
}


def infer_parent(
    display_name: str,
):
    """
    Return:
        parent_key,
        parent_display_name,
        grouping_method

    Only exact audited aliases are collapsed.

    Everything else remains its own legal-entity parent until
    we have evidence that it belongs to another organization.
    """
    simp = simplified(
        display_name
    )

    parent = PARENT_ALIASES.get(
        simp
    )

    if parent:
        return (
            normalize_company_name(
                parent
            ),
            parent,
            "EXACT_ALIAS",
        )

    return (
        normalize_company_name(
            display_name
        ),
        display_name,
        "SELF",
    )


def strength_rank(
    value: str,
) -> int:
    return {
        "STRONG": 3,
        "MEDIUM": 2,
        "WEAK": 1,
        "UNKNOWN": 0,
    }.get(
        (value or "UNKNOWN").upper(),
        0,
    )


def priority_band(
    score: float,
) -> str:
    if score >= 80:
        return "TIER_1"

    if score >= 60:
        return "TIER_2"

    if score >= 40:
        return "TIER_3"

    return "LOW"


def main():
    with get_connection() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT *
                FROM sponsor_employer_universe
                """
            ).fetchall()
        ]

        groups: dict[str, dict] = {}

        for row in rows:
            (
                parent_key,
                parent_name,
                grouping_method,
            ) = infer_parent(
                row["display_name"]
            )

            group = groups.setdefault(
                parent_key,
                {
                    "display_name": parent_name,
                    "total_filings": 0,
                    "recent_filings": 0,
                    "legal_entity_count": 0,

                    "strongest_sponsor_strength":
                        "UNKNOWN",

                    "highest_priority_score":
                        0.0,

                    "already_in_registry":
                        0,

                    "matched_employer_id":
                        None,

                    "members": [],
                    "methods": set(),
                },
            )

            group[
                "total_filings"
            ] += int(
                row["total_filings"]
                or 0
            )

            group[
                "recent_filings"
            ] += int(
                row["recent_filings"]
                or 0
            )

            group[
                "legal_entity_count"
            ] += 1

            group[
                "highest_priority_score"
            ] = max(
                group[
                    "highest_priority_score"
                ],
                float(
                    row["priority_score"]
                    or 0
                ),
            )

            current_strength = group[
                "strongest_sponsor_strength"
            ]

            incoming_strength = (
                row["sponsor_strength"]
                or "UNKNOWN"
            )

            if (
                strength_rank(
                    incoming_strength
                )
                > strength_rank(
                    current_strength
                )
            ):
                group[
                    "strongest_sponsor_strength"
                ] = incoming_strength

            # --------------------------------------------------
            # Preserve operational-registry evidence.
            # --------------------------------------------------

            if row[
                "already_in_registry"
            ]:
                group[
                    "already_in_registry"
                ] = 1

                existing_id = group[
                    "matched_employer_id"
                ]

                incoming_id = row[
                    "matched_employer_id"
                ]

                if existing_id is None:
                    group[
                        "matched_employer_id"
                    ] = incoming_id

                elif (
                    incoming_id is not None
                    and incoming_id != existing_id
                ):
                    # Do NOT silently merge legal entities
                    # that map to two different registry
                    # employers.
                    raise RuntimeError(
                        "Parent grouping conflict: "
                        f"{parent_name!r} maps to "
                        f"registry employers "
                        f"{existing_id} and {incoming_id}"
                    )

            group[
                "members"
            ].append(
                row["normalized_name"]
            )

            group[
                "methods"
            ].add(
                grouping_method
            )

        # ======================================================
        # Rebuild derived parent tables.
        # ======================================================

        conn.execute(
            """
            DELETE FROM sponsor_parent_members
            """
        )

        conn.execute(
            """
            DELETE FROM sponsor_parent_groups
            """
        )

        for (
            parent_key,
            group,
        ) in groups.items():
            score = float(
                group[
                    "highest_priority_score"
                ]
            )

            conn.execute(
                """
                INSERT INTO sponsor_parent_groups (
                    parent_key,
                    display_name,

                    total_filings,
                    recent_filings,
                    legal_entity_count,

                    strongest_sponsor_strength,
                    highest_priority_score,
                    priority_band,

                    already_in_registry,
                    matched_employer_id,

                    source_resolution_status,

                    updated_at
                )
                VALUES (
                    ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?,
                    'UNRESOLVED',
                    CURRENT_TIMESTAMP
                )
                """,
                (
                    parent_key,
                    group[
                        "display_name"
                    ],

                    group[
                        "total_filings"
                    ],

                    group[
                        "recent_filings"
                    ],

                    group[
                        "legal_entity_count"
                    ],

                    group[
                        "strongest_sponsor_strength"
                    ],

                    score,

                    priority_band(
                        score
                    ),

                    group[
                        "already_in_registry"
                    ],

                    group[
                        "matched_employer_id"
                    ],
                ),
            )

            for normalized_name in group[
                "members"
            ]:
                conn.execute(
                    """
                    INSERT INTO sponsor_parent_members (
                        parent_key,
                        normalized_name
                    )
                    VALUES (?, ?)
                    """,
                    (
                        parent_key,
                        normalized_name,
                    ),
                )

        conn.commit()

    collapsed = (
        len(rows)
        - len(groups)
    )

    print(
        "LEGAL ENTITIES:",
        len(rows),
    )

    print(
        "PARENT GROUPS:",
        len(groups),
    )

    print(
        "COLLAPSED:",
        collapsed,
    )


if __name__ == "__main__":
    main()
