"""The ``masd`` command."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, config, entry, net


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
    sub.add_parser(
        "render",
        help="validate every <key>.json in the output directory, render "
        "its Markdown, and write the index",
    )
    flag = sub.add_parser(
        "flag",
        help="crop each display equation of a Marker conversion, transcribe it again "
        "with a local model, and flag disagreements (needs a running Ollama server)",
    )
    flag.add_argument("pdf", type=Path)
    flag.add_argument("marker_json", type=Path)
    flag.add_argument("out_dir", type=Path)
    flag.add_argument("--model", default="qwen3-vl:32b-instruct")
    flag.add_argument("--ollama", default="http://127.0.0.1:11434")
    testdata = sub.add_parser("testdata", help="the pinned test papers: list, fetch, import")
    testdata.add_argument("action", choices=["list", "fetch", "import"])
    testdata.add_argument("files", nargs="*", type=Path)
    testdata.add_argument("--list", type=Path, default=Path("testdata/papers.toml"))
    validate = sub.add_parser("validate", help="validate entry JSON files")
    validate.add_argument("files", nargs="+", type=Path)
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
    if args.command == "flag":
        from . import flag as flagging
        from . import marker
        from .local.ollama import LocalModelError, OllamaClient

        doc = json.loads(args.marker_json.read_text())
        spans = [
            flagging.Span(f"eq{i:03d}", b.page_index, b.box, marker.latex_of(b.html))
            for i, b in enumerate(marker.equations(doc))
        ]
        try:
            client = OllamaClient(base=args.ollama)
            flagged_spans = flagging.flag_spans(
                args.pdf, spans, flagging.transcriber(client, args.model), args.out_dir / "crops"
            )
        except LocalModelError as ex:
            print(f"masd: {ex}", file=sys.stderr)
            return 1
        flagging.write_flags(
            flagged_spans, args.out_dir / "flags.json", {"model": args.model, "pdf": args.pdf.name}
        )
        flagged = sum(1 for r in flagged_spans if r.flags)
        total = len(flagged_spans)
        print(f"{flagged} of {total} equations flagged; {args.out_dir / 'flags.json'}")
        return 0
    if args.command == "testdata":
        from . import testdata as td

        try:
            papers = td.load(args.list)
            if args.action == "list":
                for paper in papers:
                    where = paper.cached_path(cfg)
                    print(
                        f"{paper.key:28} {','.join(paper.roles):14} {paper.licence:13} "
                        f"{paper.fetch:6} {'cached' if where else 'missing'}"
                    )
            elif args.action == "fetch":
                status = 0
                for paper in papers:
                    try:
                        print(f"{paper.key}: {td.fetch(paper, cfg)}")
                    except (td.TestDataError, net.NetError) as ex:
                        print(f"{paper.key}: {ex}", file=sys.stderr)
                        status = 1
                return status
            else:
                for path in args.files:
                    print(f"{path}: {td.import_file(path, papers, cfg).key}")
        except td.TestDataError as ex:
            print(f"masd: {ex}", file=sys.stderr)
            return 1
        return 0
    if args.command == "validate":
        status = 0
        for path in args.files:
            problems = entry.validate(json.loads(path.read_text()))
            print(f"{path}: {'invalid' if problems else 'valid'}")
            for error in problems.errors:
                print(f"  {error}")
            status = status or (1 if problems else 0)
        return status
    if args.command == "render":
        out_dir = Path(cfg.output.dir)
        render_cfg = entry.render_config(cfg.output)
        try:
            for path in sorted(out_dir.glob("*.json")):
                entry.write_entry(json.loads(path.read_text()), out_dir, render_cfg)
            index = entry.write_index(out_dir, cfg.output.index)
        except entry.EntryError as ex:
            print(f"masd: {ex}", file=sys.stderr)
            return 1
        print(f"rendered {len(list(out_dir.glob('*.json')))} entries; index {index}")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    sys.exit(main())
