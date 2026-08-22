from __future__ import annotations

import re

from .database import get_connection


TECH_TERMS = {
    "software",
    "technology",
    "technologies",
    "systems",
    "digital",
    "data",
    "cloud",
    "cyber",
    "ai",
    "artificial intelligence",
    "platform",
    "semiconductor",
    "electronics",
    "computing",
    "internet",
    "network",
    "networks",
}

FINANCE_TERMS = {
    "bank",
    "financial",
    "finance",
    "capital",
    "payments",
    "payment",
    "securities",
    "investment",
    "investments",
    "insurance",
    "credit",
}

CONSULTING_TERMS = {
    "consulting",
    "consultancy",
    "solutions",
    "services",
    "staffing",
    "resources",
    "outsourcing",
}

INDUSTRIAL_TERMS = {
    "motor",
    "automotive",
    "aerospace",
    "manufacturing",
    "industrial",
    "energy",
    "engineering",
    "semiconductor",
}

HEALTH_TERMS = {
    "health",
    "healthcare",
    "medical",
    "pharma",
    "pharmaceutical",
    "clinic",
    "hospital",
    "biotech",
    "life sciences",
}

UNIVERSITY_TERMS = {
    "university",
    "college",
    "school",
    "institute",
    "laboratory",
    "lab",
    "research",
    "trustees",
}


KNOWN_BRAND_CATEGORIES = {
    # Technology / product / engineering
    "intel": "TECH_PRODUCT",
    "qualcomm": "TECH_PRODUCT",
    "ebay": "TECH_PRODUCT",
    "expedia": "TECH_PRODUCT",
    "arm": "TECH_PRODUCT",
    "hpe": "TECH_PRODUCT",
    "sap": "TECH_PRODUCT",
    "netflix": "TECH_PRODUCT",
    "bytedance": "TECH_PRODUCT",
    "tiktok": "TECH_PRODUCT",
    "mathworks": "TECH_PRODUCT",
    "applied materials": "TECH_PRODUCT",
    "micron": "TECH_PRODUCT",
    "lucid": "TECH_PRODUCT",
    "snap": "TECH_PRODUCT",
    "asml": "TECH_PRODUCT",
    "synopsys": "TECH_PRODUCT",
    "zoox": "TECH_PRODUCT",
    "cadence design systems": "TECH_PRODUCT",
    "waymo": "TECH_PRODUCT",
    "akamai": "TECH_PRODUCT",
    "marvell semiconductor": "TECH_PRODUCT",
    "arista networks": "TECH_PRODUCT",
    "keysight technologies": "TECH_PRODUCT",
    "western digital": "TECH_PRODUCT",
    "infineon": "TECH_PRODUCT",
    "samsung": "TECH_PRODUCT",
    "adp": "TECH_PRODUCT",

    # Finance / fintech / insurance
    "blackrock": "FINTECH_FINANCE",
    "fiserv": "FINTECH_FINANCE",
    "state street": "FINTECH_FINANCE",
    "geico": "FINTECH_FINANCE",
    "citizens financial": "FINTECH_FINANCE",
    "social finance": "FINTECH_FINANCE",
    "navy federal": "FINTECH_FINANCE",
    "bank of new york mellon": "FINTECH_FINANCE",
    "northwestern mutual": "FINTECH_FINANCE",
    "dfs corporate services": "FINTECH_FINANCE",

    # Consulting / IT services
    "deloitte": "CONSULTING_IT",
    "ey": "CONSULTING_IT",
    "ernst and young": "CONSULTING_IT",
    "boston consulting group": "CONSULTING_IT",
    "cgi": "CONSULTING_IT",
    "hexaware": "CONSULTING_IT",
    "l t technology services": "CONSULTING_IT",
    "infinite computer solutions": "CONSULTING_IT",
    "mphasis": "CONSULTING_IT",
    "tech mahindra": "CONSULTING_IT",
    "ust global": "CONSULTING_IT",
    "virtusa": "CONSULTING_IT",
    "ntt data": "CONSULTING_IT",
    "persistent systems": "CONSULTING_IT",
    "zensar": "CONSULTING_IT",
    "epam": "CONSULTING_IT",
    "kpit": "CONSULTING_IT",
    "system soft technologies": "CONSULTING_IT",
    "miracle software systems": "CONSULTING_IT",
    "tavant technologies": "CONSULTING_IT",

    # Healthcare / life sciences
    "amgen": "HEALTH_TECH",
    "regeneron": "HEALTH_TECH",
    "mayo clinic": "HEALTH_TECH",
    "aetna": "HEALTH_TECH",
    "eli lilly": "HEALTH_TECH",

    # Industrial / engineering
    "cummins": "INDUSTRIAL_TECH",
    "siemens": "INDUSTRIAL_TECH",
}


