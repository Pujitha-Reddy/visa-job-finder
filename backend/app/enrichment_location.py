from __future__ import annotations

import re


US_STATE_CODES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
    "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
    "DC",
}

US_STATE_NAMES = {
    "alabama":"AL", "alaska":"AK", "arizona":"AZ",
    "arkansas":"AR", "california":"CA", "colorado":"CO",
    "connecticut":"CT", "delaware":"DE", "florida":"FL",
    "georgia":"GA", "hawaii":"HI", "idaho":"ID",
    "illinois":"IL", "indiana":"IN", "iowa":"IA",
    "kansas":"KS", "kentucky":"KY", "louisiana":"LA",
    "maine":"ME", "maryland":"MD", "massachusetts":"MA",
    "michigan":"MI", "minnesota":"MN", "mississippi":"MS",
    "missouri":"MO", "montana":"MT", "nebraska":"NE",
    "nevada":"NV", "new hampshire":"NH", "new jersey":"NJ",
    "new mexico":"NM", "new york":"NY",
    "north carolina":"NC", "north dakota":"ND",
    "ohio":"OH", "oklahoma":"OK", "oregon":"OR",
    "pennsylvania":"PA", "rhode island":"RI",
    "south carolina":"SC", "south dakota":"SD",
    "tennessee":"TN", "texas":"TX", "utah":"UT",
    "vermont":"VT", "virginia":"VA", "washington":"WA",
    "west virginia":"WV", "wisconsin":"WI",
    "wyoming":"WY", "district of columbia":"DC",
}

# High-value city inference for locations where providers omit state/country.
US_CITY_STATE = {
    "san francisco":"CA",
    "cupertino":"CA",
    "mountain view":"CA",
    "sunnyvale":"CA",
    "san jose":"CA",
    "palo alto":"CA",
    "los angeles":"CA",
    "san diego":"CA",
    "seattle":"WA",
    "bellevue":"WA",
    "redmond":"WA",
    "new york":"NY",
    "austin":"TX",
    "dallas":"TX",
    "houston":"TX",
    "chicago":"IL",
    "boston":"MA",
    "atlanta":"GA",
    "miami":"FL",
    "denver":"CO",
    "portland":"OR",
    "philadelphia":"PA",
    "pittsburgh":"PA",
    "raleigh":"NC",
    "charlotte":"NC",
    "arlington":"VA",
    "mclean":"VA",
    "reston":"VA",
    "washington dc":"DC",
}

NON_US_CODES = {
    "AU","GB","UK","IN","CA-NONUS","DE-NONUS","FR","IE",
    "SG","JP","KR","PL","ES","IT","NL","MX","BR","RO",
    "CZ","SE","CH","IL-NONUS","TW","PT","MY","NZ",
}

NON_US_TERMS = {
    "india", "united kingdom", "canada", "germany",
    "france", "ireland", "singapore", "australia",
    "japan", "south korea", "korea", "poland", "spain",
    "italy", "netherlands", "mexico", "brazil",
    "romania", "czech republic", "sweden", "switzerland",
    "israel", "taiwan", "portugal", "malaysia",
    "new zealand", "jakarta", "bengaluru", "bangalore",
    "hyderabad", "pune", "chennai", "mumbai", "london",
    "dublin", "toronto", "vancouver", "sydney", "warsaw",
    "lisbon", "hiroshima", "tlaquepaque", "indaiatuba",
    "nottingham", "tel aviv",

    "serbia", "belgrade",
    "hungary", "budapest",
    "china", "shanghai",
    "austria", "vienna",
    "argentina", "buenos aires",
    "uruguay",
    "switzerland", "basel",
    "gurugram", "noida",
    "berlin",
}

REGION_NON_US = {
    "emea", "apj", "apac",
}


def normalize(value):
    return re.sub(r"\s+", " ", str(value or "").strip())


def low(value):
    return normalize(value).lower()


def contains(text, pattern):
    return re.search(pattern, text, re.I) is not None


def detect_state(location):
    text = low(location)

    if not text:
        return None

    for name, code in US_STATE_NAMES.items():
        if contains(text, rf"\b{re.escape(name)}\b"):
            return code

    # State abbreviations should normally appear as location components.
    for code in US_STATE_CODES:
        if contains(text, rf"(?:^|[,\s]){code}(?:$|[,\s;(])"):
            return code

    for city, code in US_CITY_STATE.items():
        if contains(text, rf"\b{re.escape(city)}\b"):
            return code

    return None


def explicit_us_signal(location):
    text = low(location)

    if contains(text, r"\bunited states(?: of america)?\b"):
        return True

    if contains(text, r"\busa\b"):
        return True

    if contains(text, r"(?:^|[,\s;(])us(?:$|[,\s;)])"):
        return True

    if contains(text, r"\bu\.s\.(?:\b|$)"):
        return True

    if contains(text, r"(?:^|[\s,;(])us-[a-z]{2}(?:-|\b)"):
        return True

    if contains(text, r"\busa\d*\b"):
        return True

    return False


