from app.analyzers.experience import parse_experience
from app.analyzers.location import classify_work_arrangement
from app.analyzers.employment import classify_employment
from app.analyzers.visa import analyze_visa_language


def test_experience():
    assert parse_experience("Minimum 3 years of experience")["match"] is True
    assert parse_experience("Minimum 7 years of experience")["match"] is False
    assert parse_experience("7 years preferred")["match"] is None
    assert parse_experience("New Grad Software Engineer")["min_years"] == 0


def test_location():
    assert classify_work_arrangement("Remote - US", "")["value"] == "REMOTE"
    assert classify_work_arrangement("", "This is a hybrid position.")["value"] == "HYBRID"
    assert classify_work_arrangement("New York, NY", "")["value"] == "UNKNOWN"


def test_employment():
    assert classify_employment("", "6 month W2 contract")["value"] == "CONTRACT_W2"
    assert classify_employment("", "C2C contract opportunity")["value"] == "CONTRACT_C2C"
    assert classify_employment("", "Full-time employee")["value"] == "FULL_TIME"


def test_visa_missing_is_not_rejected():
    result = analyze_visa_language("Build scalable Java services on AWS.")
    assert result["status"] == "NOT_MENTIONED"


def test_no_sponsorship():
    result = analyze_visa_language("We are unable to sponsor candidates now or in the future.")
    assert result["status"] == "NO_SPONSORSHIP"


def test_positive_sponsorship():
    result = analyze_visa_language("H-1B sponsorship is available for this position.")
    assert result["status"] == "SPONSORSHIP_AVAILABLE"
