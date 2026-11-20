import datetime

from dataclasses import dataclass
from urllib.parse import urlparse

from .config import ALLOWED_FIELDS, OPTIONAL_FIELDS, REQUIRED_FIELDS, STATUSES, URL_FIELDS


@dataclass(frozen=True)
class Issue:
    field: str
    code: str
    message: str
    fixable: bool = True


def _nonempty(value):
    if value is None:
        return False
    if isinstance(value, (str, list, dict, tuple, set)):
        return bool(value)
    return True


def _valid_date(value):
    if not isinstance(value, str) or not value:
        return False
    try:
        datetime.date.fromisoformat(value[:10])
        return True
    except ValueError:
        return False


def _valid_url(value):
    if not isinstance(value, str):
        return False
    # The peviitor API rejects non-ASCII URLs, so treat them as invalid here.
    if not value.isascii():
        return False
    parsed = urlparse(value)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def validate(document, scraper_map):
    if not isinstance(document, dict):
        return [Issue("<doc>", "missing_document", "Company core has no document for this CIF", False)]

    issues = []
    for field in document:
        if field not in ALLOWED_FIELDS:
            issues.append(Issue(field, "unexpected_field", f"Unexpected field: {field}"))

    for field in REQUIRED_FIELDS:
        if field == "scraperFile":
            continue
        if not _nonempty(document.get(field)):
            issues.append(Issue(field, "missing", f"Missing or empty required field: {field}"))

    cif = str(document.get("id") or "")

    for field in ("company", "brand"):
        value = document.get(field)
        if value is not None and not isinstance(value, str):
            issues.append(Issue(field, "invalid_type", f"{field} must be a string"))

    status = document.get("status")
    if status is not None and status not in STATUSES:
        issues.append(Issue("status", "invalid_value", f"status must be one of {sorted(STATUSES)}"))

    location = document.get("location")
    if location is not None and (
        not isinstance(location, list)
        or not location
        or not all(isinstance(item, str) and item.strip() for item in location)
    ):
        issues.append(Issue("location", "invalid_list", "location must be a non-empty list of strings"))

    if "lastScraped" in document and not _valid_date(document.get("lastScraped")):
        issues.append(Issue("lastScraped", "invalid_date", "lastScraped must be a YYYY-MM-DD date"))

    for field in URL_FIELDS:
        value = document.get(field)
        if value is None:
            continue
        if not isinstance(value, list):
            issues.append(Issue(field, "invalid_type", f"{field} must be a list of URLs"))
        elif not value:
            issues.append(Issue(field, "empty_optional", f"Empty optional field: {field}"))
        elif not all(_valid_url(item) for item in value):
            issues.append(Issue(field, "invalid_url", f"{field} contains an invalid URL"))

    for field in OPTIONAL_FIELDS:
        if field in URL_FIELDS:
            continue
        if field in document and not _nonempty(document.get(field)):
            issues.append(Issue(field, "empty_optional", f"Empty optional field: {field}"))

    scraper_value = document.get("scraperFile", "")
    expected = scraper_map.get(cif)
    if not isinstance(scraper_value, str):
        issues.append(Issue("scraperFile", "invalid_type", "scraperFile must be a string"))
    elif scraper_value:
        parsed = urlparse(scraper_value)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            issues.append(Issue("scraperFile", "not_full_url", "scraperFile must be a full http(s) URL"))
        elif expected and scraper_value != expected:
            issues.append(Issue("scraperFile", "mismatch", "scraperFile does not match local scraper config"))
    elif expected:
        issues.append(Issue("scraperFile", "mismatch", "scraperFile does not match local scraper config"))

    return issues
