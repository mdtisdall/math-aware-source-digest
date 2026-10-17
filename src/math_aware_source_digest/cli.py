"""The ``masd`` command."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, config, net


def _config_json(cfg: config.Config) -> str:
    def default(value: object) -> object:
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, tuple):
            return list(value)
        raise TypeError(type(value).__name__)

    return json.dumps(dataclasses.asdict(cfg), default=default, indent=2)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="masd", description=__doc__)
    parser.add_argument("--version", action="version", version=f"masd {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("config", help="print the configuration in effect, and the files it came from")
    policy = sub.add_parser("policy", help="say whether the download policy allows a URL")
    policy.add_argument("url")
    resolve = sub.add_parser(
        "resolve", help="resolve DOIs, arXiv IDs, ISBNs, titles or zotero:<key> items (JSON out)"
    )
    resolve.add_argument("inputs", nargs="+")
    resolve.add_argument("--zotero", action="store_true", help="use Zotero's local API")
    args = parser.parse_args(argv)

    try:
        cfg = config.load()
    except config.ConfigError as ex:
        print(f"masd: configuration error: {ex}", file=sys.stderr)
        return 2

    if args.command == "config":
        print(_config_json(cfg))
        return 0
    if args.command == "policy":
        try:
            net.DownloadPolicy(cfg.downloads.allowed_hosts).check(args.url)
        except net.ApprovalRequired as ex:
            print(f"needs approval: host {ex.host} is not in downloads.allowed_hosts")
            return 1
        except net.NetError as ex:
            print(f"refused: {ex}")
            return 1
        print("allowed")
        return 0
    if args.command == "resolve":
        from .resolve import Resolver
        from .resolve.zotero import LocalZotero

        resolver = Resolver(net.Fetcher(cfg), LocalZotero() if args.zotero else None)
        results = resolver.resolve_many(args.inputs)
        print(json.dumps([r.to_json() for r in results], indent=2, ensure_ascii=False, default=str))
        return 0 if all(r.found for r in results) else 1
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
