"""The gate 1 source-accuracy tool, on Zach et al. (2023), whose arXiv LaTeX
is committed under testdata/sources (CC BY 4.0)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_DIR = Path(__file__).parent / "judging"
_SPEC = importlib.util.spec_from_file_location("gate1_source_accuracy", _DIR / "source_accuracy.py")
assert _SPEC is not None and _SPEC.loader is not None
acc = importlib.util.module_from_spec(_SPEC)
sys.modules["gate1_source_accuracy"] = acc
_SPEC.loader.exec_module(acc)

ZACH = Path(__file__).parents[1] / "testdata/sources/zach-knoll-pock-2023/arxiv-2210.13834/main.tex"


@pytest.fixture(scope="module")
def zach() -> list[object]:
    equations: list[object] = acc.source_equations(ZACH)
    return equations


def test_zach_has_18_numbered_equations(zach: list[object]) -> None:
    assert [e.number for e in zach] == list(range(1, 19))  # type: ignore[attr-defined]


def test_macros_expand(zach: list[object]) -> None:
    latex = {e.number: e.latex for e in zach}  # type: ignore[attr-defined]
    assert r"\left\lVert x - x^\prime\right\rVert" in latex[3]  # \norm, with a space kept
    assert r"\operatorname*{arg\,min}" in latex[10]  # \DeclareMathOperator*
    assert r"A\colon \mathbb{R}^n\to \mathbb{C}^m" in latex[8]  # \Function and \R
    assert r"\vdots" in latex[8] and "vdotswithin" not in latex[8]
    assert r"\text{TV}" in latex[18]  # \gls inside the \replaced text that is shown
    assert "label" not in "".join(latex.values())


def test_a_drawn_symbol_is_marked(zach: list[object]) -> None:
    assert [e.number for e in zach if e.drawn] == [16]  # type: ignore[attr-defined]


def test_measure_matches_by_number(zach: list[object]) -> None:
    judgement = {
        "equations": [
            {"number": "(1)", "latex": r"\min_{x} E(x, z) := D(x, z) + R(x)", "pdf_page": 2},
            {"number": "(2)", "latex": r"\max_x \int p(y' \mid z)", "pdf_page": 2},
            {"number": "(16)", "latex": r"R_\theta = \square", "pdf_page": 6},
        ]
    }
    levels = {r.number: r.level for r in acc.measure(zach, judgement, 1)}
    assert levels[1] == "same"
    assert levels[2] == "strict"
    assert levels[16] == "drawn"
    assert levels[3] == "missing"


@pytest.mark.parametrize(
    "text, expected",
    [
        (r"a \added{b} c", "a b c"),
        (r"a \replaced{new}{old} c", "a new c"),
        (r"a \deleted{gone} c", "a c"),
        (r"x \label{eq:x}", "x"),
    ],
)
def test_changes_package_final_form(text: str, expected: str) -> None:
    assert acc.expand(text, {}, {}) == expected
