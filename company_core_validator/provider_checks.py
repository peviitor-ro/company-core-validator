import re
import unicodedata

from .enrich import combined_status
from .rules import Issue

LEGAL_TOKENS = frozenset({"srl", "s", "r", "l", "sa", "sc", "ltd", "llc", "srl", "sr"})


def normalize_cui(value):
    """Only strips an optional RO prefix and whitespace; never pads or truncates."""
    return re.sub(r"^ro\s*", "", str(value or "").strip(), flags=re.IGNORECASE)


def normalize_name(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return " ".join(token for token in text.split() if token not in LEGAL_TOKENS)


def validate_provider(document, cuiscan_data=None, cuifirma_row=None):
    """Checks core identity against CUIscan/CUIFirma. No CUI length rule."""
    if not isinstance(document, dict):
        return []

    cuiscan_data = cuiscan_data if isinstance(cuiscan_data, dict) else None
    cuifirma_row = cuifirma_row if isinstance(cuifirma_row, dict) else None
    issues = []

    provider_cui = None
    if cuiscan_data:
        provider_cui = cuiscan_data.get("cui")
    if provider_cui is None and cuifirma_row:
        provider_cui = cuifirma_row.get("cui")

    if provider_cui is None:
        issues.append(Issue(
            "id", "unverified", "CUI not found in CUIscan or CUIFirma", False))
        return issues

    core_cui = normalize_cui(document.get("id"))
    if normalize_cui(provider_cui) != core_cui:
        issues.append(Issue(
            "id", "mismatch", f"Core CUI {document.get('id')} != provider CUI {provider_cui}", False))

    legal_name = (cuiscan_data or {}).get("denumire") \
        or (cuifirma_row or {}).get("display_name") \
        or (cuifirma_row or {}).get("name")
    if legal_name:
        core_name = normalize_name(document.get("company"))
        provider_name = normalize_name(legal_name)
        if core_name and provider_name and core_name != provider_name:
            issues.append(Issue(
                "company", "mismatch", f"Company name differs from provider: {legal_name}"))

    provider_status = combined_status(cuiscan_data, cuifirma_row)
    if provider_status and document.get("status") != provider_status:
        issues.append(Issue(
            "status", "mismatch", f"Status differs from provider: {provider_status}"))

    return issues
