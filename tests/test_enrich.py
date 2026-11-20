from company_core_validator.enrich import (
    build_corrected,
    combined_status,
    status_from_cuifirma,
    status_from_cuiscan,
)
from company_core_validator.rules import validate


def test_status_mapping():
    assert status_from_cuiscan({"activ": True}) == "activ"
    assert status_from_cuiscan({"activ": False, "dataRadiere": "2020-01-01"}) == "radiat"
    assert status_from_cuiscan({"activ": False}) == "inactiv"
    assert status_from_cuifirma({"status": "active"}) == "activ"
    assert status_from_cuifirma({"status": "dissolved"}) == "radiat"


def test_radiat_wins_when_providers_conflict():
    assert combined_status({"activ": True}, {"status": "dissolved"}) == "radiat"
    assert combined_status({"activ": False, "dataRadiere": "2020-01-01"}, {"status": "active"}) == "radiat"


def test_enrichment_fills_only_missing_fields():
    doc = {
        "id": "13390452",
        "company": "",
        "brand": "",
        "status": "unknown",
        "location": [],
        "lastScraped": "",
        "scraperFile": "",
        "website": [],
        "legacy": "old",
    }
    issues = validate(doc, {})
    cuiscan = {"denumire": "NETPRO SRL", "adresa": "Str. X, Oradea", "activ": True}
    payload, changes = build_corrected(doc, issues, cuiscan, None, {}, "2026-11-20")

    assert payload["company"] == "NETPRO SRL"
    assert payload["brand"] == "NETPRO SRL"
    assert payload["status"] == "activ"
    assert payload["location"] == ["Str. X, Oradea"]
    assert payload["lastScraped"] == "2026-11-20"
    assert payload["scraperFile"] == ""
    assert "legacy" not in payload
    assert "website" not in payload
    assert validate(payload, {}) == []


def test_web_verified_brand_override_wins_over_provider_brand():
    doc = {
        "id": "47266026",
        "company": "FISCHER MAN&ING OFFICE S.R.L.",
        "brand": "ING OFFICE ALEXANDRU CEL BUN, IASI (MX8 EXPRESS AGENCY )",
        "status": "activ",
        "location": ["Municipiul Timişoara"],
        "lastScraped": "2026-11-20",
        "scraperFile": "inviitor-ro-nodejs-scraper",
    }
    from company_core_validator.rules import Issue
    issues = [Issue("brand", "web_search", "verified", True)]
    payload, changes = build_corrected(
        doc, issues, None, None, {}, "2026-11-20", None, "FISCHER MAN&ING OFFICE")

    assert payload["brand"] == "FISCHER MAN&ING OFFICE"
    assert changes["brand"]["old"].startswith("ING OFFICE")


def test_scraper_file_taken_from_local_config():
    doc = {
        "id": "13390452",
        "company": "NETPRO SRL",
        "brand": "Netpro",
        "status": "activ",
        "location": ["Oradea"],
        "lastScraped": "2026-11-20",
        "scraperFile": "",
    }
    url = "https://github.com/peviitor-scrapers/netpro-srl-python-scraper/actions/workflows/job-seeker-ro-spider.yml"
    issues = validate(doc, {"13390452": url})
    payload, changes = build_corrected(doc, issues, None, None, {"13390452": url}, "2026-11-20")
    assert payload["scraperFile"] == url


def test_scraper_file_can_be_emptied_without_deleting_company():
    url = "https://github.com/old/repo/actions/workflows/gone.yml"
    doc = {
        "id": "13390452",
        "company": "NETPRO SRL",
        "brand": "Netpro",
        "status": "activ",
        "location": ["Oradea"],
        "lastScraped": "2026-11-20",
        "scraperFile": url,
    }
    from company_core_validator.rules import Issue
    issues = [Issue("scraperFile", "url_unavailable", "gone")]
    payload, changes = build_corrected(
        doc, issues, None, None, {}, "2026-11-20", "")
    assert payload["scraperFile"] == ""
    assert payload["company"] == "NETPRO SRL"
    assert changes["scraperFile"]["new"] == ""
