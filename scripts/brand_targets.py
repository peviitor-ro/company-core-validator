"""List the next unprocessed companies with the live facts needed for brand checks.

Read-only: it never touches cache/results.json, so the subsequent
``cli run --unprocessed`` still targets exactly the same companies.
"""

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from company_core_validator.api import PeviitorAPI
from company_core_validator.cli import enumerate_companies
from company_core_validator.config import DEFAULT_CACHE_DIR
from company_core_validator.store import JsonStore


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args(argv)

    cache = args.cache_dir
    api = PeviitorAPI()
    list_store = JsonStore(cache / "companies.json")
    companies = list_store.get("all")
    if not companies:
        companies = enumerate_companies(api, list_store, refresh=True)

    results = JsonStore(cache / "results.json").data
    targets = [
        company for company in companies
        if str(company.get("id") or "") not in results
    ][:args.limit] if args.limit > 0 else [
        company for company in companies
        if str(company.get("id") or "") not in results
    ]

    def fetch(company):
        cif = str(company.get("id") or "")
        document = api.get_company(cif) or {}
        return {
            "id": cif,
            "company": document.get("company") or company.get("name"),
            "brand": document.get("brand", ""),
            "website": document.get("website", []),
        }

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        rows = list(pool.map(fetch, targets))

    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
