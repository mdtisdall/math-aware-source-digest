"""HTTP for every stage: the download policy, spacing per host, backoff, and a cache.

All network access of the package goes through :class:`Fetcher`.

- **Policy.** A request to a host that the configuration does not list
  raises :class:`ApprovalRequired`, unless that exact URL was approved. The
  tool never adds a host on its own, and never because a source's text names
  it. Only ``https`` is allowed.
- **Spacing.** Requests to one host wait at least the configured interval
  (arXiv: 3 s).
- **Backoff.** HTTP 429 and 503 are retried after ``Retry-After`` (or an
  exponential wait), at most ``max_retries`` times; then :class:`RateLimited`.
- **Cache.** Each answer is stored under ``<cache root>/http/``, keyed by the
  method, the URL and the body, so that a run can be repeated without the
  network.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests

from . import __version__
from .config import Config

RETRY_STATUSES = frozenset({429, 503})
MAX_REDIRECTS = 5
BACKOFF_BASE_S = 5.0
BACKOFF_MAX_S = 300.0


class NetError(Exception):
    """A request could not be made or failed."""


class ApprovalRequired(NetError):
    """The host is not in the download policy, and the URL was not approved."""

    def __init__(self, url: str, host: str) -> None:
        super().__init__(f"download from {host} needs the user's approval: {url}")
        self.url = url
        self.host = host


class RateLimited(NetError):
    """The host still refused after the last retry."""


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    headers: dict[str, str]
    content: bytes
    from_cache: bool = False

    def json(self) -> Any:
        return json.loads(self.content)

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().rstrip(".")


def host_matches(host: str, pattern: str) -> bool:
    """``pattern`` covers itself and its subdomains (``arxiv.org`` covers ``export.arxiv.org``)."""
    pattern = pattern.lower().strip(".")
    return host == pattern or host.endswith("." + pattern)


class DownloadPolicy:
    def __init__(self, allowed_hosts: Iterable[str], approved_urls: Iterable[str] = ()) -> None:
        self.allowed_hosts = tuple(allowed_hosts)
        self.approved_urls = set(approved_urls)

    def approve(self, url: str) -> None:
        """Record the user's approval of one URL (not of its host)."""
        self.approved_urls.add(url)

    def check(self, url: str) -> None:
        parts = urlsplit(url)
        if parts.scheme != "https":
            raise NetError(f"only https URLs are allowed: {url}")
        host = host_of(url)
        if not host:
            raise NetError(f"no host in URL: {url}")
        if url in self.approved_urls:
            return
        if any(host_matches(host, pattern) for pattern in self.allowed_hosts):
            return
        raise ApprovalRequired(url, host)


def retry_after_s(value: str | None, attempt: int, now: float) -> float:
    """Seconds to wait: ``Retry-After`` (seconds or a date), else exponential."""
    if value:
        try:
            return min(max(float(value), 0.0), BACKOFF_MAX_S)
        except ValueError:
            try:
                return min(max(parsedate_to_datetime(value).timestamp() - now, 0.0), BACKOFF_MAX_S)
            except (TypeError, ValueError):
                pass
    return min(BACKOFF_BASE_S * 2.0**attempt, BACKOFF_MAX_S)


class Fetcher:
    def __init__(
        self,
        config: Config,
        policy: DownloadPolicy | None = None,
        session: requests.Session | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        timeout_s: float = 60.0,
    ) -> None:
        self.config = config
        self.policy = policy or DownloadPolicy(config.downloads.allowed_hosts)
        self.session = session or requests.Session()
        agent = f"math-aware-source-digest/{__version__}"
        if config.network.contact_email:
            agent += f" (mailto:{config.network.contact_email})"
        self.session.headers["User-Agent"] = agent
        self.clock, self.wall_clock, self.sleep = clock, wall_clock, sleep
        self.timeout_s = timeout_s
        self.cache_dir = config.cache_root / "http"
        self._last_request: dict[str, float] = {}

    def interval_for(self, host: str) -> float:
        net = self.config.network
        for pattern, seconds in net.host_intervals_s.items():
            if host_matches(host, pattern):
                return seconds
        return net.min_interval_s

    def _wait_turn(self, host: str) -> None:
        last = self._last_request.get(host)
        if last is not None:
            remaining = self.interval_for(host) - (self.clock() - last)
            if remaining > 0:
                self.sleep(remaining)
        self._last_request[host] = self.clock()

    def _cache_path(self, method: str, url: str, body: bytes | None) -> Path:
        key = hashlib.sha256(b"\0".join([method.encode(), url.encode(), body or b""])).hexdigest()
        return self.cache_dir / key[:2] / key

    def _load_cached(self, path: Path) -> Response | None:
        meta_path = path.with_suffix(".json")
        if not (meta_path.is_file() and path.is_file()):
            return None
        meta = json.loads(meta_path.read_text())
        return Response(meta["url"], meta["status"], meta["headers"], path.read_bytes(), True)

    def _store(self, path: Path, response: Response) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        tmp.write_bytes(response.content)
        tmp.replace(path)
        meta = {"url": response.url, "status": response.status, "headers": response.headers}
        path.with_suffix(".json").write_text(json.dumps(meta))

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
        refresh: bool = False,
        cache: bool = True,
        _redirects: int = 0,
    ) -> Response:
        """Make one request under the policy; raise :class:`NetError` unless the status is 2xx."""
        prepared = requests.Request(method, url, params=params, json=json_body, headers=headers)
        full = self.session.prepare_request(prepared)
        full_url = str(full.url)
        self.policy.check(full_url)
        body = full.body.encode() if isinstance(full.body, str) else full.body
        path = self._cache_path(method, full_url, body)
        if cache and not refresh:
            cached = self._load_cached(path)
            if cached is not None:
                return cached

        host = host_of(full_url)
        retries = self.config.network.max_retries
        for attempt in range(retries + 1):
            self._wait_turn(host)
            try:
                raw = self.session.send(full, timeout=self.timeout_s, allow_redirects=False)
            except requests.RequestException as ex:
                raise NetError(f"{method} {full_url}: {ex}") from ex
            if raw.is_redirect:
                # A redirect may leave the policy: check the new URL, then follow it.
                if method != "GET":
                    raise NetError(f"{method} {full_url}: unexpected redirect")
                if _redirects >= MAX_REDIRECTS:
                    raise NetError(f"{method} {full_url}: more than {MAX_REDIRECTS} redirects")
                target = str(requests.compat.urljoin(full_url, raw.headers["Location"]))
                return self.request(
                    method,
                    target,
                    headers=headers,
                    refresh=refresh,
                    cache=cache,
                    _redirects=_redirects + 1,
                )
            if raw.status_code in RETRY_STATUSES:
                if attempt == retries:
                    raise RateLimited(
                        f"{method} {full_url}: HTTP {raw.status_code} after {retries} retries"
                    )
                self.sleep(
                    retry_after_s(raw.headers.get("Retry-After"), attempt, self.wall_clock())
                )
                continue
            if not 200 <= raw.status_code < 300:
                raise NetError(f"{method} {full_url}: HTTP {raw.status_code}")
            response = Response(full_url, raw.status_code, dict(raw.headers), raw.content)
            if cache:
                self._store(path, response)
            return response
        raise AssertionError("unreachable")

    def get(self, url: str, **kwargs: Any) -> Response:
        return self.request("GET", url, **kwargs)

    def post_json(self, url: str, body: Any, **kwargs: Any) -> Response:
        return self.request("POST", url, json_body=body, **kwargs)
