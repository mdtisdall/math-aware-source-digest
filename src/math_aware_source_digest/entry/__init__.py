"""Source entries: the schema, keys, validation, rendering and the index (plan section 1a).

The JSON file is the entry; the Markdown is rendered from it and is never
edited by hand.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
from jinja2 import ChoiceLoader, FileSystemLoader, PackageLoader
from jinja2.sandbox import SandboxedEnvironment

SCHEMA_VERSION = "1"
SECTIONS = (
    "citation",
    "version",
    "summary",
    "results",
    "notation",
    "spans",
    "coverage",
    "verification",
)
HEADINGS = {
    "citation": "Citation",
    "version": "Version",
    "summary": "Summary",
    "results": "Results",
    "notation": "Notation",
    "spans": "Cited spans",
    "coverage": "Not included",
    "verification": "Verification",
}
SPAN_REF = re.compile(r"\{\{s:([a-z][a-z0-9-]*)\}\}")


class EntryError(Exception):
    """An entry is not valid; it is not written."""


@cache
def schema() -> dict[str, Any]:
    text = resources.files(__package__).joinpath("entry.schema.json").read_text()
    data: dict[str, Any] = json.loads(text)
    return data


# Keys


def _ascii_surname(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")


def make_key(surnames: list[str], year: int | str | None, existing: Iterable[str] = ()) -> str:
    """``kaipio-somersalo-2007``, ``seeger-2010``; ``a``, ``b``, ... on a collision.

    One author: the surname; two: both; three or more: the first author's.
    """
    names = [_ascii_surname(s) for s in surnames if _ascii_surname(s)]
    parts = names[:2] if len(names) == 2 else names[:1]
    base = "-".join([*parts, str(year or "nd")]) if parts else f"anon-{year or 'nd'}"
    taken = set(existing)
    if base not in taken:
        return base
    for suffix in "abcdefghijklmnopqrstuvwxyz":
        if base + suffix not in taken:
            return base + suffix
    raise EntryError(f"too many entries with key {base}")


# Validation


@dataclass
class Problems:
    errors: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.errors)


def validate(entry: dict[str, Any]) -> Problems:
    """Schema validation, then the checks a schema cannot express."""
    problems = Problems()
    validator = jsonschema.Draft202012Validator(schema())
    for error in sorted(validator.iter_errors(entry), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(p) for p in error.absolute_path) or "(top)"
        problems.errors.append(f"{where}: {error.message}")
    if problems:
        return problems

    span_ids = [s["id"] for s in entry["spans"]]
    for dup in sorted({i for i in span_ids if span_ids.count(i) > 1}):
        problems.errors.append(f"spans: duplicate id {dup}")
    result_ids = [r["id"] for r in entry["results"]]
    for dup in sorted({i for i in result_ids if result_ids.count(i) > 1}):
        problems.errors.append(f"results: duplicate id {dup}")
    known = set(span_ids)
    for result in entry["results"]:
        refs = set(result["spans"]) | set(SPAN_REF.findall(result["statement"]))
        for ref in sorted(refs - known):
            problems.errors.append(f"results/{result['id']}: unknown span {ref}")
    for item in entry["notation"]:
        if item["symbol"] not in known:
            problems.errors.append(f"notation: unknown span {item['symbol']}")
    if SPAN_REF.search(entry["summary"]) and not set(SPAN_REF.findall(entry["summary"])) <= known:
        problems.errors.append("summary: unknown span reference")
    return problems


# Rendering


@dataclass(frozen=True)
class RenderConfig:
    template: Path | None = None  # a project's own template; default: the package's
    sections: tuple[str, ...] = SECTIONS
    headings: dict[str, str] = field(default_factory=lambda: dict(HEADINGS))


def render_config(output: Any) -> RenderConfig:
    """The RenderConfig for a :class:`~math_aware_source_digest.config.OutputConfig`."""
    return RenderConfig(
        template=Path(output.template) if output.template else None,
        sections=tuple(output.sections) or SECTIONS,
        headings={**HEADINGS, **output.headings},
    )


def _environment(cfg: RenderConfig) -> SandboxedEnvironment:
    loaders: list[Any] = []
    if cfg.template is not None:
        loaders.append(FileSystemLoader(str(cfg.template.parent)))
    loaders.append(PackageLoader(__package__, "templates"))
    env = SandboxedEnvironment(
        loader=ChoiceLoader(loaders),
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    env.filters["authors"] = format_authors
    env.filters["location"] = format_location
    env.filters["spanrefs"] = lambda text, spans: expand_span_refs(text, spans)
    env.filters["oneline"] = lambda text: " ".join(str(text).split())
    # A table cell: one line, and a pipe escaped so that it does not end the cell.
    env.filters["cell"] = lambda text: " ".join(str(text).split()).replace("|", "\\|")
    return env


def format_authors(authors: list[dict[str, str]]) -> str:
    names = [f"{a.get('family', '')}, {a.get('given', '')}".strip(", ") for a in authors]
    return "; ".join(names)


def format_location(loc: dict[str, Any]) -> str:
    parts = []
    if loc.get("label"):
        parts.append(str(loc["label"]))
    if loc.get("section"):
        parts.append(f"sec. {loc['section']}")
    if loc.get("printed_page"):
        parts.append(f"p. {loc['printed_page']}")
    if loc.get("pdf_page"):
        parts.append(f"PDF p. {loc['pdf_page']}")
    return ", ".join(parts)


def expand_span_refs(text: str, spans: dict[str, dict[str, Any]]) -> str:
    """Replace ``{{s:id}}`` with the span's LaTeX (inline) and its id."""

    def one(match: re.Match[str]) -> str:
        span = spans[match.group(1)]
        body = span.get("latex")
        shown = f"${body}$" if body is not None else f"“{span.get('text', '')}”"
        return f"{shown} [{span['id']}]"

    return SPAN_REF.sub(one, text)


