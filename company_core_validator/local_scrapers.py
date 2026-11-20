import json

from pathlib import Path

from .config import DEFAULT_SCRAPERS_ROOT


def load_scraper_map(root=DEFAULT_SCRAPERS_ROOT):
    result = {}
    for config_path in sorted(Path(root).glob("*/scraper/config/company.json")):
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        cif = str(config.get("id") or config.get("cui") or "").strip()
        scraper_file = config.get("scraperFile")
        if cif and isinstance(scraper_file, str) and scraper_file:
            result[cif] = scraper_file
    return result
