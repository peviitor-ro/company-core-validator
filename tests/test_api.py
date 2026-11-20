from company_core_validator.api import unescape


def test_unescape_collapses_repeated_html_escaping():
    assert unescape("FISCHER MAN&amp;amp;ING OFFICE") == "FISCHER MAN&ING OFFICE"
    assert unescape("AT&T") == "AT&T"
    assert unescape(["A&amp;B", {"x": "C&amp;amp;D"}]) == ["A&B", {"x": "C&D"}]
