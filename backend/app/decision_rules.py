def decide_job(
    work_arrangement: str,
    visa_language_status: str,
    experience_match: bool | None,
) -> tuple[str, str]:
    """
    Important project rule:
    Missing visa/sponsorship language must NEVER be treated as automatic rejection.
    """

    if visa_language_status in {"NO_SPONSORSHIP", "RESTRICTED"}:
        return "SKIP", "Job contains explicit sponsorship or work-authorization restrictions."

    if experience_match is False:
        return "SKIP", "Required experience is outside the configured 0-6 year range."

    if visa_language_status in {"NOT_MENTIONED", "UNKNOWN"}:
        return (
            "NEEDS_REVIEW",
            "Visa/sponsorship language was not found or is unclear; manual review required.",
        )

    if work_arrangement == "REMOTE":
        return "APPLY", "Remote role with positive/acceptable visa evidence."

    if work_arrangement == "HYBRID":
        return "OK_TO_APPLY", "Hybrid role fits the configured location preference."

    if work_arrangement in {"ONSITE", "UNKNOWN"}:
        return "NEEDS_REVIEW", "Location arrangement requires manual review."

    return "NEEDS_REVIEW", "Insufficient information for an automatic decision."
