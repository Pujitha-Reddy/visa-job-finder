from app.collectors.common import clean_html, title_matches


def test_title_matches_target():
    assert title_matches("Backend Software Engineer")
    assert title_matches("Java Developer II")
    assert not title_matches("Product Manager")


def test_clean_html():
    assert clean_html("<p>Hello <strong>world</strong></p>") == "Hello world"
