from enum import Enum
from typing import Optional
from pydantic import BaseModel


class WorkArrangement(str, Enum):
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ONSITE = "ONSITE"
    UNKNOWN = "UNKNOWN"


class EmploymentType(str, Enum):
    FULL_TIME = "FULL_TIME"
    CONTRACT_W2 = "CONTRACT_W2"
    CONTRACT_C2C = "CONTRACT_C2C"
    CONTRACT_UNKNOWN = "CONTRACT_UNKNOWN"
    TEMPORARY = "TEMPORARY"
    INTERNSHIP = "INTERNSHIP"
    UNKNOWN = "UNKNOWN"


class VisaLanguageStatus(str, Enum):
    SPONSORSHIP_AVAILABLE = "SPONSORSHIP_AVAILABLE"
    OPT_F1_MENTIONED = "OPT_F1_MENTIONED"
    NO_SPONSORSHIP = "NO_SPONSORSHIP"
    RESTRICTED = "RESTRICTED"
    NOT_MENTIONED = "NOT_MENTIONED"
    UNKNOWN = "UNKNOWN"


class Decision(str, Enum):
    APPLY = "APPLY"
    OK_TO_APPLY = "OK_TO_APPLY"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SKIP = "SKIP"


class Job(BaseModel):
    id: int
    company_name_raw: str
    title: str
    source: str
    source_url: str
    apply_url: Optional[str] = None
    location_raw: Optional[str] = None
    posted_at: Optional[str] = None
    min_experience_years: Optional[float] = None
    max_experience_years: Optional[float] = None
    work_arrangement: WorkArrangement
    employment_type: EmploymentType
    visa_language_status: VisaLanguageStatus
    h1b_history_strength: str
    sponsorship_score: float
    overall_score: float
    decision: Decision
    application_status: str
