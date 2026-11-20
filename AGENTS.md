# AGENTS.md

## Ce e acest repo

Validator pentru **company core** de pe peviitor.ro. Citește documentele de firmă din
`https://api.peviitor.ro/v1/firme/company/`, le compară cu providerii CUIScan / CUIFirma
și scrie înapoi doar câmpurile care încalcă regulile din `company_core_validator/rules.py`.

Sursa de date pentru lista de firme e `GET /v1/companies/`; fiecare firmă e identificată
prin CUI (`id`).

## Reguli de aur

1. **Rulează codul din repo, nu-l reimplementa.** Unica comandă de validare e:
   ```
   python -m company_core_validator.cli run --unprocessed --limit 20 --workers 8
   ```
2. **Folosește `--unprocessed`.** Nu folosi `--limit N` simplu: ar revalidat primele N
   firme din listă la fiecare run. `--unprocessed` selectează firmele fără intrare în
   `cache/results.json`.
3. **Scrierea e singurul mod.** `run` aplică întotdeauna. Nu există `--dry-run` și nici
   `--apply`; ambele au fost șterse din cod. Fiecare rulare GitHub Actions scrie și
   repară companiile pe bune.
4. **Verificarea web a brandului e OBLIGATORIE la fiecare rulare**, pentru fiecare firmă
   din batch, înainte de comanda de aplicare. Nu e opțională și nu depinde de „dacă ai
   unelte web”. Pași:
   - rulează `python scripts/brand_targets.py --limit 20 > /tmp/brand-targets.json`
     pentru lista CUIs + brand live + nume legal + website;
   - pentru **fiecare** CUI caută brandul pe web (site oficial, CUIFirma, motor de
     căutare) și notează în log: `CUI | brand live | sursa verificată | verdict`;
   - dacă brandul live aparține clar altei firme, adaugă corecția în
     `cache/brand-overrides.json` (JSON: `"CUI": "brand"`) înainte de `run`;
   - override-ul are prioritate față de provider. Nu adăuga corecții speculative.
   - dacă nu poți accesa webul, **oprește-te înainte de `run`** și spune explicit că
     verificarea brandului a eșuat. Nu aplica nimic fără ea.
5. **Nu suprascrie manual** `company`, `status`, `location`, `website`, `career`,
   `scraperFile` sau `lastScraped`. Le gestionează validatorul și providerii.
6. **Actualizare live e eventual consistentă.** După un PUT, o citire imediată poate
   întoarce încă valoarea veche; reîncearcă după o scurtă pauză.
7. **API-ul escape-uiește `&` la scriere.** Clientul deja aplică `unescape()` la
   citire/scriere — nu adăuga un alt strat de escape.

## Stare între run-uri

- `cache/results.json` e sursa de adevăr pentru ce s-a procesat. În GitHub Actions e
  restaurat prin `actions/cache` (cheie per run, `restore-keys` pe prefix) și rescris la
  finalul job-ului.
- `cache/companies.json`, `cache/documents.json`, `cache/providers.json`,
  `cache/urls.json` sunt cache-uri tehnice; le păstrăm între run-uri ca să nu reîncărcăm
  18.000+ de firme de fiecare dată.
- `cache/brand-overrides.json` e versionat în git (singurul fișier din `cache/` care e
  commit-at).

## Raport

După run, `cache/report.json` conține `scannedThisRun`, `summary` și `companies` cu
`changes` per CUI. Afișează un scurt sumar, nu tot JSON-ul.

## Teste

```
python -m pytest -q
```
