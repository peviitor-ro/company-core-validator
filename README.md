# Company Core Validator

Validates every document in the peviitor **company** core, repairs missing or
malformed fields using CUIScan/CUIFirma, and reports what it would change.

All Solr access goes through the peviitor v1 API. No direct Solr calls.

## Fields learned from the core

| Field | Required | Source when missing |
|---|---|---|
| `id` | yes | never rewritten; no length rule, verified against providers |
| `company` | yes | CUIScan `denumire`, fallback CUIFirma `name` |
| `brand` | yes | CUIFirma `display_name`, fallback `company` |
| `status` | yes | CUIScan `activ`/`dataRadiere` or CUIFirma `status` |
| `location` | yes | CUIScan `adresa`, fallback CUIFirma `location` |
| `lastScraped` | yes | today (UTC date) |
| `scraperFile` | yes, may be empty | local scraper config; empty when there is no scraper |
| `website`, `career`, `group` | optional | empty values are omitted, never invented |

Allowed `status` values: `activ`, `suspendat`, `inactiv`, `radiat`.

Identity is checked by querying CUIscan by CUI and CUIFirma by CUI. Only an
optional `RO` prefix and surrounding whitespace are ignored when comparing the
CUI — no padding, truncation or digit-count rule. `company` and `status` are
compared with the provider answer and repaired when they differ. If neither
provider knows the CUI, the record is reported as `unverified`.

`scraperFile` rules:

- the value must be a full `http(s)` URL, never a bare scraper name;
- the URL is checked with an HTTP HEAD request (cached);
- if the company has a local scraper under `~/scrapers/*/scraper/config/company.json`,
  its workflow URL is preferred;
- if the URL no longer exists, or there is no scraper, the field is set to `""`
  and the company document is otherwise left intact.

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest tests -q
```

## Usage

```bash
.venv/bin/python -m company_core_validator.cli run --limit 20
.venv/bin/python -m company_core_validator.cli run --limit 0
.venv/bin/python -m company_core_validator.cli run --pending --limit 20
.venv/bin/python -m company_core_validator.cli run --unprocessed --limit 50
```

`--pending` re-applies fixes to companies that were already validated but whose
changes were not applied. `--unprocessed` targets companies that have no entry
in `cache/results.json` yet. Both modes refresh the live document before
upserting, so curated fields such as the web-searched `brand` are preserved.

Web-verified brand corrections live in `cache/brand-overrides.json` (a simple
CUI → brand map). Overrides are applied only when the web evidence clearly
contradicts the live brand; all other fields are still fixed by the validator.

`run` always applies fixes — there is no preview mode, and no `--apply` flag.
Provider answers and company documents are cached in `cache/`, so a later full
run resumes without repeating expensive lookups.

Rate limiting is conservative: one request per second per provider by default,
with a JSON cache and 429/5xx backoff. CUIFirma advertises a 60-request limit;
CUIScan caches responses for 180 seconds. A full 18k-company enrichment is
therefore slow by design.

## GitHub Actions

[`.github/workflows/validate-companies.yml`](.github/workflows/validate-companies.yml)
runs the validator with **OpenCode** (`opencode/big-pickle`) driving the repo code:

- scheduled daily at 04:00 UTC, or manually via `workflow_dispatch` with `limit`
  (default `20`);
- **every run writes fixes** — there is no dry-run input and no preview mode;
- `scripts/brand_targets.py --limit <limit>` writes the read-only list of this batch
  to `cache/brand-targets.json` (CUI, live brand, legal name, website), then
  `scripts/brand_verify.py` collects web evidence in parallel into
  `cache/brand-checks.json`. OpenCode reviews every `review: true` row via webfetch
  and may add only clear corrections to `cache/brand-overrides.json`. If no web
  evidence at all can be collected, the run stops before applying;
- then it uses `--unprocessed --limit <limit> --workers 8` so each run advances to
  the next batch instead of reprocessing the first companies;
- restores `cache/results.json` and the technical caches through `actions/cache`
  (rolling key per run) and uploads `cache/report.json` as an artifact.

OpenCode reads [`AGENTS.md`](AGENTS.md) first and never hand-edits `company`,
`status`, `location`, `website`, `career`, `scraperFile` or `lastScraped`.

## Report

`cache/report.json` contains one entry per scanned company: validation issues,
proposed field changes, and whether they were applied.
