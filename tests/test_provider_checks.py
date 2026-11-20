from company_core_validator.provider_checks import (
    normalize_cui,
    normalize_name,
    validate_provider,
)


def test_normalizers_do_not_pad_or_truncate():
    assert normalize_cui("RO 4981476") == "4981476"
    assert normalize_cui("1") == "1"
    assert normalize_cui("1" * 50) == "1" * 50
    assert normalize_name("CENTRO IMOBILIARE S.R.L.") == normalize_name("Centro Imobiliare SRL")


def test_short_cui_is_verified_against_provider():
    doc = {"id": "1", "company": "FIRST SRL", "status": "activ"}
    cuiscan = {"cui": 1, "denumire": "FIRST S.R.L.", "activ": True}
    assert validate_provider(doc, cuiscan, None) == []


def test_provider_cui_mismatch_is_reported():
    doc = {"id": "1", "company": "FIRST SRL", "status": "activ"}
    cuiscan = {"cui": 2, "denumire": "FIRST SRL", "activ": True}
    issues = validate_provider(doc, cuiscan, None)
    assert any(issue.field == "id" and issue.code == "mismatch" for issue in issues)


def test_name_and_status_mismatch_are_fixable():
    doc = {"id": "13390452", "company": "OLD NAME", "status": "inactiv"}
    cuiscan = {"cui": 13390452, "denumire": "NETPRO SRL", "activ": True}
    issues = validate_provider(doc, cuiscan, None)
    codes = {(issue.field, issue.code, issue.fixable) for issue in issues}
    assert ("company", "mismatch", True) in codes
    assert ("status", "mismatch", True) in codes


def test_radiat_wins_over_cuiscan_active():
    doc = {"id": "14336222", "company": "WORK BETON SRL", "status": "activ"}
    cuiscan = {"cui": 14336222, "denumire": "WORK BETON SRL", "activ": True}
    cuifirma = {"cui": "14336222", "status": "dissolved"}
    issues = validate_provider(doc, cuiscan, cuifirma)
    assert any(issue.field == "status" and issue.code == "mismatch" for issue in issues)


def test_missing_provider_data_is_unverified():
    issues = validate_provider({"id": "123", "company": "X", "status": "activ"})
    assert any(issue.field == "id" and issue.code == "unverified" for issue in issues)
