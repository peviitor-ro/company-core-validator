from .config import ALLOWED_FIELDS, OPTIONAL_FIELDS


def status_from_cuiscan(data):
    if not data:
        return None
    if data.get("activ") is True:
        return "activ"
    if data.get("dataRadiere"):
        return "radiat"
    return "inactiv"


def status_from_cuifirma(row):
    if not row:
        return None
    status = str(row.get("status") or "").lower()
    if status in ("dissolved", "radiated", "radiate"):
        return "radiat"
    if status == "active" or row.get("is_active") is True:
        return "activ"
    return "inactiv"


def combined_status(cuiscan_data=None, cuifirma_row=None):
    """Radiat wins whenever any provider reports it."""
    statuses = (status_from_cuiscan(cuiscan_data), status_from_cuifirma(cuifirma_row))
    if "radiat" in statuses:
        return "radiat"
    return statuses[0] or statuses[1]


def build_corrected(document, issues, cuiscan_data=None, cuifirma_row=None,
                    scraper_map=None, today=None, scraper_file_value=None,
                    brand_override=None):
    scraper_map = scraper_map or {}
    payload = {key: value for key, value in document.items() if key in ALLOWED_FIELDS}
    changes = {}
    fixable = {issue.field for issue in issues if issue.fixable}

    for field in OPTIONAL_FIELDS:
        if field in fixable and field in payload:
            changes[field] = {"old": payload.pop(field), "new": "<omitted>"}

    def set_field(field, value):
        if value in (None, "", [], {}):
            return
        old = payload.get(field)
        if old == value:
            return
        payload[field] = value
        changes[field] = {"old": old, "new": value}

    cuiscan_data = cuiscan_data if isinstance(cuiscan_data, dict) else None
    cuifirma_row = cuifirma_row if isinstance(cuifirma_row, dict) else None
    legal_name = (cuiscan_data or {}).get("denumire") \
        or (cuifirma_row or {}).get("display_name") \
        or (cuifirma_row or {}).get("name")
    address = (cuiscan_data or {}).get("adresa") or (cuifirma_row or {}).get("location")
    status = combined_status(cuiscan_data, cuifirma_row)
    brand = (cuifirma_row or {}).get("display_name") or legal_name

    if "company" in fixable:
        set_field("company", legal_name)
    if "brand" in fixable:
        set_field("brand", brand_override or brand)
    if "location" in fixable and address:
        set_field("location", [address])
    if "status" in fixable:
        set_field("status", status)
    if "lastScraped" in fixable:
        set_field("lastScraped", today)

    if "scraperFile" in fixable:
        cif = str(document.get("id") or "")
        old = payload.get("scraperFile", "")
        new = scraper_file_value if scraper_file_value is not None else scraper_map.get(cif, "")
        if old != new:
            payload["scraperFile"] = new
            changes["scraperFile"] = {"old": old, "new": new}

    return payload, changes
