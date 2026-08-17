NON_US_REGEX = r"(poland|dublin|ireland|remote uk|united kingdom|england|scotland|canada|toronto|vancouver|montreal|mexico|greece|athens|germany|berlin|munich|france|paris|spain|madrid|barcelona|italy|milan|netherlands|amsterdam|belgium|sweden|stockholm|norway|denmark|finland|switzerland|austria|portugal|czech|romania|hungary|india|gurugram|gurgaon|bangalore|bengaluru|hyderabad|pune|chennai|mumbai|delhi|singapore|australia|new zealand|japan|china|hong kong|taiwan|philippines|brazil|argentina|colombia|chile|peru|israel|united arab emirates|uae|south africa)"
US_REMOTE_REGEX = r"(remote[, -]*(usa|us|u\.s\.|united states)|(usa|us|u\.s\.|united states)[, -]*remote|^united states$|^usa$|^u\.s\.$|anywhere in (the )?(us|u\.s\.|united states)|nationwide)"
ALLOWED_METRO_REGEX = r"(florida|miami|orlando|tampa|jacksonville|fort lauderdale|west palm beach|boca raton|clearwater|st\.? petersburg|dallas|fort worth|plano|irving|richardson|frisco|addison|dfw|chicago|chicagoland|naperville|schaumburg|evanston|oak brook|st\.? louis|saint louis|clayton|chesterfield|kansas city|overland park|lenexa|shawnee|olathe)"
SENIORITY_EXCLUDE_REGEX = r"(^| )(principal|senior staff|sr staff|staff|lead)( |$)"

def strict_freshness_sql():
    return """AND source_published_at IS NOT NULL AND ((%s <= 24 AND freshness_confidence='HIGH') OR (%s > 24 AND freshness_confidence IN ('HIGH','MEDIUM'))) AND NULLIF(source_published_at,'')::timestamptz >= NOW() - (%s * INTERVAL '1 hour')"""

def strict_freshness_params(hours):
    return [hours, hours, hours]

def strict_eligibility_sql():
    return f"""AND COALESCE(is_active,TRUE)=TRUE AND employment_type NOT IN ('INTERNSHIP','TEMPORARY') AND (min_experience_years IS NULL OR min_experience_years <= 6) AND NOT (min_experience_years IS NULL AND LOWER(COALESCE(title,'')) ~ '{SENIORITY_EXCLUDE_REGEX}') AND NOT (LOWER(TRIM(COALESCE(location_raw,''))) ~ '{NON_US_REGEX}') AND (LOWER(TRIM(COALESCE(location_raw,''))) ~ '{US_REMOTE_REGEX}' OR LOWER(TRIM(COALESCE(location_raw,''))) ~ '{ALLOWED_METRO_REGEX}')"""
