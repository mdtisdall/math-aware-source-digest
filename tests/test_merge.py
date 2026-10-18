"""The gate 1 merge tool, without the API."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_DIR = Path(__file__).parent / "judging"
sys.path.insert(0, str(_DIR))
_SPEC = importlib.util.spec_from_file_location("gate1_merge", _DIR / "merge.py")
assert _SPEC is not None and _SPEC.loader is not None
merge = importlib.util.module_from_spec(_SPEC)
sys.modules["gate1_merge"] = merge
_SPEC.loader.exec_module(merge)


def eq(page: int, order: int, latex: str, number: str = "") -> dict[str, Any]:
    return {
        "pdf_page": page,
        "printed_page": str(400 + page),
        "order_on_page": order,
        "number": number,
        "latex": latex,
        "uncertain": "",
    }


def judgement(*eqs: dict[str, Any]) -> dict[str, Any]:
    return {"pages": [], "equations": list(eqs), "items": []}


def test_numbered_pair_by_number_even_if_order_differs() -> None:
    j1 = judgement(eq(1, 1, r"a=b", "(1)"), eq(1, 2, r"\gamma_k", "(2)"))
    j2 = judgement(eq(1, 1, r"y_k", "(2)"), eq(1, 2, r"a = b", "(1)"))
    entries = merge.merge(j1, j2)
    by_number = {e.number: e for e in entries}
    assert by_number["(1)"].status == "agreed" and by_number["(1)"].latex == "a=b"
    assert by_number["(2)"].status == "strict" and by_number["(2)"].latex == ""
    assert by_number["(2)"].readings == {"1": r"\gamma_k", "2": "y_k"}


def test_unnumbered_pair_in_order_and_omissions_are_kept() -> None:
    j1 = judgement(eq(2, 1, r"\mathbf{x}"), eq(2, 2, r"z"), eq(3, 1, r"q"))
    j2 = judgement(eq(2, 1, r"x"))
    entries = merge.merge(j1, j2)
    assert [e.status for e in entries] == ["style", "only-1", "only-1"]
    assert merge.summary(entries) == {"style": 1, "only-1": 2, "total": 3}


def test_formatting_differences_are_agreements() -> None:
    j1 = judgement(eq(1, 1, r"\exp\left(- \parallel y - Ax\|_2^2\right)", "(6)"))
    j2 = judgement(eq(1, 1, r"\exp(-\|y-Ax\|_2^2)", "(6)"))
    assert merge.merge(j1, j2)[0].status == "agreed"


def test_adjudication_request(tmp_path: Path) -> None:
    page = tmp_path / "page-3.png"
    page.write_bytes(b"\x89PNG fake")
    entry = merge.merge(judgement(eq(3, 2, r"\gamma", "(9)")), judgement(eq(3, 2, "y", "(9)")))[0]
    params = merge.adjudication_params(entry, page)
    content = params["messages"][0]["content"]
    assert [b["type"] for b in content] == ["image", "text"]
    assert "Reading A:\n\\gamma" in content[1]["text"] and "Reading B:\ny" in content[1]["text"]
    assert "equation (9)" in content[1]["text"]
    assert params["model"] == "claude-opus-5-5"
    assert params["output_config"]["format"]["schema"] is merge.ADJUDICATE_SCHEMA


def verdict_message(verdict: dict[str, Any], **changes: Any) -> dict[str, Any]:
    base = {
        "model": "claude-opus-5-5",
        "stop_reason": "end_turn",
        "content": [{"type": "text", "text": json.dumps(verdict)}],
        "usage": {},
    }
    base.update(changes)
    return base


def test_only_confident_verdicts_settle() -> None:
    entry = merge.merge(judgement(eq(1, 1, "a", "(1)")), judgement(eq(1, 1, "b", "(1)")))[0]
    merge.apply_resolution(
        entry, {"choice": "A", "latex": "a", "confidence": "high", "reason": "x"}
    )
    assert entry.latex == "a" and entry.resolution["settled_by"] == "opus"
    other = merge.merge(judgement(eq(1, 1, "a", "(1)")), judgement(eq(1, 1, "b", "(1)")))[0]
    merge.apply_resolution(
        other, {"choice": "B", "latex": "b", "confidence": "medium", "reason": "x"}
    )
    assert other.latex == "" and other.resolution["settled_by"] == "user (pending)"


@pytest.mark.parametrize(
    "changes, match",
    [
        ({"model": "claude-opus-4-8"}, "answered by"),
        ({"usage": {"iterations": [{"type": "fallback_message"}]}}, "fallback"),
        ({"stop_reason": "refusal"}, "stopped"),
        ({"content": [{"type": "text", "text": "A"}]}, "not JSON"),
    ],
)
def test_invalid_verdicts(changes: dict[str, Any], match: str) -> None:
    good = {"choice": "A", "latex": "a", "confidence": "high", "reason": "r"}
    assert merge.check_verdict(verdict_message(good)) == good
    with pytest.raises(ValueError, match=match):
        merge.check_verdict(verdict_message(good, **changes))


def item(kind: str, label: str, page: int) -> dict[str, Any]:
    return {"kind": kind, "label": label, "pdf_page": page, "printed_page": str(page)}


@pytest.mark.parametrize(
    "a, b",
    [
        (item("section", "Section 2.1", 2), item("section", "2.1 Bayesian Reconstruction", 2)),
        (item("section", "1. Introduction", 2), item("section", "Section 1", 2)),
        (item("section", "Section I-C-1", 3), item("section", "I-C-1 Training", 3)),
        (item("theorem", "Thm. 3", 8), item("theorem", "Theorem 3", 8)),
        (item("lemma", "2", 7), item("lemma", "Lemma 2", 7)),
    ],
)
def test_item_labels_written_differently_pair(a: dict[str, Any], b: dict[str, Any]) -> None:
    assert merge.item_key(a) == merge.item_key(b)


@pytest.mark.parametrize(
    "a, b",
    [
        (item("section", "3. A method", 6), item("section", "Section 3.1", 6)),
        (item("theorem", "Theorem 3", 8), item("lemma", "Lemma 3", 8)),
        (item("section", "Section I-A", 2), item("section", "Section I-B", 2)),
    ],
)
def test_different_items_do_not_pair(a: dict[str, Any], b: dict[str, Any]) -> None:
    assert merge.item_key(a) != merge.item_key(b)


def test_merge_items() -> None:
    j1 = {"items": [item("theorem", "Theorem 1", 3), item("lemma", "Lemma 2", 4)]}
    j2 = {
        "items": [
            item("theorem", "Theorem 1", 3),
            item("lemma", "Lemma 2", 5),
            item("section", "Appendix", 9),
        ]
    }
    status = {i.label: i.status for i in merge.merge_items(j1, j2)}
    assert status == {"Theorem 1": "agreed", "Lemma 2": "page", "Appendix": "only-2"}
