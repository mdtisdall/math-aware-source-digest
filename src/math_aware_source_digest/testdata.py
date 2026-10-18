"""The pinned test papers (``testdata/papers.toml``): list, fetch, import.

A test paper is identified by its SHA-256. ``fetch`` downloads the papers that
allow it, each from its pinned URL only (that URL, and redirects on the same
site, count as approved: the list itself is the approval); a file whose hash
differs is refused. ``import`` adds papers that a person downloaded by hand,
recognized by their hash.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from . import net
from .cache import SourceCache, sha256_bytes, sha256_file
from .config import Config

ALLOWED_LICENCES = {"public-domain", "CC0-1.0", "CC-BY-3.0", "CC-BY-4.0", "CC-BY-SA-4.0"}
ROLES = {"judged", "latex", "jats", "open", "example", "reserve"}
DEFAULT_LIST = Path("testdata/papers.toml")


class TestDataError(Exception):
    pass


@dataclass(frozen=True)
class Paper:
    key: str
    id: str
    title: str
    url: str
    fetch: str
    sha256: str
    bytes: int
    pages: int
    licence: str
    licence_source: str
    roles: tuple[str, ...]
    form: str
    faces: str
    tests: str

    def cache(self, cfg: Config) -> SourceCache:
        return SourceCache(cfg.cache_root, self.id)

    def cached_path(self, cfg: Config) -> Path | None:
        path = self.cache(cfg).files / f"{self.sha256}.pdf"
        return path if path.is_file() else None


def load(path: Path = DEFAULT_LIST) -> list[Paper]:
    data = tomllib.loads(path.read_text())
    papers = []
    for raw in data.get("paper", []):
        raw = dict(raw)
        raw["roles"] = tuple(raw.get("roles", ()))
        try:
            papers.append(Paper(**raw))
        except TypeError as ex:
            raise TestDataError(f"{path}: {raw.get('key', '?')}: {ex}") from ex
    problems = check(papers)
    if problems:
        raise TestDataError(f"{path}:\n  " + "\n  ".join(problems))
    return papers


def check(papers: list[Paper]) -> list[str]:
    """The rules of the list: unique keys and hashes, allowed licences and roles."""
    problems = []
    for field_name in ("key", "sha256", "id"):
        values = [getattr(p, field_name) for p in papers]
        for dup in sorted({v for v in values if values.count(v) > 1}):
            problems.append(f"duplicate {field_name}: {dup}")
    for p in papers:
        if p.licence not in ALLOWED_LICENCES:
            problems.append(f"{p.key}: licence {p.licence!r} is not allowed for test data")
        if not p.licence_source:
            problems.append(f"{p.key}: no licence_source")
        if not set(p.roles) <= ROLES or not p.roles:
            problems.append(f"{p.key}: roles must be some of {sorted(ROLES)}")
        if p.fetch not in ("auto", "manual"):
            problems.append(f"{p.key}: fetch must be 'auto' or 'manual'")
        if urlsplit(p.url).scheme != "https":
            problems.append(f"{p.key}: url must be https")
        if len(p.sha256) != 64 or any(c not in "0123456789abcdef" for c in p.sha256):
            problems.append(f"{p.key}: sha256 must be 64 lower-case hex digits")
    return problems


def fetch(paper: Paper, cfg: Config, fetcher: net.Fetcher | None = None) -> Path:
    """Download one paper from its pinned URL, check its hash, store it in the cache."""
    existing = paper.cached_path(cfg)
    if existing is not None:
        return existing
    if paper.fetch != "auto":
        raise TestDataError(
            f"{paper.key}: download it by hand from {paper.url}, "
            f"then run: masd testdata import <file>"
        )
    policy = net.DownloadPolicy(cfg.downloads.allowed_hosts)
    policy.approve(paper.url)
    fetcher = fetcher or net.Fetcher(cfg, policy=policy, timeout_s=300)
    fetcher.policy = policy
    site = net.host_of(paper.url)
    url = paper.url
    for _ in range(5):
        try:
            response = fetcher.get(url, cache=False)
            break
        except net.ApprovalRequired as ex:
            if not net.host_matches(ex.host, site.split(".", 1)[-1]):
                raise TestDataError(
                    f"{paper.key}: {paper.url} redirects to another site: {ex.url}"
                ) from ex
            policy.approve(ex.url)
            url = ex.url
    else:
        raise TestDataError(f"{paper.key}: too many redirects")
    digest = sha256_bytes(response.content)
    if digest != paper.sha256:
        raise TestDataError(
            f"{paper.key}: the download's SHA-256 is {digest}, not the pinned "
            f"{paper.sha256}; not stored"
        )
    return paper.cache(cfg).store_bytes(response.content, "pdf")


def import_file(path: Path, papers: list[Paper], cfg: Config) -> Paper:
    """Add a file downloaded by hand, recognized by its SHA-256."""
    digest = sha256_file(path)
    for paper in papers:
        if paper.sha256 == digest:
            paper.cache(cfg).store_file(path, "pdf")
            return paper
    raise TestDataError(f"{path}: its SHA-256 {digest} matches no pinned test paper")
