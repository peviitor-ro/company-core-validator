import threading
import time

import requests

from .config import CUIFIRMA_URL, CUISCAN_URL, TIMEOUT, USER_AGENT


class RateLimiter:
    def __init__(self, interval=1.0):
        self.interval = max(0.0, interval)
        self.last = 0.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            delay = self.interval - (time.monotonic() - self.last)
            if delay > 0:
                time.sleep(delay)
            self.last = time.monotonic()


class CachedClient:
    def __init__(self, store, prefix, limiter, ttl):
        self.store = store
        self.prefix = prefix
        self.limiter = limiter
        self.ttl = ttl

    def fetch(self, key, loader):
        cache_key = f"{self.prefix}:{key}"
        entry = self.store.get(cache_key)
        if isinstance(entry, dict) and time.time() - entry.get("ts", 0) < self.ttl:
            return entry.get("value")
        self.limiter.wait()
        try:
            value = loader()
        except Exception:
            return None
        self.store.set(cache_key, {"ts": time.time(), "value": value})
        return value


class CuiscanClient:
    def __init__(self, store, limiter, ttl=7 * 86400):
        self.client = CachedClient(store, "cuiscan", limiter, ttl)

    def company(self, cif):
        return self.client.fetch(str(cif), lambda: self._load(cif))

    def _load(self, cif):
        response = requests.get(
            CUISCAN_URL,
            params={"action": "company", "cui": cif},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else None


class CuifirmaClient:
    def __init__(self, store, limiter, ttl=7 * 86400):
        self.client = CachedClient(store, "cuifirma", limiter, ttl)

    def exact(self, cif, name):
        if not name:
            return None
        rows = self.client.fetch(f"q:{name}", lambda: self._search(name)) or []
        wanted = str(cif)
        for row in rows:
            if str(row.get("cui")) == wanted:
                return row
        return None

    def by_cui(self, cif):
        return self.exact(cif, str(cif))

    def _search(self, name):
        response = requests.get(
            CUIFIRMA_URL,
            params={"q": name},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        rows = data.get("results") or []
        return rows if isinstance(rows, list) else []


class UrlChecker:
    def __init__(self, store, limiter=None, ttl=3600):
        self.client = CachedClient(store, "url", limiter or RateLimiter(0.2), ttl)

    def exists(self, url):
        return self.client.fetch(url, lambda: self._head(url)) is True

    def _head(self, url):
        response = requests.head(
            url, allow_redirects=True, timeout=TIMEOUT,
            headers={"User-Agent": USER_AGENT})
        return 200 <= response.status_code < 400
