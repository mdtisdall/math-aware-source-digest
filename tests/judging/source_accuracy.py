"""Gate 1: measure the judges' accuracy against a paper's own LaTeX (plan 6.1).

    uv run python tests/judging/source_accuracy.py <paper key>

For a test paper with an exact source (papers.toml: exact_source), this reads
the display equations of the source, expands the paper's own macros, and
compares each judge's transcription of the same printed equation number with
the comparison of stage 5 (strict and style levels). Only numbered equations
are measured: the number is the one link between the source and the page
that does not depend on any judge.

The source is the arXiv LaTeX, and the judged PDF is the version of record;
a difference may therefore be a judge's error or a change between versions.
The report lists every difference with both readings, for a person to
classify; the tool itself does not decide which it is.

Writes ground_truth/<key>/source-accuracy.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from math_aware_source_digest import testdata  # noqa: E402
from math_aware_source_digest.compare import compare  # noqa: E402

OUT = ROOT / "ground_truth"

# Commands of the changes package in its "final" mode: what the reader sees.
_KEEP_FIRST = {"added": 1, "replaced": 2, "highlight": 1}
_DROP = {"deleted": 1, "label": 1, "phantom": 1, "comment": 1}
# Commands with no mathematical content that the judges cannot see.
_INVISIBLE = ("nonumber", "notag")
# Display environments that this tool reads; any other display environment in
# a source stops it, so that no equation is silently missed.
_NUMBERED = ("equation",)
_OTHER_DISPLAY = re.compile(
    r"\\begin\{(?:equation\*|align\*?|gather\*?|multline\*?|eqnarray\*?|displaymath)\}|\\\[|\$\$"
)


@dataclass
class SourceEquation:
    number: int
    line: int  # line of \begin{equation} in the source file
    latex: str  # after expanding the paper's macros
    drawn: bool = False  # it contains a symbol that the source draws (TikZ)


@dataclass
class Result:
    number: int
    line: int
    source: str
    judge: int
    found: bool
    judged: str
    pdf_page: int | None
    level: str  # same | style | strict | missing | drawn (a person compares it)


def strip_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%[^\n]*", "", text)


def read_group(text: str, i: int) -> tuple[str, int]:
    """The argument that starts at text[i] (after spaces): a brace group or a
    single token. Returns its content and the index after it."""
    while i < len(text) and text[i] in " \t\n":
        i += 1
    if i >= len(text):
        raise ValueError("argument expected at the end of the text")
    if text[i] != "{":
        m = re.compile(r"\\[A-Za-z]+|\\.|.").match(text, i)
        assert m is not None
        return m.group(0), m.end()
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "\\":
            continue
        if text[j] == "{" and (j == 0 or text[j - 1] != "\\"):
            depth += 1
        elif text[j] == "}" and text[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return text[i + 1 : j], j + 1
    raise ValueError(f"unbalanced braces from {text[i : i + 40]!r}")


@dataclass
class Macro:
    args: int
    body: str


def definitions(preamble: str) -> dict[str, Macro]:
    """\\newcommand and \\DeclareMathOperator definitions of the preamble."""
    macros: dict[str, Macro] = {}
    for m in re.finditer(r"\\(?:re)?newcommand\*?\s*\{?\\([A-Za-z]+)\}?\s*(?:\[(\d)\])?", preamble):
        body, _ = read_group(preamble, m.end())
        macros[m.group(1)] = Macro(int(m.group(2) or 0), body)
    for m in re.finditer(r"\\DeclareMathOperator(\*?)\s*\{\\([A-Za-z]+)\}", preamble):
        text, _ = read_group(preamble, m.end())
        macros[m.group(2)] = Macro(0, f"\\operatorname{m.group(1)}{{{text}}}")
    return macros


def acronyms(text: str) -> dict[str, str]:
    """\\newacronym{key}{short}{long}: the short form, as \\gls prints it."""
    out: dict[str, str] = {}
    for m in re.finditer(r"\\newacronym\s*\{([^}]*)\}", text):
        short, _ = read_group(text, m.end())
        out[m.group(1)] = short.strip("{}")
    return out


def expand(text: str, macros: dict[str, Macro], short: dict[str, str]) -> str:
    """Expand the paper's macros, \\gls, and the final form of the changes
    package. Macros whose body draws a picture (TikZ) stay as they are: no
    LaTeX transcription can match a drawing, so a person compares them."""
    pattern = re.compile(r"\\([A-Za-z]+)\*?")
    for _ in range(50):  # macros may expand to macros
        out: list[str] = []
        i = 0
        changed = False
        while (m := pattern.search(text, i)) is not None:
            name = m.group(1)
            out.append(text[i : m.start()])
            j = m.end()
            if name in _DROP:
                for _ in range(_DROP[name]):
                    _, j = read_group(text, j)
                changed = True
            elif name in _KEEP_FIRST:
                first, j = read_group(text, j)
                for _ in range(_KEEP_FIRST[name] - 1):
                    _, j = read_group(text, j)
                out.append(first)
                changed = True
            elif name in ("gls", "glspl", "Gls", "acrshort"):
                key, j = read_group(text, j)
                out.append(short[key] + ("s" if name == "glspl" else ""))
                changed = True
            elif name == "vdotswithin":
                _, j = read_group(text, j)
                out.append("\\vdots")
                changed = True
            elif name in _INVISIBLE:
                changed = True
            elif name in macros and "\\tikz" not in macros[name].body:
                macro = macros[name]
                body = macro.body
                for n in range(1, macro.args + 1):
                    arg, j = read_group(text, j)
                    # A space keeps a command in the body from running into the
                    # argument (\lVert#1 with x must not become \lVertx).
                    body = re.sub(rf"(\\[A-Za-z]+)#{n}", rf"\1 #{n}", body).replace(f"#{n}", arg)
                out.append(body)
                changed = True
            else:
                out.append(m.group(0))
            i = j
        out.append(text[i:])
        text = "".join(out)
        if not changed:
            return re.sub(r"\s+", " ", text).strip()
    raise ValueError("macro expansion does not end")


def source_equations(main_tex: Path) -> list[SourceEquation]:
    raw = main_tex.read_text()
    text = strip_comments(raw)
    preamble, _, body = text.partition("\\begin{document}")
    short: dict[str, str] = {}
    for m in re.finditer(r"\\input\{([^}]+)\}", preamble):
        included = main_tex.parent / (m.group(1) + ("" if m.group(1).endswith(".tex") else ".tex"))
        short.update(acronyms(strip_comments(included.read_text())))
    macros = definitions(preamble)
    pictures = [name for name, macro in macros.items() if "\\tikz" in macro.body]
    if other := _OTHER_DISPLAY.search(body):
        raise ValueError(f"display maths that this tool does not read: {other.group(0)}")
    equations: list[SourceEquation] = []
    env = "|".join(_NUMBERED)
    for m in re.finditer(rf"\\begin\{{({env})\}}(.*?)\\end\{{\1\}}", body, re.S):
        content = m.group(2)
        if re.search(r"\\(?:nonumber|notag|tag)\b", content):
            raise ValueError(f"an unnumbered or retagged equation: {content[:60]!r}")
        # The line in the file (comments were removed within lines only).
        start = raw.find("\\begin{document}")
        nth = body[: m.start()].count(f"\\begin{{{m.group(1)}}}")
        line = _nth_line(raw, start, f"\\begin{{{m.group(1)}}}", nth)
        latex = expand(content, macros, short)
        drawn = any(re.search(rf"\\{name}(?![A-Za-z])", latex) for name in pictures)
        equations.append(SourceEquation(len(equations) + 1, line, latex, drawn))
    return equations


def _nth_line(raw: str, start: int, needle: str, nth: int) -> int:
    i = start
    for _ in range(nth + 1):
        i = raw.index(needle, i + 1)
    return raw.count("\n", 0, i) + 1


def printed_number(number: str) -> int | None:
    m = re.fullmatch(r"\(?\s*(\d+)\s*\)?", number.strip())
    return int(m.group(1)) if m else None


def measure(sources: list[SourceEquation], judgement: dict[str, Any], judge: int) -> list[Result]:
    by_number: dict[int, dict[str, Any]] = {}
    for eq in judgement["equations"]:
        n = printed_number(eq.get("number", ""))
        if n is not None:
            by_number.setdefault(n, eq)
    results: list[Result] = []
    for src in sources:
        eq = by_number.get(src.number)
        if eq is None:
            results.append(
                Result(src.number, src.line, src.latex, judge, False, "", None, "missing")
            )
            continue
        level: str = compare(src.latex, eq["latex"]).level
        if level != "same" and src.drawn:
            level = "drawn"
        results.append(
            Result(src.number, src.line, src.latex, judge, True, eq["latex"], eq["pdf_page"], level)
        )
    return results


def summary(results: list[Result]) -> dict[str, int]:
    counts = {"same": 0, "style": 0, "strict": 0, "missing": 0, "drawn": 0}
    for r in results:
        counts[r.level] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("key")
    args = parser.parse_args()
    list_path = ROOT / "testdata" / "papers.toml"
    paper = next(p for p in testdata.load(list_path) if p.key == args.key)
    if not paper.exact_source:
        sys.exit(f"{args.key} has no exact source")
    sources = source_equations(ROOT / paper.exact_source / "main.tex")
    report: dict[str, Any] = {"key": args.key, "source_equations": len(sources), "judges": {}}
    for path in sorted((OUT / args.key).glob("judge-[0-9].json")):
        judge = int(path.stem.split("-")[1])
        results = measure(sources, json.loads(path.read_text()), judge)
        report["judges"][judge] = {
            "summary": summary(results),
            "differences": [asdict(r) for r in results if r.level != "same"],
        }
        print(f"judge {judge}: {summary(results)} of {len(sources)} numbered equations")
        for r in results:
            if r.level != "same":
                print(f"  ({r.number}) {r.level}, source line {r.line}, PDF page {r.pdf_page}")
                print(f"    source: {r.source}")
                print(f"    judge:  {r.judged}")
    if not report["judges"]:
        sys.exit(f"no judgements in ground_truth/{args.key}/")
    out = OUT / args.key / "source-accuracy.json"
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
