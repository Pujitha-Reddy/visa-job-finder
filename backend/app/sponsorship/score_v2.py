def sponsor_history_strength(total_lcas=0, recent_lcas=0):
    total = int(total_lcas or 0)
    recent = int(recent_lcas or 0)
    if recent >= 20 or total >= 100: return "STRONG"
    if recent >= 5 or total >= 25: return "MEDIUM"
    if recent >= 1 or total >= 5: return "LOW"
    return "UNKNOWN"

def calculate_sponsorship_score(history_strength, visa_detail_status, visa_language_status):
    score = {"STRONG":55,"MEDIUM":40,"LOW":20,"UNKNOWN":0}.get(history_strength or "UNKNOWN",0)
    detail = visa_detail_status or visa_language_status or "UNKNOWN"
    score += {
        "SPONSORSHIP_AVAILABLE":40,
        "F1_OPT_COMPATIBLE_SIGNAL":28,
        "OPT_F1_MENTIONED":28,
        "WORK_AUTHORIZATION_MENTIONED":10,
        "NOT_MENTIONED":5,
        "UNKNOWN":0,
        "NO_SPONSORSHIP":-45,
        "RESTRICTED":-60,
    }.get(detail,0)
    if detail in {"NO_SPONSORSHIP","RESTRICTED"}:
        score = min(score,25)
    return max(0,min(100,score))
