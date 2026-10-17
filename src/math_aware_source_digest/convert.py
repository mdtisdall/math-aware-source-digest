"""Stage 3 (exact route): convert author LaTeX or JATS XML with pandoc.

Pandoc always runs with ``--sandbox`` (no reading or writing of files other
than its input and output, no network), with a timeout, on a copy of the
input in its own directory. Its warnings are kept with the result.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PANDOC_TIMEOUT_S = 120
FORMATS = {"latex": "latex+latex_macros", "jats": "jats"}


class ConvertError(Exception):
    pass


@dataclass
class Converted:
    markdown: str
    warnings: list[str] = field(default_factory=list)
    display_math: int = 0
    inline_math: int = 0

    @property
    def has_math(self) -> bool:
        return self.display_math + self.inline_math > 0


_INPUT = re.compile(r"\\(input|include|subfile)\s*\{([^}]+)\}")
MAX_INPUT_DEPTH = 10


def flatten_latex(main: Path, root: Path, warnings: list[str], depth: int = 0) -> str:
    """Inline ``\\input``, ``\\include`` and ``\\subfile`` of files inside ``root``.

    Pandoc in sandbox mode reads only the file it is given, so a multi-file
    source is joined first. A path that leaves ``root``, or a missing file,
    is left out with a warning.
    """
    text = main.read_text(errors="replace")
    root = root.resolve()

    def replace(match: re.Match[str]) -> str:
        name = match.group(2).strip()
        if depth >= MAX_INPUT_DEPTH:
            warnings.append(f"\\{match.group(1)}{{{name}}}: nesting deeper than {MAX_INPUT_DEPTH}")
            return ""
        for candidate in (root / name, root / f"{name}.tex"):
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root):
                warnings.append(f"\\{match.group(1)}{{{name}}}: outside the source; left out")
                return ""
            if resolved.is_file():
                return flatten_latex(resolved, root, warnings, depth + 1)
        warnings.append(f"\\{match.group(1)}{{{name}}}: file not found; left out")
        return ""

    # Not inside comments: on each line, only the part before an unescaped %.
    out = []
    for line in text.splitlines(keepends=True):
        comment = re.search(r"(?<!\\)%", line)
        cut = comment.start() if comment else len(line)
        out.append(_INPUT.sub(replace, line[:cut]) + line[cut:])
    return "".join(out)


def pandoc_version() -> str:
    if shutil.which("pandoc") is None:
        raise ConvertError("pandoc is not on PATH: run inside `nix develop`")
    out = subprocess.run(["pandoc", "--version"], capture_output=True, text=True, check=True)
    return out.stdout.splitlines()[0]


def count_math(markdown: str) -> tuple[int, int]:
    """(display, inline) TeX math spans in pandoc Markdown."""
    display = len(re.findall(r"(?<!\\)\$\$.+?(?<!\\)\$\$", markdown, re.S))
    without_display = re.sub(r"(?<!\\)\$\$.+?(?<!\\)\$\$", "", markdown, flags=re.S)
    inline = len(re.findall(r"(?<![\\$])\$(?!\s)[^$\n]+?(?<![\\\s])\$(?!\d)", without_display))
    return display, inline


def run_pandoc(
    source: Path, kind: str, workdir: Path, timeout_s: float = PANDOC_TIMEOUT_S
) -> Converted:
    """Convert ``source`` (``kind`` is "latex" or "jats") to Markdown with TeX math."""
    if kind not in FORMATS:
        raise ConvertError(f"unknown input kind {kind!r}")
    pandoc_version()
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = [
        "pandoc",
        "--sandbox",
        "--from",
        FORMATS[kind],
        "--to",
        "markdown",
        "--wrap=none",
        "--verbose",
        str(source),
    ]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout_s, cwd=workdir, check=False
        )
    except subprocess.TimeoutExpired as ex:
        raise ConvertError(f"pandoc did not finish in {timeout_s:.0f} s") from ex
    if proc.returncode != 0:
        raise ConvertError(f"pandoc failed ({proc.returncode}): {proc.stderr.strip()[:500]}")
    warnings = [line for line in proc.stderr.splitlines() if line.startswith("[WARNING]")]
    display, inline = count_math(proc.stdout)
    return Converted(proc.stdout, warnings, display, inline)
