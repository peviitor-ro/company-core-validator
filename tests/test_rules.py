from company_core_validator.rules import validate


def valid_doc():
    return {
        "id": "13390452",
        "company": "NETPRO SRL",
        "brand": "Netpro",
        "status": "activ",
        "location": ["Oradea"],
        "lastScraped": "2026-11-20",
        "scraperFile": "https://github.com/peviitor-scrapers/netpro-srl-python-scraper/actions/workflows/job-seeker-ro-spider.yml",
    }


def test_valid_document_has_no_issues():
    assert validate(valid_doc(), {}) == []


def test_scraper_file_must_be_a_full_url():
    doc = valid_doc()
    doc["scraperFile"] = "inviitor-ro-nodejs-scraper"
    issues = validate(doc, {})
    assert any(issue.field == "scraperFile" and issue.code == "not_full_url" for issue in issues)


def test_cui_length_is_never_validated():
    for cif in ("1", "4981476", "1" * 50, "RO123"):
        doc = valid_doc()
        doc["id"] = cif
        assert validate(doc, {}) == []


def test_missing_and_malformed_fields_are_detected():
    doc = valid_doc()
    doc.pop("brand")
    doc["status"] = "unknown"
    doc["lastScraped"] = "yesterday"
    codes = {(issue.field, issue.code) for issue in validate(doc, {})}
    assert ("brand", "missing") in codes
    assert ("status", "invalid_value") in codes
    assert ("lastScraped", "invalid_date") in codes


def test_scraper_file_must_match_local_scraper():
    doc = valid_doc()
    doc["scraperFile"] = "https://github.com/other/scraper/actions/workflows/job.yml"
    issues = validate(doc, {"13390452": valid_doc()["scraperFile"]})
    assert any(issue.field == "scraperFile" and issue.code == "mismatch" for issue in issues)


def test_scraper_file_may_be_empty_without_a_scraper():
    doc = valid_doc()
    doc["scraperFile"] = ""
    assert validate(doc, {}) == []


def test_unexpected_and_empty_optional_fields_are_flagged():
    doc = valid_doc()
    doc["website"] = []
    doc["legacyField"] = "old"
    codes = {(issue.field, issue.code) for issue in validate(doc, {})}
    assert ("website", "empty_optional") in codes
    assert ("legacyField", "unexpected_field") in codes


def test_non_ascii_website_url_is_invalid():
    doc = valid_doc()
    doc["website"] = ["https://www.topfirme.com/afacere/neacşu-întreprindere/"]
    issues = validate(doc, {})
    assert any(issue.field == "website" and issue.code == "invalid_url" for issue in issues)
