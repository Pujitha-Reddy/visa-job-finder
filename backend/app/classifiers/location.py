def classify_work_arrangement(location: str, description: str, workplace_type: str | None = None) -> dict:
    wt = (workplace_type or "").lower()
    combined = f"{location or ''} {description or ''}".lower()

    if wt in {"remote","hybrid","on_site","onsite"}:
        mapping = {"remote":"REMOTE","hybrid":"HYBRID","on_site":"ONSITE","onsite":"ONSITE"}
        return {"value":mapping[wt],"reason":"ATS workplace type."}

    if "hybrid" in combined:
        return {"value":"HYBRID","reason":"Hybrid language detected."}
    if any(x in combined for x in ("remote","work from home","distributed")):
        return {"value":"REMOTE","reason":"Remote language detected."}
    if any(x in combined for x in ("on-site","onsite","in-office","in office")):
        return {"value":"ONSITE","reason":"Onsite language detected."}
    return {"value":"UNKNOWN","reason":"Work arrangement unclear."}
