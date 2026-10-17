from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from math_aware_source_digest import convert

needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not on PATH")


def test_flatten_inlines_inputs_inside_the_source(tmp_path: Path) -> None:
    (tmp_path / "sec").mkdir()
    (tmp_path / "sec" / "intro.tex").write_text("Intro $a$.\n\\input{sec/deeper}\n")
    (tmp_path / "sec" / "deeper.tex").write_text("Deeper $b$.\n")
    main = tmp_path / "main.tex"
    main.write_text(
        "\\begin{document}\n\\input{sec/intro}\n% \\input{commented}\n"
        "\\include{missing}\n\\input{../../etc/passwd}\n\\end{document}\n"
    )
    warnings: list[str] = []
    text = convert.flatten_latex(main, tmp_path, warnings)
    assert "Intro $a$." in text and "Deeper $b$." in text
    assert "% \\input{commented}" in text
    assert any("missing" in w and "not found" in w for w in warnings)
    assert any("passwd" in w and "outside" in w for w in warnings)


def test_flatten_stops_at_depth(tmp_path: Path) -> None:
    (tmp_path / "loop.tex").write_text("\\input{loop}\n")
    warnings: list[str] = []
    convert.flatten_latex(tmp_path / "loop.tex", tmp_path, warnings)
    assert any("nesting" in w for w in warnings)


def test_count_math() -> None:
    md = "Let $x$ be and $y_1$ cost \\$5.\n\n$$a = b$$\n\nAlso $$c$$ and 3$ or $ 4$."
    assert convert.count_math(md) == (2, 2)


@needs_pandoc
def test_pandoc_converts_latex_with_macros(tmp_path: Path) -> None:
    src = tmp_path / "in.tex"
    src.write_text(
        "\\newcommand{\\R}{\\mathbb{R}}\n\\begin{document}\n"
        "Let $x \\in \\R$.\n\\begin{equation}\\hat\\phi = \\tilde{\\gamma}\\end{equation}"
        "\n\\end{document}\n"
    )
    out = convert.run_pandoc(src, "latex", tmp_path / "work")
    assert "\\mathbb{R}" in out.markdown
    assert out.has_math and out.display_math == 1


@needs_pandoc
def test_pandoc_sandbox_refuses_other_files(tmp_path: Path) -> None:
    secret = tmp_path / "secret.tex"
    secret.write_text("TOPSECRETVALUE\n")
    src = tmp_path / "in.tex"
    src.write_text(f"\\begin{{document}}\n\\input{{{secret}}}\n\\end{{document}}\n")
    try:
        out = convert.run_pandoc(src, "latex", tmp_path / "work")
    except convert.ConvertError:
        return  # refusing outright is also acceptable
    assert "TOPSECRETVALUE" not in out.markdown


@needs_pandoc
def test_pandoc_jats(tmp_path: Path) -> None:
    src = tmp_path / "a.xml"
    src.write_text(
        '<?xml version="1.0"?><article xmlns:mml="http://www.w3.org/1998/Math/MathML">'
        "<body><sec><title>S</title><p>Let <inline-formula><mml:math><mml:msub><mml:mi>x</mml:mi>"
        "<mml:mn>1</mml:mn></mml:msub></mml:math></inline-formula> be.</p></sec></body></article>"
    )
    out = convert.run_pandoc(src, "jats", tmp_path / "work")
    assert "x_{1}" in out.markdown.replace(" ", "") or "x_1" in out.markdown


def test_unknown_kind(tmp_path: Path) -> None:
    with pytest.raises(convert.ConvertError):
        convert.run_pandoc(tmp_path / "x", "docx", tmp_path)