CATEGORY_SCORES = {
    "TECH_PRODUCT": 30,
    "FINTECH_FINANCE": 25,
    "CONSULTING_IT": 22,
    "INDUSTRIAL_TECH": 18,
    "HEALTH_TECH": 15,
    "UNIVERSITY_RESEARCH": 8,
    "OTHER": 5,
}


def normalize(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def contains_any(text: str, terms: set[str]) -> bool:
    return any(
        re.search(
            r"\b" + re.escape(term) + r"\b",
            text,
        )
        for term in terms
    )


def classify(name: str) -> tuple[str, int, str]:
    text = normalize(name)

    # 1. Audited brand classification
    matches = []

    for brand, category in KNOWN_BRAND_CATEGORIES.items():
        if (
            text == brand
            or text.startswith(brand + " ")
        ):
            matches.append(
                (
                    len(brand),
                    category,
                    brand,
                )
            )

    if matches:
        matches.sort(
            key=lambda x: x[0],
            reverse=True,
        )

        _, category, brand = matches[0]

        return (
            category,
            CATEGORY_SCORES[category],
            f"Audited employer classification: {brand}",
        )

    # 2. University / research
    if contains_any(
        text,
        UNIVERSITY_TERMS,
    ):
        return (
            "UNIVERSITY_RESEARCH",
            CATEGORY_SCORES["UNIVERSITY_RESEARCH"],
            "University/research organization",
        )

    # 3. Healthcare / life sciences
    if contains_any(
        text,
        HEALTH_TERMS,
    ):
        return (
            "HEALTH_TECH",
            CATEGORY_SCORES["HEALTH_TECH"],
            "Healthcare/life-sciences employer",
        )

    # 4. Finance / fintech
    if contains_any(
        text,
        FINANCE_TERMS,
    ):
        return (
            "FINTECH_FINANCE",
            CATEGORY_SCORES["FINTECH_FINANCE"],
            "Financial-services employer",
        )

    # 5. Consulting / IT services
    if contains_any(
        text,
        CONSULTING_TERMS,
    ):
        return (
            "CONSULTING_IT",
            CATEGORY_SCORES["CONSULTING_IT"],
            "Consulting/services organization",
        )

    # 6. Technology / product
    if contains_any(
        text,
        TECH_TERMS,
    ):
        return (
            "TECH_PRODUCT",
            CATEGORY_SCORES["TECH_PRODUCT"],
            "Technology/software terminology in employer identity",
        )

    # 7. Industrial / engineering
    if contains_any(
        text,
        INDUSTRIAL_TERMS,
    ):
        return (
            "INDUSTRIAL_TECH",
            CATEGORY_SCORES["INDUSTRIAL_TECH"],
            "Industrial/engineering organization",
        )

    return (
        "OTHER",
        CATEGORY_SCORES["OTHER"],
        "No strong software-employer signal from employer identity",
    )


def main():
    with get_connection() as conn:
        cols = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(combined_sponsor_universe)"
            ).fetchall()
        }

        additions = {
            "employer_relevance_band": "TEXT",
            "employer_relevance_score": "INTEGER NOT NULL DEFAULT 0",
            "employer_relevance_reason": "TEXT",
            "source_discovery_score": "REAL NOT NULL DEFAULT 0",
        }

        for name, definition in additions.items():
            if name not in cols:
                conn.execute(
                    f"""
                    ALTER TABLE combined_sponsor_universe
                    ADD COLUMN {name} {definition}
                    """
                )

        rows = [
            dict(r)
            for r in conn.execute("""
                SELECT
                    parent_key,
                    display_name,
                    combined_sponsor_score
                FROM combined_sponsor_universe
            """).fetchall()
        ]

        for row in rows:
            band, relevance, reason = classify(
                row["display_name"]
            )

            sponsor_score = float(
                row["combined_sponsor_score"]
                or 0
            )

            # Sponsor evidence remains dominant.
            #
            # Maximum:
            #   sponsor evidence 100 * 0.75 = 75
            #   relevance                = 30
            #
            # capped to 100.
            discovery_score = min(
                100.0,
                sponsor_score * 0.75
                + relevance,
            )

            conn.execute("""
                UPDATE combined_sponsor_universe
                SET employer_relevance_band=?,
                    employer_relevance_score=?,
                    employer_relevance_reason=?,
                    source_discovery_score=?,
                    updated_at=CURRENT_TIMESTAMP
                WHERE parent_key=?
            """, (
                band,
                relevance,
                reason,
                discovery_score,
                row["parent_key"],
            ))

        conn.commit()

    print(
        "EMPLOYER RELEVANCE CLASSIFIED:",
        len(rows),
    )


if __name__ == "__main__":
    main()