def render(entry: dict[str, Any], cfg: RenderConfig | None = None) -> str:
    cfg = cfg or RenderConfig()
    unknown = set(cfg.sections) - set(SECTIONS)
    if unknown:
        raise EntryError(f"unknown sections: {', '.join(sorted(unknown))}")
    env = _environment(cfg)
    name = cfg.template.name if cfg.template is not None else "entry.md.j2"
    spans = {s["id"]: s for s in entry["spans"]}
    return env.get_template(name).render(
        e=entry, spans=spans, sections=cfg.sections, headings={**HEADINGS, **cfg.headings}
    )


# Writing and the index


def write_entry(entry: dict[str, Any], out_dir: Path, cfg: RenderConfig | None = None) -> Path:
    """Validate, then write ``<key>.json`` and ``<key>.md``; refuse an invalid entry."""
    problems = validate(entry)
    if problems:
        raise EntryError("entry not written:\n  " + "\n  ".join(problems.errors))
    out_dir.mkdir(parents=True, exist_ok=True)
    key = entry["key"]
    markdown = render(entry, cfg)
    for path, text in (
        (out_dir / f"{key}.json", json.dumps(entry, indent=2, ensure_ascii=False) + "\n"),
        (out_dir / f"{key}.md", markdown),
    ):
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_text(text)
        tmp.replace(path)
    return out_dir / f"{key}.json"


def span_counts(entry: dict[str, Any]) -> dict[str, int]:
    counts = {"exact": 0, "verified": 0, "unverified": 0}
    for span in entry["spans"]:
        counts[span["status"]] += 1
    return counts


def index_line(entry: dict[str, Any]) -> str:
    c = entry["citation"]
    authors = c["authors"]["value"]
    first = authors[0]["family"] if authors else "?"
    who = (
        first
        if len(authors) == 1
        else (f"{first} and {authors[1]['family']}" if len(authors) == 2 else f"{first} et al.")
    )
    title = " ".join(str(c["title"]["value"]).split())
    v = entry["version"]
    licence = entry.get("licence", {}).get("value", "unknown")
    n = span_counts(entry)
    status = f"{n['exact']} exact, {n['verified']} verified, {n['unverified']} unverified"
    unchecked_fields = [k for k, f in c.items() if f["status"] == "unverified"]
    if unchecked_fields:
        status += f"; citation unverified: {', '.join(unchecked_fields)}"
    return (
        f"- [{entry['key']}]({entry['key']}.md): {who} ({c['year']['value']}), *{title}*. "
        f"Version: {v['describes']}; form: {v['form']}; licence: {licence}; spans: {status}."
    )


def write_index(out_dir: Path, name: str = "README.md") -> Path:
    entries = []
    for path in sorted(out_dir.glob("*.json")):
        entry = json.loads(path.read_text())
        if validate(entry):
            raise EntryError(f"{path}: not a valid entry; fix it before writing the index")
        entries.append(entry)
    lines = [
        "# Sources",
        "",
        "Annotated bibliography, written by math-aware-source-digest from the JSON entries "
        "in this directory. Do not edit; edit the JSON and render again.",
        "",
    ]
    lines += [index_line(e) for e in sorted(entries, key=lambda e: e["key"])]
    path = out_dir / name
    path.write_text("\n".join(lines) + "\n")
    return path
