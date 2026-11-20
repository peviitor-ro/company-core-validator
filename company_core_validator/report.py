import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .api import PeviitorAPI
from .config import DEFAULT_CACHE_DIR
from .enrich import status_from_cuifirma, status_from_cuiscan
from .local_scrapers import load_scraper_map
from .provider_checks import normalize_cui, normalize_name, validate_provider
from .rules import validate


def _provider_row(cif, providers):
    entry = providers.get(f"cuifirma:q:{cif}") or {}
    for row in entry.get("value") or []:
        if normalize_cui(row.get("cui")) == normalize_cui(cif):
            return row
    return None


def _verdict(issues, field):
    codes = [issue.code for issue in issues if issue.field == field]
    return "OK" if not codes else ", ".join(codes)


def _field(name, core, cuiscan=None, cuifirma=None, verdict="OK", note=""):
    return {
        "field": name,
        "core": core,
        "cuiscan": cuiscan,
        "cuifirma": cuifirma,
        "verdict": verdict,
        "note": note,
    }


def build_entries(limit=20, cache_dir=DEFAULT_CACHE_DIR):
    cache_dir = Path(cache_dir)
    source = json.loads((cache_dir / "report.json").read_text(encoding="utf-8"))
    providers = json.loads((cache_dir / "providers.json").read_text(encoding="utf-8"))
    scraper_map = load_scraper_map()
    api = PeviitorAPI()

    targets = source["companies"] if limit <= 0 else source["companies"][:limit]
    entries = []
    for item in targets:
        cif = item["id"]
        document = api.get_company(cif)
        cuiscan = (providers.get(f"cuiscan:{cif}") or {}).get("value")
        cuifirma = _provider_row(cif, providers)
        issues = validate(document, scraper_map) + validate_provider(document, cuiscan, cuifirma)

        cs_name = (cuiscan or {}).get("denumire")
        cf_name = (cuifirma or {}).get("display_name") or (cuifirma or {}).get("name")
        cs_status = status_from_cuiscan(cuiscan)
        cf_status = status_from_cuifirma(cuifirma)
        cs_cui = (cuiscan or {}).get("cui")
        cf_cui = (cuifirma or {}).get("cui")

        fields = [
            _field("id", document.get("id"), cs_cui, cf_cui, _verdict(issues, "id"),
                   "Fără verificare de lungime; comparat după eliminarea prefixului RO."),
            _field("company", document.get("company"), cs_name, cf_name, _verdict(issues, "company"),
                   "Comparat după normalizarea diacriticelor și a sufixelor legale."),
            _field("brand", document.get("brand"), None, cf_name, _verdict(issues, "brand"),
                   "Brandul nu are sursă autoritară în provideri; CUIFirma e doar referință."),
            _field("status", document.get("status"),
                   f"{cs_status} (activ={(cuiscan or {}).get('activ')}, dataRadiere={(cuiscan or {}).get('dataRadiere') or '-'})" if cuiscan else None,
                   f"{cf_status} ({(cuifirma or {}).get('status')}, {(cuifirma or {}).get('status_label')})" if cuifirma else None,
                   _verdict(issues, "status")),
            _field("location", document.get("location"), (cuiscan or {}).get("adresa"),
                   (cuifirma or {}).get("location"), _verdict(issues, "location"),
                   "Localitatea din core e păstrată; adresa completă e doar referință."),
            _field("lastScraped", document.get("lastScraped"), None, None,
                   _verdict(issues, "lastScraped"), "Validat ca dată YYYY-MM-DD; fără sursă în provideri."),
            _field("scraperFile", document.get("scraperFile") or "", None, None,
                   _verdict(issues, "scraperFile"),
                   "Trebuie să fie URL complet http(s) care există; altfel se golește doar câmpul."),
            _field("group/website/career",
                   {key: document.get(key) for key in ("group", "website", "career")
                    if document.get(key) not in (None, "", [], {})},
                   None, None, "OK", "Câmpuri opționale; absența nu e eroare."),
        ]

        entries.append({
            "id": cif,
            "company": document.get("company"),
            "fields": fields,
            "issues": [{"field": issue.field, "code": issue.code, "message": issue.message}
                       for issue in issues],
            "changes": item["changes"],
            "applied": item["applied"],
        })
    return entries


def render_markdown(entries):
    lines = [
        "# Full validation report — core vs CUIscan vs CUIFirma",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Legend: `OK` = valid; any other text = issue codes. "
        "Provider values are shown even when the core value is intentionally kept.",
        "",
    ]
    for entry in entries:
        lines.append(f"## {entry['id']} — {entry['company']}")
        lines.append("")
        lines.append("| Câmp | Core | CUIscan | CUIFirma | Verdict |")
        lines.append("|---|---|---|---|---|")
        for field in entry["fields"]:
            values = []
            for key in ("core", "cuiscan", "cuifirma"):
                value = field[key]
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                value = str(value) if value is not None else "-"
                value = value.replace("|", "\\|").replace("\n", " ")
                if len(value) > 90:
                    value = value[:89] + "…"
                values.append(value or "-")
            lines.append(f"| {field['field']} | {values[0]} | {values[1]} | {values[2]} | {field['verdict']} |")
        lines.append("")
        if entry["issues"]:
            lines.append("Issue-uri: " + "; ".join(
                f"{issue['field']}:{issue['code']}" for issue in entry["issues"]))
            lines.append("")
        if entry["changes"]:
            changes = "; ".join(
                f"{name}: {json.dumps(change['old'], ensure_ascii=False)} → "
                f"{json.dumps(change['new'], ensure_ascii=False)}"
                for name, change in entry["changes"].items())
            lines.append(f"Modificări aplicate (`applied={entry['applied']}`): {changes}")
            lines.append("")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Full core/provider validation report")
    parser.add_argument("--limit", type=int, default=20, help="0 = all companies in the pilot report")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    args = parser.parse_args(argv)

    entries = build_entries(args.limit, args.cache_dir)
    markdown = render_markdown(entries)
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    (args.cache_dir / "full-report.json").write_text(
        json.dumps({"generatedAt": datetime.now(timezone.utc).isoformat(), "entries": entries},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    (args.cache_dir / "full-report.md").write_text(markdown, encoding="utf-8")
    print(markdown)


if __name__ == "__main__":
    main()