def non_us_signals(location):
    text = low(location)
    signals = []

    for term in NON_US_TERMS:
        if contains(text, rf"\b{re.escape(term)}\b"):
            signals.append(term)

    # Common ISO/provider suffixes.
    code_patterns = {
        "AU": r"(?:^|[,\s])au(?:$|[,\s])",
        "GB": r"(?:^|[,\s])gb(?:$|[,\s])",
        "IN": r"(?:^|[,\s])in(?:$|[,\s])",
        "SG": r"(?:^|[,\s])sg(?:$|[,\s])",
        "JP": r"(?:^|[,\s])jp(?:$|[,\s])",
        "KR": r"(?:^|[,\s])kr(?:$|[,\s])",
        "MX": r"(?:^|[,\s])mx(?:$|[,\s])",
        "BR": r"(?:^|[,\s])br(?:$|[,\s])",
        "CZ": r"(?:^|[,\s])cz(?:$|[,\s])",
        "TW": r"(?:^|[,\s])tw(?:$|[,\s])",
        "PT": r"(?:^|[,\s])pt(?:$|[,\s])",
        "RS": r"(?:^|[,\s-])rs(?:$|[,\s-])",
        "HU": r"(?:^|[,\s-])hu(?:$|[,\s-])",
        "CN": r"(?:^|[,\s-])cn(?:$|[,\s-])",
        "AT": r"(?:^|[,\s-])at(?:$|[,\s-])",
        "AR": r"(?:^|[,\s-])ar(?:$|[,\s-])",
    }

    for code, pattern in code_patterns.items():
        if contains(text, pattern):
            signals.append(code)

    for region in REGION_NON_US:
        if contains(text, rf"\b{region}\b"):
            signals.append(region)

    return signals


def detect_country(location):
    text = low(location)

    if not text or text in {
        "n/a",
        "na",
        "none",
        "-",
    }:
        return (
            None,
            0.20,
            "NO_USABLE_LOCATION",
        )

    # ======================================================
    # Explicit US always wins when the posting genuinely
    # includes a United States location option.
    #
    # Examples:
    #   Remote, Canada; Remote, United States
    #   Indianapolis, IN, US
    #   US, NJ, Newark
    #   US-CA-Menlo Park
    # ======================================================

    us_explicit = explicit_us_signal(
        location
    )

    if us_explicit:
        foreign = non_us_signals(
            location
        )

        if foreign:
            return (
                "US",
                0.98,
                "US_AND_NON_US_LOCATIONS",
            )

        return (
            "US",
            1.0,
            "EXPLICIT_US",
        )

    # ======================================================
    # Terminal country-code detection.
    #
    # Critical distinction:
    #
    #   Hyderabad, TS, IN
    #       IN = India
    #
    # versus:
    #
    #   Indianapolis, IN, US
    #       IN = Indiana because US is explicit.
    #
    # Never let a final foreign ISO country code become a
    # U.S. state.
    # ======================================================

    normalized = normalize(
        location
    )

    components = [
        part.strip()
        for part in re.split(
            r"[,|;]",
            normalized,
        )
        if part.strip()
    ]

    FOREIGN_TERMINAL_CODES = {
        "IN": "INDIA",
        "GB": "UNITED_KINGDOM",
        "UK": "UNITED_KINGDOM",
        "CA": "CANADA",
        "AU": "AUSTRALIA",
        "SG": "SINGAPORE",
        "JP": "JAPAN",
        "KR": "SOUTH_KOREA",
        "DE": "GERMANY",
        "FR": "FRANCE",
        "IE": "IRELAND",
        "NL": "NETHERLANDS",
        "MX": "MEXICO",
        "BR": "BRAZIL",
        "PL": "POLAND",
        "ES": "SPAIN",
        "IT": "ITALY",
        "CZ": "CZECH_REPUBLIC",
        "SE": "SWEDEN",
        "CH": "SWITZERLAND",
        "TW": "TAIWAN",
        "PT": "PORTUGAL",
        "RO": "ROMANIA",
        "HU": "HUNGARY",
        "AT": "AUSTRIA",
        "RS": "SERBIA",
        "AR": "ARGENTINA",
        "CN": "CHINA",
        "NZ": "NEW_ZEALAND",
        "MY": "MALAYSIA",
    }

    if components:
        terminal = components[-1].upper()

        # Handles:
        #   "IN"
        #   "GB"
        # but not longer textual location components.
        if terminal in FOREIGN_TERMINAL_CODES:

            # CA is ambiguous:
            #
            #   San Francisco, CA
            #       = California
            #
            #   Toronto, ON, CA
            #       = Canada
            #
            # A known U.S. city resolves the ambiguity.
            if terminal == "CA":
                value_lower = low(
                    location
                )

                known_us_city = any(
                    re.search(
                        rf"\b{re.escape(city)}\b",
                        value_lower,
                    )
                    for city
                    in US_CITY_STATE
                )

                if known_us_city:
                    return (
                        "US",
                        0.97,
                        "US_CITY_WITH_CA_STATE",
                    )

            return (
                "NON_US",
                0.995,
                (
                    "TERMINAL_COUNTRY_CODE:"
                    + terminal
                ),
            )

    # ======================================================
    # Foreign textual / code evidence comes BEFORE generic
    # U.S. state inference.
    # ======================================================

    foreign = non_us_signals(
        location
    )

    if foreign:
        return (
            "NON_US",
            0.97,
            f"NON_US:{foreign[0]}",
        )

    # ======================================================
    # Only now use state/city inference.
    # ======================================================

    state = detect_state(
        location
    )

    if state:
        return (
            "US",
            0.97,
            f"US_STATE:{state}",
        )

    return (
        None,
        0.40,
        "COUNTRY_UNKNOWN",
    )


