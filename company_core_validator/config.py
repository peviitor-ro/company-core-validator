from pathlib import Path

API_BASE = "https://api.peviitor.ro/v1"
CUISCAN_URL = "https://cuiscan.ro/api.php"
CUIFIRMA_URL = "https://cuifirma.ro/api/search"
USER_AGENT = "job_seeker_ro_spider"
TIMEOUT = 15

ALLOWED_FIELDS = frozenset({
    "id", "company", "brand", "group", "status", "location",
    "website", "career", "lastScraped", "scraperFile",
})
REQUIRED_FIELDS = ("id", "company", "brand", "status", "location", "lastScraped", "scraperFile")
OPTIONAL_FIELDS = ("group", "website", "career")
URL_FIELDS = ("website", "career")
STATUSES = frozenset({"activ", "suspendat", "inactiv", "radiat"})
PROVIDER_FIELDS = frozenset({"company", "brand", "status", "location"})

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[1] / "cache"
DEFAULT_SCRAPERS_ROOT = Path.home() / "scrapers"
