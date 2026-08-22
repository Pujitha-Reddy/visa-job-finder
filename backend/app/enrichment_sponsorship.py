from __future__ import annotations

import re


# ==========================================================
# JOB-SPECIFIC VISA LANGUAGE
#
# Ordering matters:
# explicit negative language is checked before positive
# language because phrases such as:
#
# "we do not provide visa sponsorship"
#
# contain the word "sponsorship".
# ==========================================================


NEGATIVE_PATTERNS = (
    r"\bwill not (?:provide |offer )?(?:visa |immigration |employment )?sponsorship\b",

    r"\bdoes not (?:provide |offer )?(?:visa |immigration |employment )?sponsorship\b",

    r"\bdo not (?:provide |offer )?(?:visa |immigration |employment )?sponsorship\b",

    r"\bunable to (?:provide |offer )?(?:visa |immigration |employment )?sponsorship\b",

    r"\bcannot (?:provide |offer )?(?:visa |immigration |employment )?sponsorship\b",

    r"\bnot eligible for (?:visa |immigration |employment )?sponsorship\b",

    r"\bno (?:visa |immigration |employment )?sponsorship(?: available)?\b",

    r"\bwithout (?:the need for )?(?:current or future )?(?:employer )?(?:visa |immigration |employment )?sponsorship\b",

    r"\bwithout requiring (?:current or future )?(?:employer )?(?:visa |immigration |employment )?sponsorship\b",

    r"\bmust be (?:legally )?authorized to work.{0,120}\bwithout.{0,80}\bsponsorship\b",

    r"\brequire no sponsorship\b",

    r"\bno sponsorship (?:is |will be )?available\b",

    r"\bwe are unable to sponsor\b",

    r"\bnot able to sponsor\b",
)



POSITIVE_PATTERNS = (
    r"\bvisa sponsorship (?:is )?available\b",

    r"\bimmigration sponsorship (?:is )?available\b",

    r"\bwill (?:provide |offer )?(?:visa |immigration )?sponsorship\b",

    r"\bwe sponsor\b",

    r"\bwill sponsor\b",

    r"\bsponsorship available\b",

    r"\bh-?1b sponsorship\b",

    r"\bsponsor(?:ing)? (?:an )?h-?1b\b",

    r"\bemployment visa sponsorship\b",

    r"\bwork visa sponsorship\b",
)


POSSIBLE_PATTERNS = (
    r"\bmay (?:provide |offer )?(?:visa |immigration )?sponsorship\b",

    r"\bsponsorship may be available\b",

    r"\bvisa sponsorship may be considered\b",

    r"\bimmigration support\b",

    r"\bimmigration assistance\b",

    r"\bvisa support\b",
)


def normalize(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def extract_visa_language(
    title,
    description,
):
    text = normalize(
        " ".join(
            [
                str(title or ""),
                str(description or ""),
            ]
        )
    )

    if not text:
        return {
            "status": "NO_EXPLICIT_LANGUAGE",
            "evidence": None,
            "confidence": 0.0,
        }

    # ------------------------------------------------------
    # Explicit rejection
    # ------------------------------------------------------

    for pattern in NEGATIVE_PATTERNS:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return {
                "status": "EXPLICIT_NO_SPONSORSHIP",
                "evidence": match.group(0),
                "confidence": 0.99,
            }

    # ------------------------------------------------------
    # Explicit positive sponsorship
    # ------------------------------------------------------

    for pattern in POSITIVE_PATTERNS:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return {
                "status": "EXPLICIT_SPONSORSHIP",
                "evidence": match.group(0),
                "confidence": 0.99,
            }

    # ------------------------------------------------------
    # Conditional / weaker signal
    # ------------------------------------------------------

    for pattern in POSSIBLE_PATTERNS:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )

        if match:
            return {
                "status": "POSSIBLE_SPONSORSHIP",
                "evidence": match.group(0),
                "confidence": 0.75,
            }

    return {
        "status": "NO_EXPLICIT_LANGUAGE",
        "evidence": None,
        "confidence": 0.0,
    }


# ==========================================================
# EMPLOYER HISTORICAL SPONSORSHIP
# ==========================================================


def history_strength(
    *,
    combined_score,
    filings,
    approvals,
):
    score = float(
        combined_score
        or 0
    )

    filings = int(
        filings
        or 0
    )

    approvals = int(
        approvals
        or 0
    )

    if (
        score >= 80
        or approvals >= 50
        or filings >= 100
    ):
        return "STRONG"

    if (
        score >= 65
        or approvals >= 15
        or filings >= 30
    ):
        return "GOOD"

    if (
        score >= 50
        or approvals >= 5
        or filings >= 10
    ):
        return "MODERATE"

    if (
        score > 0
        or approvals > 0
        or filings > 0
    ):
        return "WEAK"

    return "UNKNOWN"


def calculate_sponsorship(
    *,
    sponsor_parent_key,
    combined_score,
    filings,
    approvals,
    visa_status,
):
    combined_score = float(
        combined_score
        or 0
    )

    filings = int(
        filings
        or 0
    )

    approvals = int(
        approvals
        or 0
    )

    strength = history_strength(
        combined_score=combined_score,
        filings=filings,
        approvals=approvals,
    )

    # ------------------------------------------------------
    # Base score = employer historical evidence.
    #
    # combined_sponsor_score already incorporates the
    # sponsor-universe evidence, so we do not heavily
    # double-count raw DOL/USCIS volumes here.
    # ------------------------------------------------------

    score = combined_score

    reasons = []

    if sponsor_parent_key:
        reasons.append(
            "SPONSOR_IDENTITY_MATCH"
        )

    if combined_score:
        reasons.append(
            f"HISTORY_SCORE={combined_score:.1f}"
        )

    if filings:
        reasons.append(
            f"DOL_RECENT={filings}"
        )

    if approvals:
        reasons.append(
            f"USCIS_RECENT={approvals}"
        )

    # ------------------------------------------------------
    # Job-specific language dominates history where explicit.
    # ------------------------------------------------------

    if visa_status == "EXPLICIT_NO_SPONSORSHIP":

        score = 0.0

        reasons.append(
            "JOB_EXPLICITLY_REJECTS_SPONSORSHIP"
        )

    elif visa_status == "EXPLICIT_SPONSORSHIP":

        score = max(
            score,
            95.0,
        )

        reasons.append(
            "JOB_EXPLICITLY_SUPPORTS_SPONSORSHIP"
        )

    elif visa_status == "POSSIBLE_SPONSORSHIP":

        score = min(
            95.0,
            score + 8.0,
        )

        reasons.append(
            "JOB_HAS_POSSIBLE_SPONSORSHIP_LANGUAGE"
        )

    # Small activity fallback when sponsor score happens
    # to be absent but raw filing/approval evidence exists.
    elif score == 0:

        if approvals >= 10:
            score = 60.0

        elif approvals > 0:
            score = 50.0

        elif filings >= 10:
            score = 45.0

        elif filings > 0:
            score = 35.0

    score = max(
        0.0,
        min(
            100.0,
            score,
        ),
    )

    if not reasons:
        reasons.append(
            "NO_SPONSOR_EVIDENCE"
        )

    return {
        "history_strength": strength,
        "score": round(
            score,
            2,
        ),
        "reason": ";".join(
            reasons
        ),
    }
