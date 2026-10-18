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
    exact_source: str = ""  # a committed exact form (arXiv TeX), relative to the repository

    def committed_path(self, list_path: Path) -> Path:
        """Where the PDF is committed: testdata/papers/<key>.pdf next to the list."""
        return list_path.parent / "papers" / f"{self.key}.pdf"

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


def pdf_path(paper: Paper, list_path: Path, cfg: Config) -> Path:
    """The paper's PDF: the committed copy first, else the cache; checked against its hash."""
    for path in (paper.committed_path(list_path), paper.cached_path(cfg)):
        if path is not None and path.is_file():
            if sha256_file(path) != paper.sha256:
                raise TestDataError(f"{path}: its SHA-256 differs from the pinned one")
            return path
    raise TestDataError(f"{paper.key}: no committed or cached PDF; run masd testdata fetch")


def verify(papers: list[Paper], list_path: Path) -> list[str]:
    """Problems with the committed PDFs and exact sources (empty: all present and intact)."""
    problems = []
    for paper in papers:
        path = paper.committed_path(list_path)
        if not path.is_file():
            problems.append(f"{paper.key}: {path} is missing")
        elif sha256_file(path) != paper.sha256:
            problems.append(f"{paper.key}: {path} does not match its pinned SHA-256")
        if paper.exact_source and not (list_path.parent.parent / paper.exact_source).is_dir():
            problems.append(f"{paper.key}: exact source {paper.exact_source} is missing")
    return problems


def verify_remote(paper: Paper, cfg: Config, fetcher: net.Fetcher | None = None) -> str:
    """Compare the original source with the pinned hash: "same", "changed: ...", or why not checked.

    Downloads the file again (into memory only) from its pinned URL; publishers that refuse
    scripts are reported for a check by hand.
    """
    if paper.fetch != "auto":
        return f"not checked: download by hand from {paper.url} and compare its SHA-256"
    policy = net.DownloadPolicy(cfg.downloads.allowed_hosts)
    policy.approve(paper.url)
    fetcher = fetcher or net.Fetcher(cfg, policy=policy, timeout_s=300)
    fetcher.policy = policy
    site = net.host_of(paper.url).split(".", 1)[-1]
    url = paper.url
    for _ in range(5):
        try:
            response = fetcher.get(url, cache=False)
            break
        except net.ApprovalRequired as ex:
            if not net.host_matches(ex.host, site):
                return f"not checked: redirected to another site ({ex.url})"
            policy.approve(ex.url)
            url = ex.url
    else:
        return "not checked: too many redirects"
    digest = sha256_bytes(response.content)
    return "same" if digest == paper.sha256 else f"changed: the source now has SHA-256 {digest}"


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
