import re


# ==========================================================
# Software / platform engineering title taxonomy
# ==========================================================

TARGET_PATTERNS = [
    # ------------------------------------------------------
    # Core software engineering
    # ------------------------------------------------------
    r"\bsoftware\s+(?:development\s+)?engineer\b",
    r"\bsoftware\s+developer\b",
    r"\bsoftware\s+engineering\b",

    # Common SWE abbreviations
    r"\bswe\b",

    # ------------------------------------------------------
    # Full stack / frontend / backend
    # ------------------------------------------------------
    r"\bfull[\s-]?stack\b",

    r"\bfront[\s-]?end\b",
    r"\bfrontend\b",

    r"\bback[\s-]?end\b",
    r"\bbackend\b",

    # ------------------------------------------------------
    # Developers
    # ------------------------------------------------------
    r"\bjava\s+developer\b",
    r"\bpython\s+developer\b",
    r"\bjavascript\s+developer\b",
    r"\btypescript\s+developer\b",
    r"\breact\s+developer\b",
    r"\bnode(?:\.js)?\s+developer\b",
    r"\b\.net\s+developer\b",
    r"\bdotnet\s+developer\b",
    r"\bapi\s+developer\b",

    # Generic developer title, but exclusions below protect us.
    r"\bdeveloper\b",

    # ------------------------------------------------------
    # Platform / infrastructure / cloud
    # ------------------------------------------------------
    r"\bplatform\s+engineer(?:ing)?\b",
    r"\bplatform\s+engineering\b",

    r"\bcloud\s+(?:software\s+)?engineer\b",
    r"\bcloud\s+developer\b",

    r"\bdevops\b",

    r"\bsite\s+reliability\s+engineer\b",
    r"\bsite\s+reliability\b",
    r"\bsre\b",

    r"\binfrastructure\s+(?:software\s+)?engineer\b",

    # ------------------------------------------------------
    # Developer productivity / developer experience
    # ------------------------------------------------------
    r"\bdeveloper\s+experience\b",
    r"\bdeveloper\s+productivity\b",
    r"\bdevex\b",

    # ------------------------------------------------------
    # Databases / distributed systems
    # ------------------------------------------------------
    r"\bdatabase\s+developer\b",
    r"\bdatabase\s+engineer\b",

    # ------------------------------------------------------
    # AI / ML engineering
    # ------------------------------------------------------
    r"\bai\s+(?:software\s+)?engineer\b",
    r"\bmachine\s+learning\s+engineer\b",
    r"\bml\s+engineer\b",

    # Some companies call production AI/platform roles
    # "AI Operations Engineer".
    r"\bai\s+operations\s+engineer\b",

    # ------------------------------------------------------
    # Application engineering
    #
    # Keep this narrower than simply matching "application".
    # ------------------------------------------------------
    r"\bapplication\s+engineer\b",

    # ------------------------------------------------------
    # Enterprise software engineering stacks
    # ------------------------------------------------------
    r"\bsap\s+abap\s+developer\b",
    r"\babap\s+developer\b",

    r"\bservicenow\b.*\bplatform\s+engineering\b",
]


# ==========================================================
# Strong non-target signals
#
# These override TARGET_PATTERNS.
# This prevents phrases such as:
#
#   "Account Executive - Workforce Software"
#
# from being considered software-engineering jobs simply
# because the word "software" occurs in the title.
# ==========================================================

EXCLUDE_TITLE_PATTERNS = [
    # Sales / revenue
    r"\baccount\s+executive\b",
    r"\bsales\s+representative\b",
    r"\bsales\s+manager\b",
    r"\bsales\s+director\b",
    r"\bdigital\s+sales\b",
    r"\bfield\s+sales\b",
    r"\benterprise\s+sales\b",
    r"\bbusiness\s+development\b",
    r"\bpre[-\s]?sales\b",

    # Customer/service roles
    r"\bcustomer\s+service\b",
    r"\bclient\s+service\b",

    # Explicit consulting / implementation roles
    # that happen to mention a software product.
    r"\btechnical\s+implementation\s+consultant\b",
    r"\bimplementation\s+consultant\b",

    # Executive/management roles rather than IC engineering.
    r"\bdirector\b",
    r"\bvice\s+president\b",
    r"\bvp\b",
    r"\bchief\b",

    # Recruiting / HR
    r"\brecruiter\b",
    r"\btalent\s+acquisition\b",
]


def title_matches(title):
    t = re.sub(
        r"\s+",
        " ",
        (title or "").lower(),
    ).strip()

    if not t:
        return False

    # Strong exclusions win first.
    if any(
        re.search(pattern, t)
        for pattern in EXCLUDE_TITLE_PATTERNS
    ):
        return False

    return any(
        re.search(pattern, t)
        for pattern in TARGET_PATTERNS
    )