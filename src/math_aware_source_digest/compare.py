"""Compare two LaTeX transcriptions of one span (stage 5, step 3).

Two levels, as the plan defines them:

- **strict:** the rendered symbols differ (γ against y, a tilde against a
  hat, 𝒲 against 𝒱, a dropped term, a changed relation);
- **style:** only the style differs (bold, calligraphic, blackboard,
  upright against italic).

This module compares normalized token sequences. It is a fast first check;
CDM (which renders both and matches characters) is the reference and needs
TeX Live and ImageMagick, which are not in the default devShell:
:func:`cdm_available` reports whether it can run.
"""

from __future__ import annotations

import html
import re
import shutil
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


def clean(latex: str) -> str:
    """Remove what does not change the mathematics: HTML entities (Marker writes
    ``&gt;``), display environments, alignment marks, line breaks and a trailing
    equation number such as ``[3]``, ``(3)`` or ``\\tag{3}``."""
    text = html.unescape(latex)
    text = _ENVIRONMENT.sub(" ", text)
    text = re.sub(r"\\\\(?:\[[^\]]*\])?", " ", text)  # \\ line breaks
    text = re.sub(r"(?<!\\)&", " ", text)  # alignment marks
    previous = None
    while previous != text:  # a number may follow final punctuation
        previous = text
        text = _EQUATION_NUMBER.sub("", text.rstrip())
    return text


def _normalize(latex: str, keep_style: bool) -> tuple[str, ...]:
    out: list[str] = []
    toks = tokens(clean(latex))
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
            i += 1
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


def cdm_available() -> tuple[bool, str]:
    """Whether CDM can run here (it needs pdflatex and ImageMagick)."""
    missing = [tool for tool in ("pdflatex", "magick") if shutil.which(tool) is None]
    if missing:
        return False, (
            f"CDM needs {', '.join(missing)}: run it in its own nix shell "
            "(TeX Live and ImageMagick are not in the default devShell)"
        )
    return True, ""
