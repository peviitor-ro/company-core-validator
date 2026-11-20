import argparse
import datetime
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

from .api import PeviitorAPI
from .config import DEFAULT_CACHE_DIR, DEFAULT_SCRAPERS_ROOT
from .enrich import build_corrected
from .local_scrapers import load_scraper_map
from .provider_checks import validate_provider
from .providers import CuifirmaClient, CuiscanClient, RateLimiter, UrlChecker
from .rules import Issue, validate
from .store import JsonStore


def enumerate_companies(api, store, refresh=False):
    cached = store.get("all")
    if cached and not refresh:
        return cached
    companies = []
    page = 1
    while page <= 1000:
        data = api.list_companies(page, rows=1000)
        batch = data.get("companies") or []
        companies.extend(batch)
        total = int(data.get("total") or 0)
        if not batch or len(companies) >= total:
            break
        page += 1
    store.set("all", companies)
    return companies


def get_company(api, store, cif, refresh=False):
    entry = store.get(str(cif))
    if entry is not None and not refresh:
        return entry.get("value")
    value = api.get_company(cif)
    store.set(str(cif), {"value": value})
    return value


def _dedupe(issues):
    seen = set()
    result = []
    for issue in issues:
        key = (issue.field, issue.code)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate and enrich the peviitor company core")
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run", help="validate and optionally fix company documents")
    run_parser.add_argument("--limit", type=int, default=20, help="0 validates every company")
    run_parser.add_argument(
        "--dry-run", action="store_true",
        help="validate without writing fixes (default is to apply fixes directly)")
    run_parser.add_argument(
        "--apply", action="store_true", help=argparse.SUPPRESS)  # deprecated: apply is now default
    run_parser.add_argument("--refresh", action="store_true", help="ignore cached documents and company list")
    run_parser.add_argument(
        "--pending", action="store_true",
        help="re-apply fixes for validated companies whose changes were not applied")
    run_parser.add_argument(
        "--unprocessed", action="store_true",
        help="validate/fix companies that have no entry in results.json yet")
    run_parser.add_argument("--workers", type=int, default=8)
    run_parser.add_argument("--provider-interval", type=float, default=1.0)
    run_parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    run_parser.add_argument(
        "--brand-overrides", type=Path, default=None,
        help="JSON map of CUI to web-verified brand (default: <cache-dir>/brand-overrides.json)")
    run_parser.add_argument("--scrapers-root", type=Path, default=DEFAULT_SCRAPERS_ROOT)
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.print_help()
        return
    if args.dry_run and args.apply:
        run_parser.error("--dry-run and --apply are mutually exclusive")
    if args.pending and args.unprocessed:
        run_parser.error("--pending and --unprocessed are mutually exclusive")
    args.apply = not args.dry_run

    api = PeviitorAPI()
    list_store = JsonStore(args.cache_dir / "companies.json")
    doc_store = JsonStore(args.cache_dir / "documents.json")
    result_store = JsonStore(args.cache_dir / "results.json")
    provider_store = JsonStore(args.cache_dir / "providers.json")
    url_store = JsonStore(args.cache_dir / "urls.json")

    overrides_path = args.brand_overrides or args.cache_dir / "brand-overrides.json"
    if overrides_path.exists():
        brand_overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        if not isinstance(brand_overrides, dict):
            run_parser.error(f"{overrides_path} must contain a JSON object")
    else:
        brand_overrides = {}

    scraper_map = load_scraper_map(args.scrapers_root)
    limiter = RateLimiter(args.provider_interval)
    cuiscan = CuiscanClient(provider_store, limiter)
    cuifirma = CuifirmaClient(provider_store, limiter)
    url_checker = UrlChecker(url_store)

    print(f"Local scrapers: {len(scraper_map)}")
    companies = enumerate_companies(api, list_store, args.refresh)
    print(f"Company core: {len(companies)} records")
    if args.pending:
        by_id = {str(company.get("id") or ""): company for company in companies}
        pending_ids = [
            cif for cif, entry in result_store.data.items()
            if entry.get("status") == "changed"
            and not entry.get("applied")
            and not entry.get("error")
            and cif in by_id
        ]
        if args.limit > 0:
            pending_ids = pending_ids[:args.limit]
        targets = [by_id[cif] for cif in pending_ids]
        print(f"Pending fixes: {len(targets)}")
    elif args.unprocessed:
        targets = [
            company for company in companies
            if str(company.get("id") or "") not in result_store.data
        ]
        if args.limit > 0:
            targets = targets[:args.limit]
        print(f"Unprocessed fixes: {len(targets)}")
    else:
        targets = companies if args.limit <= 0 else companies[:args.limit]
    print(f"Scanning: {len(targets)} ({'APPLY' if args.apply else 'dry run'})")

    def load(company):
        cif = str(company.get("id") or "")
        # In pending/unprocessed modes the cached document is stale; use the
        # live one so already-correct fields (e.g. AI-curated brand) survive.
        refresh = args.refresh or args.pending or args.unprocessed
        return cif, get_company(api, doc_store, cif, refresh)

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        documents = dict(pool.map(load, targets))

    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    for index, company in enumerate(targets, 1):
        cif = str(company.get("id") or "")
        document = documents.get(cif)
        issues = validate(document, scraper_map)
        if cif in brand_overrides:
            issues.append(Issue(
                "brand", "web_search", "Brand verified/corrected via web search", True))
        entry = {
            "id": cif,
            "company": (document or {}).get("company") or company.get("name"),
            "issues": [asdict(issue) for issue in issues],
            "changes": {},
            "applied": False,
            "skipped": False,
        }

        if not issues:
            entry["status"] = "valid"
        elif document is None:
            entry["status"] = "no_document"
            entry["skipped"] = True
        else:
            cuiscan_data = cuiscan.company(cif)
            cuifirma_row = cuifirma.by_cui(cif)
            issues = _dedupe(issues + validate_provider(document, cuiscan_data, cuifirma_row))

            scraper_value = document.get("scraperFile", "")
            expected_scraper = scraper_map.get(cif)
            scraper_file_value = None
            if expected_scraper:
                scraper_file_value = expected_scraper if url_checker.exists(expected_scraper) else ""
            elif isinstance(scraper_value, str) and scraper_value:
                parsed = urlparse(scraper_value)
                is_full_url = parsed.scheme in ("http", "https") and bool(parsed.netloc)
                if not is_full_url:
                    scraper_file_value = ""
                elif not url_checker.exists(scraper_value):
                    issues.append(Issue(
                        "scraperFile", "url_unavailable", "Scraper URL no longer exists"))
                    scraper_file_value = ""

            issues = _dedupe(issues)
            entry["issues"] = [asdict(issue) for issue in issues]
            payload, changes = build_corrected(
                document, issues, cuiscan_data, cuifirma_row, scraper_map, today,
                scraper_file_value, brand_overrides.get(cif))
            entry["changes"] = changes
            entry["status"] = "changed" if changes else "unfixable"
            if changes and args.apply:
                try:
                    api.upsert_company(payload)
                    entry["applied"] = True
                except Exception as err:
                    entry["error"] = str(err)

        result_store.set(cif, entry)
        if index % 20 == 0 or index == len(targets):
            print(f"  {index}/{len(targets)}")

    entries = list(result_store.data.values())
    report = {
        "generatedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "apply": args.apply,
        "scannedThisRun": len(targets),
        "cachedResults": len(entries),
        "summary": {
            "valid": sum(item["status"] == "valid" for item in entries),
            "changed": sum(item["status"] == "changed" for item in entries),
            "unfixable": sum(item["status"] == "unfixable" for item in entries),
            "noDocument": sum(item["status"] == "no_document" for item in entries),
            "applied": sum(bool(item["applied"]) for item in entries),
        },
        "companies": entries,
    }
    report_path = args.cache_dir / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Summary:", json.dumps(report["summary"]))
    print("Report:", report_path)


if __name__ == "__main__":
    main()
