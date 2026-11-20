import html
import time

import requests

from .config import API_BASE, TIMEOUT, USER_AGENT


def unescape(value):
    """Collapse repeated HTML escaping applied by the company API."""
    if isinstance(value, str):
        previous = None
        while previous != value:
            previous = value
            value = html.unescape(value)
        return value
    if isinstance(value, list):
        return [unescape(item) for item in value]
    if isinstance(value, dict):
        return {key: unescape(item) for key, item in value.items()}
    return value


class PeviitorAPI:
    def __init__(self, base=API_BASE):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _get(self, path, params):
        for attempt in range(4):
            response = self.session.get(self.base + path, params=params, timeout=TIMEOUT)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(0.5 * (2 ** attempt))
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(f"API GET failed after retries: {path}")

    def list_companies(self, page, rows=1000):
        return self._get("/companies/", {"page": page, "rows": rows})

    def get_company(self, cif):
        data = self._get("/firme/company/", {"cif": cif, "rows": 1})
        rows = data.get("data") or []
        return unescape(rows[0]) if rows else None

    def upsert_company(self, document):
        response = self.session.put(
            self.base + "/firme/company/add/", json=unescape(document), timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
