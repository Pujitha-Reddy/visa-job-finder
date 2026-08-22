from __future__ import annotations

import re


# ==========================================================
# EXPERIENCE EXTRACTION
# ==========================================================

YEAR_PATTERNS = (
    # 3-5 years / 3 to 5 years
    re.compile(
        r"\b(\d{1,2})\s*(?:-|–|—|to)\s*(\d{1,2})"
        r"\+?\s+years?(?:\s+of)?\s+(?:relevant\s+)?experience\b",
        re.I,
    ),

    # 3+ years
    re.compile(
        r"\b(\d{1,2})\s*\+\s+years?(?:\s+of)?"
        r"\s+(?:relevant\s+)?experience\b",
        re.I,
    ),

    # at least 3 years
    re.compile(
        r"\b(?:at\s+least|minimum(?:\s+of)?|min\.?)\s+"
        r"(\d{1,2})\s+years?(?:\s+of)?"
        r"\s+(?:relevant\s+)?experience\b",
        re.I,
    ),

    # 3 years of experience
    re.compile(
        r"\b(\d{1,2})\s+years?(?:\s+of)?"
        r"\s+(?:relevant\s+|professional\s+|industry\s+)?"
        r"experience\b",
        re.I,
    ),

    # experience: 3 years
    re.compile(
        r"\bexperience\s*[:\-]?\s*"
        r"(\d{1,2})\+?\s+years?\b",
        re.I,
    ),
)


def normalize(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def extract_years(description):
    text = normalize(
        description
    )

    if not text:
        return {
            "min": None,
            "max": None,
            "evidence": None,
            "confidence": 0.0,
        }

    candidates = []

    # ------------------------------------------------------
    # Range pattern
    # ------------------------------------------------------

    range_pattern = YEAR_PATTERNS[0]

    for match in range_pattern.finditer(
        text
    ):
        low = float(
            match.group(1)
        )

        high = float(
            match.group(2)
        )

        if (
            low <= high
            and high <= 30
        ):
            candidates.append(
                {
                    "min": low,
                    "max": high,
                    "evidence": match.group(0),
                    "confidence": 0.98,
                }
            )

    # ------------------------------------------------------
    # Minimum/single-year patterns
    # ------------------------------------------------------

    for pattern in YEAR_PATTERNS[1:]:
        for match in pattern.finditer(
            text
        ):
            value = float(
                match.group(1)
            )

            if value > 30:
                continue

            candidates.append(
                {
                    "min": value,
                    "max": None,
                    "evidence": match.group(0),
                    "confidence": 0.95,
                }
            )

    if not candidates:
        return {
            "min": None,
            "max": None,
            "evidence": None,
            "confidence": 0.0,
        }

    # Conservative:
    # use the lowest explicit minimum because descriptions
    # can mention optional/preferred higher experience later.
    candidates.sort(
        key=lambda item: (
            item["min"],
            item["max"]
            if item["max"] is not None
            else 999,
        )
    )

    return candidates[0]


# ==========================================================
# SENIORITY
# ==========================================================


def classify_title_seniority(title):
    text = normalize(
        title
    ).lower()

    if not text:
        return (
            "UNKNOWN",
            0.0,
            "EMPTY_TITLE",
        )

    # ------------------------------------------------------
    # Internship / student
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"intern|internship|co-op|coop|student"
        r")\b",
        text,
    ):
        return (
            "INTERN",
            0.99,
            "TITLE:INTERN",
        )

    # ------------------------------------------------------
    # Executive / director
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"vice president|vp|director|head of|"
        r"chief technology officer|cto"
        r")\b",
        text,
    ):
        return (
            "EXECUTIVE",
            0.99,
            "TITLE:EXECUTIVE",
        )

    # ------------------------------------------------------
    # Manager
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"manager|engineering manager|"
        r"development manager"
        r")\b",
        text,
    ):
        return (
            "MANAGER",
            0.98,
            "TITLE:MANAGER",
        )

    # ------------------------------------------------------
    # Principal / distinguished
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"principal|distinguished|architect"
        r")\b",
        text,
    ):
        return (
            "PRINCIPAL",
            0.97,
            "TITLE:PRINCIPAL",
        )

    # ------------------------------------------------------
    # Staff
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"staff|sr staff|senior staff"
        r")\b",
        text,
    ):
        return (
            "STAFF",
            0.97,
            "TITLE:STAFF",
        )

    # ------------------------------------------------------
    # Lead
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"lead|tech lead|technical lead"
        r")\b",
        text,
    ):
        return (
            "LEAD",
            0.95,
            "TITLE:LEAD",
        )

    # ------------------------------------------------------
    # Senior
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"senior|sr\.?|level iv|level 4|"
        r"engineer iv"
        r")\b",
        text,
    ):
        return (
            "SENIOR",
            0.95,
            "TITLE:SENIOR",
        )

    # ------------------------------------------------------
    # Early career
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"new grad|new graduate|graduate|"
        r"early career|entry level|entry-level|"
        r"junior|jr\.?"
        r")\b",
        text,
    ):
        return (
            "EARLY_CAREER",
            0.98,
            "TITLE:EARLY_CAREER",
        )

    # ------------------------------------------------------
    # Numbered levels
    # ------------------------------------------------------

    if re.search(
        r"\b("
        r"engineer i|software engineer i|"
        r"developer i|level 1|level i"
        r")\b",
        text,
    ):
        return (
            "EARLY_CAREER",
            0.95,
            "TITLE:LEVEL_1",
        )

    if re.search(
        r"\b("
        r"engineer ii|software engineer ii|"
        r"developer ii|level 2|level ii"
        r")\b",
        text,
    ):
        return (
            "MID",
            0.92,
            "TITLE:LEVEL_2",
        )

    if re.search(
        r"\b("
        r"engineer iii|software engineer iii|"
        r"developer iii|level 3|level iii"
        r")\b",
        text,
    ):
        return (
            "MID",
            0.90,
            "TITLE:LEVEL_3",
        )

    # Associate often means early/mid level in the
    # finance/consulting employers in our corpus.
    if re.search(
        r"\bassociate\b",
        text,
    ):
        return (
            "MID",
            0.80,
            "TITLE:ASSOCIATE",
        )

    return (
        "UNKNOWN",
        0.40,
        "NO_TITLE_SENIORITY",
    )


