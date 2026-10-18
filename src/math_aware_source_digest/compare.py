"""Compare two LaTeX transcriptions of one span (stage 5, step 3).

Two levels, as the plan defines them:

- **strict:** the rendered symbols differ (γ against y, a tilde against a
  hat, 𝒲 against 𝒱, a dropped term, a changed relation);
- **style:** only the style differs (bold, calligraphic, blackboard,
  upright against italic).

This is the first of the two stages of plan section 5, step 3. It converts
both readings into a narrow LaTeX, in which notation that means the same is
written one way (spacing, sizing, display environments, delimiters of
matrices, primes, ``:=``, the order of a subscript and a superscript), and
compares the tokens. Equal tokens are equivalent; the pairs it does not settle
go to the second stage, a local model that judges meaning in context. Each
rule of the narrow LaTeX must never merge two readings that a mathematical
reader would tell apart, and has a test.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Literal

Level = Literal["same", "style", "strict"]

STYLE_COMMANDS = {
    "mathbf",
    "boldsymbol",
    "bm",
    "mathbfit",
    "pmb",
    "mathcal",
    "mathscr",
    "mathfrak",
    "mathbb",
    "mathrm",
    "mathit",
    "mathsf",
    "mathtt",
    "textbf",
    "textit",
    "textrm",
    "text",
    "operatorname",
    "mathnormal",
}
SPACING = {
    ",",
    ";",
    ":",
    "!",
    " ",
    "quad",
    "qquad",
    "enspace",
    "thinspace",
    "medspace",
    "thickspace",
    "negthinspace",
    "hspace",
    "vspace",
    "displaystyle",
    "textstyle",
    "scriptstyle",
    "limits",
    "nolimits",
}
SIZING = {
    "left",
    "right",
    "big",
    "Big",
    "bigg",
    "Bigg",
    "bigl",
    "bigr",
    "Bigl",
    "Bigr",
    "biggl",
    "biggr",
    "Biggl",
    "Biggr",
    "middle",
}
ALIASES = {
    "le": "leq",
    "ge": "geq",
    "ne": "neq",
    "to": "rightarrow",
    "gets": "leftarrow",
    "lbrace": "\\{",
    "rbrace": "\\}",
    "vert": "|",
    "Vert": "\\|",
    "parallel": "\\|",
    "|": "\\|",
    "dfrac": "frac",
    "tfrac": "frac",
    "lvert": "|",
    "rvert": "|",
    "lVert": "\\|",
    "rVert": "\\|",
    "colon": ":",
    "dots": "ldots",
    "cdotp": "cdot",
}

_TOKEN = re.compile(r"\\[A-Za-z]+|\\.|[A-Za-z0-9]|[^\sA-Za-z0-9]")


def tokens(latex: str) -> list[str]:
    return _TOKEN.findall(latex)


@dataclass(frozen=True)
class Comparison:
    level: Level
    a: tuple[str, ...]  # the normalized tokens compared at the strict level
    b: tuple[str, ...]

    @property
    def differs(self) -> bool:
        return self.level != "same"


_ENVIRONMENT = re.compile(
    r"\\(?:begin|end)\{(?:equation|align|aligned|alignat|alignedat|split|gather|gathered|"
    r"multline|eqnarray|displaymath|math)\*?\}(?:\{\d+\})?"
)
_EQUATION_NUMBER = re.compile(
    r"(?:\\tag\*?\{[^}]*\}|\\qquad\s*\(\s*\d+[a-z]?\s*\)|[\[(]\s*(?:\\(?:text|mathrm)\{\s*)?[A-Z]?\.?\d+[a-z]?\s*\}?\s*[\])])\s*[.,]?\s*$"
)


# A matrix environment prints its delimiters; write them as \left...\right does.
_MATRIX_DELIMITERS = {
    "pmatrix": ("(", ")"),
    "bmatrix": ("[", "]"),
    "Bmatrix": ("\\{", "\\}"),
    "vmatrix": ("|", "|"),
    "Vmatrix": ("\\|", "\\|"),
    "cases": ("\\{", ""),
    "matrix": ("", ""),
    "smallmatrix": ("", ""),
    "array": ("", ""),
}
_MATRIX = re.compile(r"\\(begin|end)\{(" + "|".join(_MATRIX_DELIMITERS) + r")\*?\}")
_ARRAY_COLUMNS = re.compile(r"\\begin\{array\}\{[^}]*\}")


def _matrix_delimiters(m: re.Match[str]) -> str:
    left, right = _MATRIX_DELIMITERS[m.group(2)]
    return f" {left} " if m.group(1) == "begin" else f" {right} "


def clean(latex: str) -> str:
    """Remove what does not change the mathematics: HTML entities (Marker writes
    ``&gt;``), display environments, alignment marks, line breaks and a trailing
    equation number such as ``[3]``, ``(3)`` or ``\\tag{3}``."""
    text = html.unescape(latex)
    text = _ENVIRONMENT.sub(" ", text)
    text = _ARRAY_COLUMNS.sub(r"\\begin{array}", text)
    text = _MATRIX.sub(_matrix_delimiters, text)
    text = re.sub(r"\\\\(?:\[[^\]]*\])?", " ", text)  # \\ line breaks
    text = re.sub(r"(?<!\\)&", " ", text)  # alignment marks
    previous = None
    while previous != text:  # a number may follow final punctuation
        previous = text
        text = _EQUATION_NUMBER.sub("", text.rstrip())
    return text


# Commands that print the same symbols as a sequence of other tokens.
EXPANSIONS = {
    "coloneqq": (":", "="),
    "coloneq": (":", "="),
    "eqqcolon": ("=", ":"),
    "eqcolon": ("=", ":"),
    "llbracket": ("[", "["),
    "rrbracket": ("]", "]"),
}


def _group_end(toks: list[str], i: int) -> int:
    """The index after the script argument that starts at toks[i]: a brace
    group, a command with its brace group (``\\mathrm{T}``), or one token."""
    if i >= len(toks):
        return i
    if toks[i] == "{":
        depth = 0
        for j in range(i, len(toks)):
            depth += {"{": 1, "}": -1}.get(toks[j], 0)
            if depth == 0:
                return j + 1
        return len(toks)
    if toks[i].startswith("\\") and i + 1 < len(toks) and toks[i + 1] == "{":
        return _group_end(toks, i + 1)
    return i + 1


def _canonical(toks: list[str]) -> list[str]:
    """Write the same notation one way: ``x'`` as ``x^{\\prime}``, the commands
    of EXPANSIONS as their tokens, and a subscript before a superscript
    (``x^2_i`` as ``x_i^2``)."""
    out: list[str] = []
    i = 0
    while i < len(toks):
        tok = toks[i]
        if tok == "'":
            primes = 0
            while i < len(toks) and toks[i] == "'":
                primes += 1
                i += 1
            out += ["^", "{", *["\\prime"] * primes, "}"]
            continue
        if tok.startswith("\\") and tok[1:] in EXPANSIONS:
            out += EXPANSIONS[tok[1:]]
        else:
            out.append(tok)
        i += 1
    i = 0
    while i < len(out):
        if out[i] == "^":
            sup_end = _group_end(out, i + 1)
            if sup_end < len(out) and out[sup_end] == "_":
                sub_end = _group_end(out, sup_end + 1)
                out[i:sub_end] = out[sup_end:sub_end] + out[i:sup_end]
        i += 1
    return out


def _normalize(latex: str, keep_style: bool) -> tuple[str, ...]:
    out: list[str] = []
    toks = _canonical(tokens(clean(latex)))
    i = 0
    while i < len(toks):
        tok = toks[i]
        name = tok[1:] if tok.startswith("\\") else None
        if name in SPACING:
            if name in ("hspace", "vspace") and i + 1 < len(toks) and toks[i + 1] == "{":
                depth, i = 0, i + 1
                while i < len(toks):
                    depth += {"{": 1, "}": -1}.get(toks[i], 0)
                    if depth == 0:
                        break
                    i += 1
            i += 1
            continue
        if name in SIZING:
            # \left. and \right. print no delimiter.
            i += 2 if name in ("left", "right") and toks[i + 1 : i + 2] == ["."] else 1
            continue
        if name in STYLE_COMMANDS:
            if keep_style:
                out.append(
                    "\\"
                    + (
                        "mathbf"
                        if name in ("boldsymbol", "bm", "pmb", "textbf")
                        else "mathrm"
                        if name in ("text", "textrm", "operatorname")
                        else name
                    )
                )
            i += 1
            continue
        if name is not None:
            alias = ALIASES.get(name)
            if alias is None:
                tok = "\\" + name
            elif alias.startswith("\\") or alias in ("|", ":"):
                tok = alias
            else:
                tok = "\\" + alias
        if tok in ("{", "}"):
            if keep_style:
                out.append(tok)
            i += 1
            continue
        out.append(tok)
        i += 1
    return tuple(out)


def _strip_final_punctuation(toks: tuple[str, ...]) -> tuple[str, ...]:
    end = len(toks)
    while end and toks[end - 1] in (".", ","):
        end -= 1
    return toks[:end]


def compare(a: str, b: str) -> Comparison:
    strict_a = _strip_final_punctuation(_normalize(a, keep_style=False))
    strict_b = _strip_final_punctuation(_normalize(b, keep_style=False))
    if strict_a != strict_b:
        return Comparison("strict", strict_a, strict_b)
    if _style_signature(a) != _style_signature(b):
        return Comparison("style", strict_a, strict_b)
    return Comparison("same", strict_a, strict_b)


def _style_signature(latex: str) -> tuple[tuple[str, str], ...]:
    """Each styled base symbol with its style: (style, symbol)."""
    toks = _normalize(latex, keep_style=True)
    styled: list[tuple[str, str]] = []
    for i, tok in enumerate(toks):
        if tok.startswith("\\") and tok[1:] in STYLE_COMMANDS:
            j = i + 1
            if j < len(toks) and toks[j] == "{":
                depth, k = 0, j
                while k < len(toks):
                    depth += {"{": 1, "}": -1}.get(toks[k], 0)
                    if depth == 0:
                        break
                    if toks[k] not in ("{", "}"):
                        styled.append((tok, toks[k]))
                    k += 1
            elif j < len(toks):
                styled.append((tok, toks[j]))
    return tuple(sorted(styled))
