"""Collect deterministic web evidence for every brand in cache/brand-targets.json.

For each CUI we fetch the official website and the CUIFirma public search API in
parallel, then store a compact evidence record in cache/brand-checks.json.
OpenCode uses this file to decide whether a brand override is warranted; the
script itself never changes cache/brand-overrides.json.
"""

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests

from company_core_validator.config import CUIFIRMA_URL, TIMEOUT, USER_AGENT


def _clean(text):
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()[:2000]


def _website(url):
    try:
        response = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT,
            allow_redirects=True)
        response.raise_for_status()
        title = re.search(r"(?is)<title[^>]*>(.*?)</title>", response.text)
        return {
            "url": response.url,
            "status": response.status_code,
            "title": _clean(title.group(1))[:300] if title else "",
            "snippet": _clean(response.text),
        }
    except Exception as err:
        return {"url": url, "error": str(err)[:200]}


def _cuifirma(cif):
    try:
        response = requests.get(
            CUIFIRMA_URL, params={"q": cif},
            headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        response.raise_for_status()
        rows = response.json().get("results") or []
        for row in rows:
            if str(row.get("cui")) == str(cif):
                return {
                    "name": row.get("display_name") or row.get("name"),
                    "brand": row.get("brand"),
                }
        return {"name": None, "brand": None}
    except Exception as err:
        return {"error": str(err)[:200]}


def verify(row):
    cif = str(row.get("id") or "")
    brand = str(row.get("brand") or "")
    company = str(row.get("company") or "")
    sites = [_website(url) for url in (row.get("website") or [])[:2]]
    haystack = " ".join(
        [site.get("title", "") + " " + site.get("snippet", "") for site in sites]
    ).lower()
    tokens = [t for t in re.split(r"\W+", brand.lower()) if len(t) >= 4]
    brand_seen = bool(tokens) and all(token in haystack for token in tokens)
    company_seen = bool(company) and company.lower() in haystack
    return {
        "id": cif,
        "company": company,
        "brand": brand,
        "sites": sites,
        "cuifirma": _cuifirma(cif),
        "brand_on_site": brand_seen,
        "legal_name_on_site": company_seen,
        "review": not sites or not (brand_seen or company_seen),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", default="cache/brand-targets.json")
    parser.add_argument("--output", default="cache/brand-checks.json")
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args(argv)

    targets = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        rows = list(pool.map(verify, targets))

    Path(args.output).write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Brand evidence collected: {len(rows)} companies, "
          f"{sum(1 for row in rows if row['review'])} need review "
          f"-> {args.output}")


if __name__ == "__main__":
    main()
