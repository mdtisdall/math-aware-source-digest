"""The configuration: defaults, then the user's file, then the project's file.

The user's file is ``~/.config/math-aware-source-digest/config.toml``. The
project's file is ``masd.toml`` in the current directory or the nearest parent
directory. A later file replaces the values that it sets, key by key.

Example ``masd.toml``::

    [output]
    dir = "sources"
    index = "README.md"

    [downloads]
    # Hosts that need no approval for each download. A host also covers its
    # subdomains. Empty (the default): every download asks.
    allowed_hosts = ["arxiv.org", "ncbi.nlm.nih.gov"]

    [network]
    # Sent to Crossref, OpenAlex and Unpaywall only if set.
    contact_email = ""
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_FILE = "masd.toml"


class ConfigError(Exception):
    """A configuration file is not valid."""


def default_cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "math-aware-source-digest"


def user_config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "math-aware-source-digest" / "config.toml"


@dataclass(frozen=True)
class OutputConfig:
    dir: str = "sources"
    index: str = "README.md"


@dataclass(frozen=True)
class DownloadConfig:
    allowed_hosts: tuple[str, ...] = ()


@dataclass(frozen=True)
class NetworkConfig:
    contact_email: str = ""
    # Seconds between two requests to the same host, and the hosts that need more.
    min_interval_s: float = 1.0
    host_intervals_s: dict[str, float] = field(default_factory=lambda: {"arxiv.org": 3.0})
    max_retries: int = 4


@dataclass(frozen=True)
class Config:
    output: OutputConfig = field(default_factory=OutputConfig)
    downloads: DownloadConfig = field(default_factory=DownloadConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    cache_root: Path = field(default_factory=default_cache_root)
    sources: tuple[Path, ...] = ()


def find_project_file(start: Path) -> Path | None:
    for directory in (start, *start.parents):
        candidate = directory / PROJECT_FILE
        if candidate.is_file():
            return candidate
    return None


def _read(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as ex:
        raise ConfigError(f"{path}: {ex}") from ex


def _table(data: dict[str, Any], name: str, path: Path) -> dict[str, Any]:
    value = data.get(name, {})
    if not isinstance(value, dict):
        raise ConfigError(f"{path}: [{name}] must be a table")
    return value


def _check_keys(table: dict[str, Any], allowed: set[str], name: str, path: Path) -> None:
    unknown = set(table) - allowed
    if unknown:
        raise ConfigError(f"{path}: unknown keys in [{name}]: {', '.join(sorted(unknown))}")


def _merge(config: Config, data: dict[str, Any], path: Path) -> Config:
    _check_keys(data, {"output", "downloads", "network", "cache"}, "top level", path)
    out = _table(data, "output", path)
    _check_keys(out, {"dir", "index"}, "output", path)
    dl = _table(data, "downloads", path)
    _check_keys(dl, {"allowed_hosts"}, "downloads", path)
    net = _table(data, "network", path)
    _check_keys(
        net, {"contact_email", "min_interval_s", "host_intervals_s", "max_retries"}, "network", path
    )
    cache = _table(data, "cache", path)
    _check_keys(cache, {"root"}, "cache", path)

    hosts = dl.get("allowed_hosts", list(config.downloads.allowed_hosts))
    if not isinstance(hosts, list) or not all(isinstance(h, str) and h for h in hosts):
        raise ConfigError(f"{path}: downloads.allowed_hosts must be a list of host names")
    intervals = dict(config.network.host_intervals_s)
    intervals.update(net.get("host_intervals_s", {}))
    root = cache.get("root")
    return Config(
        output=OutputConfig(
            dir=str(out.get("dir", config.output.dir)),
            index=str(out.get("index", config.output.index)),
        ),
        downloads=DownloadConfig(allowed_hosts=tuple(h.lower().strip(".") for h in hosts)),
        network=NetworkConfig(
            contact_email=str(net.get("contact_email", config.network.contact_email)),
            min_interval_s=float(net.get("min_interval_s", config.network.min_interval_s)),
            host_intervals_s={k.lower(): float(v) for k, v in intervals.items()},
            max_retries=int(net.get("max_retries", config.network.max_retries)),
        ),
        cache_root=Path(root).expanduser() if root else config.cache_root,
        sources=(*config.sources, path),
    )


def check_cache_root(root: Path) -> None:
    """Refuse a cache inside a git repository: full texts must never be committed."""
    resolved = root.expanduser().resolve()
    for directory in (resolved, *resolved.parents):
        if (directory / ".git").exists():
            raise ConfigError(
                f"the cache root {root} is inside the git repository {directory}; "
                "put it outside any repository"
            )


def load(cwd: Path | None = None, user_file: Path | None = None) -> Config:
    """Return the configuration for a project in ``cwd`` (default: the current directory)."""
    config = Config()
    for path in (user_file or user_config_path(), find_project_file(cwd or Path.cwd())):
        if path is not None and path.is_file():
            config = _merge(config, _read(path), path)
    check_cache_root(config.cache_root)
    return config
