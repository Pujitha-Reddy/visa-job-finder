from app.sponsorship.normalize import normalize_company_name
from app.sponsorship.scoring import score_sponsor_history, combine_job_and_sponsor


def test_normalization():
    assert normalize_company_name("Microsoft Corporation") == "microsoft"
    assert normalize_company_name("Amazon.com Services LLC") == "amazon"


def test_strong_sponsor_history():
    result = score_sponsor_history([
        {"source": "DOL", "source_year": 2026, "filings_count": 150},
        {"source": "USCIS", "source_year": 2025, "filings_count": 200,
         "approved_count": 195, "denied_count": 5},
    ], current_year=2026)
    assert result["strength"] == "STRONG"


def test_missing_visa_language_stays_review():
    result = combine_job_and_sponsor("NOT_MENTIONED", "STRONG", 90)
    assert result["label"] == "NEEDS_REVIEW_STRONG_HISTORY"


def test_explicit_no_sponsorship_beats_history():
    result = combine_job_and_sponsor("NO_SPONSORSHIP", "STRONG", 95)
    assert result["label"] == "SKIP"
    assert result["sponsorship_score"] == 0
