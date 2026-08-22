from __future__ import annotations

import re


# ==========================================================
# ROLE FAMILIES
#
# IMPORTANT:
# This classifier answers:
#
#     "Is this job in the software / software-adjacent
#      engineering domain?"
#
# It does NOT answer:
#
#     "Is this job appropriate for the user's experience?"
#
# Manager/staff/principal/etc. decisions belong to the
# experience / seniority eligibility stage.
# ==========================================================


ROLE_RULES = [
    (
        "SOFTWARE_ENGINEERING",
        100,
        [
            r"\bsoftware engineer\b",
            r"\bsoftware engineers\b",
            r"\bsoftware engineering\b",
            r"\bsoftware developer\b",
            r"\bsoftware developers\b",
            r"\bsoftware development engineer\b",
            r"\bsoftware development\b",
            r"\bsoftware systems engineer\b",
            r"\bsoftware systems engineering\b",
            r"\bsde\b",
        ],
    ),

    (
        "FULL_STACK",
        100,
        [
            r"\bfull[\s-]?stack\b",
            r"\bfull stack engineer\b",
            r"\bfull stack developer\b",
        ],
    ),

    (
        "BACKEND",
        95,
        [
            r"\bback[\s-]?end\b",
            r"\bbackend engineer\b",
            r"\bbackend developer\b",
            r"\bserver[\s-]?side\b",
        ],
    ),

    (
        "FRONTEND",
        95,
        [
            r"\bfront[\s-]?end\b",
            r"\bfrontend engineer\b",
            r"\bfrontend developer\b",
            r"\bui engineer\b",
            r"\bui developer\b",
            r"\bweb engineer\b",
        ],
    ),

    (
        "SITE_RELIABILITY",
        95,
        [
            r"\bsite reliability\b",
            r"\bsre\b",
        ],
    ),

    (
        "PLATFORM",
        92,
        [
            r"\bplatform engineer\b",
            r"\bplatform engineering\b",
            r"\bplatform developer\b",
            r"\bplatform software\b",
        ],
    ),

    (
        "DEVOPS",
        92,
        [
            r"\bdevops\b",
            r"\bdevsecops\b",
            r"\bbuild and release engineer\b",
            r"\brelease engineer\b",
        ],
    ),

    (
        "CLOUD",
        88,
        [
            r"\bcloud engineer\b",
            r"\bcloud engineering\b",
            r"\bcloud developer\b",
            r"\bcloud platform engineer\b",
        ],
    ),

    (
        "DATA_ENGINEERING",
        90,
        [
            r"\bdata engineer\b",
            r"\bdata engineering\b",
            r"\bdata platform engineer\b",
            r"\bdata infrastructure engineer\b",
        ],
    ),

    (
        "ML_ENGINEERING",
        92,
        [
            r"\bmachine learning engineer\b",
            r"\bmachine learning engineering\b",
            r"\bml engineer\b",
            r"\bml engineering\b",
            r"\bai engineer\b",
            r"\bai engineering\b",
            r"\bapplied ai engineer\b",
            r"\bml platform\b",
        ],
    ),

    (
        "APPLICATION_ENGINEERING",
        88,
        [
            r"\bapplication developer\b",
            r"\bapplications developer\b",
            r"\bapplication engineer\b",
            r"\bapplication engineering\b",
            r"\bapplications engineer\b",
        ],
    ),

    (
        "INFRASTRUCTURE",
        85,
        [
            r"\binfrastructure engineer\b",
            r"\binfrastructure engineering\b",
            r"\bsystems software engineer\b",
            r"\bproduction engineer\b",
        ],
    ),

    (
        "DATABASE_ENGINEERING",
        82,
        [
            r"\bdatabase engineer\b",
            r"\bdatabase developer\b",
            r"\bdb engineer\b",
        ],
    ),

    (
        "DEVELOPER",
        80,
        [
            r"\bjava developer\b",
            r"\bpython developer\b",
            r"\bjavascript developer\b",
            r"\btypescript developer\b",
            r"\breact developer\b",
            r"\bnode(?:\.js)? developer\b",
            r"\bapi developer\b",
            r"\bweb developer\b",
            r"\bcloud developer\b",
        ],
    ),
]


# ==========================================================
# HARD DOMAIN EXCLUDES
#
# These remove clearly non-software engineering domains.
#
# Do NOT put management/seniority terms here.
# ==========================================================

HARD_EXCLUDES = [
    r"\bmechanical engineer\b",
    r"\bcivil engineer\b",
    r"\bchemical engineer\b",
    r"\bmanufacturing engineer\b",
    r"\bprocess engineer\b",
    r"\bindustrial engineer\b",
    r"\bconstruction engineer\b",

    r"\belectrical engineer\b",
    r"\bhardware engineer\b",

    r"\bsales engineer\b",
    r"\bfield service engineer\b",

    r"\bclinical\b",
    r"\bnurse\b",
    r"\bphysician\b",

    r"\baccountant\b",
    r"\battorney\b",
]


def normalize(value):
    return re.sub(
        r"\s+",
        " ",
        str(value or "").lower(),
    ).strip()


def classify_software_role(title):
    title = normalize(title)

    if not title:
        return {
            "is_software_role": 0,
            "software_role_family": None,
            "software_role_score": 0,
            "software_role_reason": "EMPTY_TITLE",
        }

    # ------------------------------------------------------
    # Strong software evidence takes precedence over generic
    # engineering exclusions.
    #
    # Example:
    # "Software Engineer - Hardware Platform"
    # should remain software.
    # ------------------------------------------------------

    matches = []

    for family, score, patterns in ROLE_RULES:
        for pattern in patterns:
            if re.search(
                pattern,
                title,
            ):
                matches.append(
                    (
                        score,
                        family,
                        pattern,
                    )
                )

    if matches:
        matches.sort(
            key=lambda item: (
                -item[0],
                item[1],
            )
        )

        score, family, pattern = matches[0]

        return {
            "is_software_role": 1,
            "software_role_family": family,
            "software_role_score": score,
            "software_role_reason": (
                f"TITLE_MATCH:{pattern}"
            ),
        }

    # ------------------------------------------------------
    # No software evidence found.
    # Now check obvious non-software domains.
    # ------------------------------------------------------

    for pattern in HARD_EXCLUDES:
        if re.search(
            pattern,
            title,
        ):
            return {
                "is_software_role": 0,
                "software_role_family": None,
                "software_role_score": 0,
                "software_role_reason": (
                    f"HARD_EXCLUDE:{pattern}"
                ),
            }

    return {
        "is_software_role": 0,
        "software_role_family": None,
        "software_role_score": 0,
        "software_role_reason": (
            "NO_SOFTWARE_TITLE_MATCH"
        ),
    }