def detect_work_arrangement(title, location, description):
    title_text = low(title)
    location_text = low(location)
    description_text = low(description)

    # Strongest evidence: title/location.
    primary = f"{title_text} {location_text}"

    if contains(primary, r"\bhybrid\b"):
        return "HYBRID", 0.98, "TITLE_LOCATION:HYBRID"

    if (
        contains(primary, r"\bremote\b")
        or contains(primary, r"\bwork from home\b")
        or contains(primary, r"\bwfh\b")
    ):
        return "REMOTE", 0.98, "TITLE_LOCATION:REMOTE"

    if (
        contains(primary, r"\bon[\s-]?site\b")
        or contains(primary, r"\bin[\s-]?office\b")
        or contains(primary, r"\boffice[\s-]?based\b")
    ):
        return "ONSITE", 0.97, "TITLE_LOCATION:ONSITE"

    # Description only gets used for explicit work-arrangement phrases,
    # not arbitrary occurrences of "remote" or "virtual".
    hybrid_description = (
        r"\bhybrid work\b|"
        r"\bhybrid schedule\b|"
        r"\bhybrid role\b|"
        r"\bhybrid position\b|"
        r"\bhybrid working\b|"
        r"\bdays? (?:per week )?in (?:the )?office\b"
    )

    remote_description = (
        r"\bfully remote\b|"
        r"\b100% remote\b|"
        r"\bremote position\b|"
        r"\bremote role\b|"
        r"\bremote work\b|"
        r"\bwork remotely\b|"
        r"\bremote employee\b"
    )

    onsite_description = (
        r"\bfully onsite\b|"
        r"\bfully on-site\b|"
        r"\bon-site position\b|"
        r"\bonsite position\b|"
        r"\bmust work onsite\b|"
        r"\bmust work on-site\b"
    )

    if contains(description_text, hybrid_description):
        return "HYBRID", 0.90, "DESCRIPTION_EXPLICIT:HYBRID"

    if contains(description_text, remote_description):
        return "REMOTE", 0.90, "DESCRIPTION_EXPLICIT:REMOTE"

    if contains(description_text, onsite_description):
        return "ONSITE", 0.90, "DESCRIPTION_EXPLICIT:ONSITE"

    # A physical location does NOT prove onsite.
    if location_text and location_text not in {
        "n/a", "na", "none", "-"
    }:
        return "UNKNOWN", 0.45, "PHYSICAL_LOCATION_NO_WORK_MODE"

    return "UNKNOWN", 0.20, "NO_WORK_ARRANGEMENT_SIGNAL"


def detect_city(location, state_code):
    value = normalize(location)

    if not value:
        return None

    text = low(value)

    for city in US_CITY_STATE:
        if contains(text, rf"\b{re.escape(city)}\b"):
            return city.title()

    parts = [
        part.strip()
        for part in value.split(",")
        if part.strip()
    ]

    if state_code and parts:
        candidate = parts[0]

        if (
            not re.match(r"^\d+\b", candidate)
            and low(candidate) not in {"us", "usa", "remote"}
        ):
            return candidate

    return None


def classify_location(*, title, location, description):
    arrangement, arrangement_confidence, arrangement_reason = (
        detect_work_arrangement(
            title,
            location,
            description,
        )
    )

    country, country_confidence, country_reason = (
        detect_country(location)
    )

    state = detect_state(location)

    city = detect_city(
        location,
        state,
    )

    is_us_job = (
        1 if country == "US"
        else 0 if country == "NON_US"
        else None
    )

    is_us_remote = 1 if (
        arrangement == "REMOTE"
        and country == "US"
    ) else 0

    return {
        "country_code": "US" if country == "US" else None,
        "state_code": state,
        "city": city,
        "work_arrangement": arrangement,
        "is_us_job": is_us_job,
        "is_us_remote": is_us_remote,
        "location_confidence": round(
            max(
                country_confidence,
                arrangement_confidence,
            ),
            4,
        ),
        "location_reason": (
            f"{country_reason};{arrangement_reason}"
        ),
    }