def enrich_experience(
    *,
    title,
    description,
):
    years = extract_years(
        description
    )

    (
        title_band,
        title_confidence,
        title_reason,
    ) = classify_title_seniority(
        title
    )

    explicit_min = years["min"]
    explicit_max = years["max"]

    # ======================================================
    # HARD TITLE SENIORITY
    #
    # Do not let a stray requirement such as:
    #
    #   "1+ year with AWS"
    #
    # turn:
    #
    #   Senior Manager
    #   Staff Engineer
    #   Principal Engineer
    #
    # into an early-career job.
    # ======================================================

    hard_title_bands = {
        "INTERN",
        "EXECUTIVE",
        "MANAGER",
        "PRINCIPAL",
        "STAFF",
        "LEAD",
    }

    if title_band in hard_title_bands:
        reason = title_reason

        if explicit_min is not None:
            reason += (
                ";EXPLICIT_YEARS_FOUND:"
                + str(years["evidence"])
            )

        return {
            "min_experience_years": explicit_min,
            "max_experience_years": explicit_max,

            "seniority_band": title_band,

            "experience_confidence": max(
                title_confidence,
                years["confidence"],
            ),

            "experience_reason": reason,
        }

    # ======================================================
    # SENIOR TITLE
    #
    # Explicit years may refine a senior title, but should
    # not demote it all the way to early career merely
    # because the description contains a small skill-specific
    # year requirement.
    # ======================================================

    if title_band == "SENIOR":

        if explicit_min is None:
            return {
                "min_experience_years": None,
                "max_experience_years": None,
                "seniority_band": "SENIOR",
                "experience_confidence": title_confidence,
                "experience_reason": title_reason,
            }

        if explicit_min >= 7:
            band = "HIGH_EXPERIENCE"

        elif explicit_min >= 4:
            band = "EXPERIENCED"

        else:
            band = "SENIOR"

        return {
            "min_experience_years": explicit_min,
            "max_experience_years": explicit_max,
            "seniority_band": band,

            "experience_confidence": max(
                title_confidence,
                years["confidence"],
            ),

            "experience_reason": (
                f"{title_reason};"
                f"EXPLICIT_YEARS:{years['evidence']}"
            ),
        }

    # ======================================================
    # MID / EARLY / UNKNOWN
    #
    # Here explicit years are our strongest signal.
    # ======================================================

    if explicit_min is not None:

        if explicit_min <= 1:
            band = "EARLY_CAREER"

        elif explicit_min <= 3:
            band = "MID"

        elif explicit_min <= 6:
            band = "EXPERIENCED"

        else:
            band = "HIGH_EXPERIENCE"

        return {
            "min_experience_years": explicit_min,
            "max_experience_years": explicit_max,

            "seniority_band": band,

            "experience_confidence": (
                years["confidence"]
            ),

            "experience_reason": (
                "EXPLICIT_YEARS:"
                + str(
                    years["evidence"]
                )
            ),
        }

    # ======================================================
    # No explicit experience requirement.
    # Use title classification.
    # ======================================================

    return {
        "min_experience_years": None,
        "max_experience_years": None,

        "seniority_band": title_band,

        "experience_confidence": (
            title_confidence
        ),

        "experience_reason": (
            title_reason
        ),
    }
