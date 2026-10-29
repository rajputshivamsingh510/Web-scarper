"""HTTP client with retries/backoff, per-host rate limiting and robots.txt checks."""
from __future__ import annotations

import logging
import random
import threading
import time
from urllib import robotparser
from urllib.parse import urlsplit

import requests

from .stats import Stats

log = logging.getLogger("leadcollector.http")
ROBOTS_AGENT = "LeadCollector"
RETRY_STATUS = {429, 500, 502, 503, 504}


class RequestFailed(Exception):
    pass


def safe_url(url: str) -> str:
    """Strip query strings before logging so keys/tokens never reach logs."""
    p = urlsplit(url)
    return f"{p.scheme}://{p.netloc}{p.path}"


class HttpClient:
    def __init__(self, user_agent: str, timeout: float = 20, max_retries: int = 4,
                 min_interval: float = 1.0, backoff_base: float = 2.0, stats: Stats | None = None):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_interval = min_interval
        self.backoff_base = backoff_base
        self.stats = stats or Stats()
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()

    def _wait(self, key: str) -> None:
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._last.get(key, 0.0) + self.min_interval)
            self._last[key] = slot
        if slot > now:
            time.sleep(slot - now)

    def request(self, method: str, url: str, rate_key: str | None = None, **kw) -> requests.Response:
        key = rate_key or (urlsplit(url).netloc)
        retries = kw.pop('max_retries', self.max_retries)
        timeout = kw.pop('timeout', self.timeout)
        last_err = "unknown error"
        for attempt in range(retries + 1):
            self._wait(key)
            delay = self.backoff_base * (2 ** attempt)
            try:
                resp = self.session.request(method, url, timeout=timeout, **kw)
                self.stats.add("requests")
                log.debug("%s %s -> %s", method, safe_url(url), resp.status_code)
                if resp.status_code not in RETRY_STATUS:
                    return resp
                last_err = f"HTTP {resp.status_code}"
                retry_after = resp.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = max(delay, min(int(retry_after), 120))
            except requests.exceptions.SSLError as exc:  # bad certificate: retrying will not help
                self.stats.add("failed_requests")
                raise RequestFailed(f"{safe_url(url)}: SSLError") from exc
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_err = type(exc).__name__
                text = str(exc)
                if any(m in text for m in ("getaddrinfo failed", "NameResolutionError",
                                           "Name or service not known", "nodename nor servname")):
                    self.stats.add("failed_requests")  # domain does not resolve: permanent
                    raise RequestFailed(f"{safe_url(url)}: DNSError") from exc
            except requests.RequestException as exc:  # invalid URL, too many redirects, ...
                self.stats.add("failed_requests")
                raise RequestFailed(f"{safe_url(url)}: {type(exc).__name__}") from exc
            if attempt < retries:
                delay = min(delay, 90) + random.random()
                log.warning("Retry %d/%d for %s (%s) in %.1fs", attempt + 1, retries,
                            safe_url(url), last_err, delay)
                time.sleep(delay)
        self.stats.add("failed_requests")
        raise RequestFailed(f"{safe_url(url)}: {last_err}")

    def get(self, url: str, **kw) -> requests.Response:
        return self.request("GET", url, **kw)

    def post(self, url: str, **kw) -> requests.Response:
        return self.request("POST", url, **kw)


class RobotsCache:
    """robots.txt decisions, cached per origin. Conservative on server errors."""

    def __init__(self, client: HttpClient):
        self.client = client
        self._cache: dict[str, robotparser.RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def _load(self, origin: str):
        rp = robotparser.RobotFileParser()
        try:
            resp = self.client.get(origin + "/robots.txt", max_retries=1, timeout=10)
        except RequestFailed:
            return None
        if resp.status_code == 200:
            rp.parse(resp.text.splitlines())
            return rp
        if 400 <= resp.status_code < 500:
            rp.allow_all = True
            return rp
        return None

    def status(self, url: str) -> str:
        """'allowed' | 'disallowed' | 'unreachable'"""
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        with self._lock:
            known = origin in self._cache
            rp = self._cache.get(origin)
        if not known:
            rp = self._load(origin)
            with self._lock:
                self._cache[origin] = rp
        if rp is None:
            return "unreachable"
        return "allowed" if rp.can_fetch(ROBOTS_AGENT, url) else "disallowed"
