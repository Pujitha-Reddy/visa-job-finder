def calculate_overall_score(job: dict) -> dict:
    score = 0
    reasons = []

    if job.get("title"):
        score += 15
        reasons.append("Target software role/title present (+15)")

    exp_match = job.get("experience_match")
    if exp_match in (1, True):
        score += 20
        reasons.append("Experience fits 0-6 YOE (+20)")
    elif exp_match is None:
        score += 10
        reasons.append("Experience requirement unclear (+10)")

    work = job.get("work_arrangement")
    score += {"REMOTE": 15, "HYBRID": 12, "ONSITE": 5, "UNKNOWN": 7}.get(work, 0)

    employment = job.get("employment_type")
    score += {
        "FULL_TIME": 10, "CONTRACT_W2": 9, "CONTRACT_C2C": 7,
        "CONTRACT_UNKNOWN": 6, "INTERNSHIP": 7, "TEMPORARY": 4, "UNKNOWN": 5
    }.get(employment, 0)

    sponsor_strength = job.get("h1b_history_strength")
    score += {"STRONG": 20, "MEDIUM": 14, "LOW": 7, "UNKNOWN": 4}.get(sponsor_strength, 0)

    visa = job.get("visa_language_status")
    score += {
        "SPONSORSHIP_AVAILABLE": 20, "OPT_F1_MENTIONED": 18,
        "NOT_MENTIONED": 10, "UNKNOWN": 8, "NO_SPONSORSHIP": 0, "RESTRICTED": 0
    }.get(visa, 0)

    if visa in {"NO_SPONSORSHIP", "RESTRICTED"}:
        score = min(score, 35)

    score = max(0, min(100, score))
    band = "HIGH" if score >= 80 else "GOOD" if score >= 65 else "REVIEW" if score >= 50 else "LOW"
    return {"score": score, "band": band, "reasons": reasons}
