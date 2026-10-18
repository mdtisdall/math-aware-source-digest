"""The gate 1 judge tool, without the API (no network, no key)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).parent / "judging" / "judge.py"
_SPEC = importlib.util.spec_from_file_location("gate1_judge", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
judge = importlib.util.module_from_spec(_SPEC)
sys.modules["gate1_judge"] = judge
_SPEC.loader.exec_module(judge)


def pages(tmp_path: Path, n: int = 3) -> list[object]:
    out = []
    for i in range(1, n + 1):
        path = tmp_path / f"page-{i}.png"
        path.write_bytes(b"\x89PNG fake " + bytes([i]))
        out.append(judge.Page(i, path, f"{i:064x}"))
    return out


def test_request_puts_pages_first_then_the_task(tmp_path: Path) -> None:
    params = judge.build_params(pages(tmp_path))
    content = params["messages"][0]["content"]
    assert [b["type"] for b in content] == ["text", "image"] * 3 + ["text"]
    assert content[0]["text"] == "PDF page 1"
    assert content[-2]["cache_control"] == {"type": "ephemeral"}  # the shared image prefix
    assert content[-1]["text"] == judge.TASK
    assert params["model"] == "claude-opus-5-5"
    assert params["output_config"]["effort"] == "high"
    assert params["output_config"]["format"]["schema"] is judge.SCHEMA
    assert "temperature" not in params and "tools" not in params


def test_two_judges_of_a_paper_send_the_same_request(tmp_path: Path) -> None:
    p = pages(tmp_path)
    assert judge.build_params(p) == judge.build_params(p)


def test_the_record_holds_hashes_not_images(tmp_path: Path) -> None:
    record = judge.request_record("student-1908", 2, pages(tmp_path), "batch")
    text = json.dumps(record)
    assert "base64" not in text and "PNG" not in text
    assert record["pages"][0] == {"pdf_page": 1, "sha256": "0" * 63 + "1"}
    assert record["judge"] == 2 and record["model"] == judge.MODEL


def test_schema_is_closed() -> None:
    def walk(node: object) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(judge.SCHEMA)


GOOD = {
    "pages": [{"pdf_page": 1, "printed_page": "409", "kind": "article"}],
    "equations": [
        {
            "pdf_page": 1,
            "printed_page": "409",
            "order_on_page": 1,
            "number": "(1)",
            "latex": "Ax = k",
            "uncertain": "",
        }
    ],
    "items": [],
}


def message(**changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "model": "claude-opus-5-5",
        "stop_reason": "end_turn",
        "content": [
            {"type": "thinking", "thinking": ""},
            {"type": "text", "text": json.dumps(GOOD)},
        ],
        "usage": {"input_tokens": 1000, "output_tokens": 500},
    }
    base.update(changes)
    return base


def test_a_good_answer_parses() -> None:
    assert judge.check_answer(message()) == GOOD


@pytest.mark.parametrize(
    "changes, reason",
    [
        ({"model": "claude-opus-4-8"}, "not claude-opus-5-5"),
        (
            {"usage": {"iterations": [{"type": "message"}, {"type": "fallback_message"}]}},
            "fallback",
        ),
        ({"stop_reason": "refusal", "stop_details": {"category": "cyber"}}, "refused"),
        ({"stop_reason": "max_tokens"}, "max_tokens"),
        ({"content": [{"type": "text", "text": "Here is the list: ..."}]}, "not JSON"),
        ({"content": [{"type": "text", "text": '{"pages": []}'}]}, "no list"),
    ],
)
def test_invalid_judges(changes: dict[str, object], reason: str) -> None:
    with pytest.raises(judge.JudgeError, match=reason):
        judge.check_answer(message(**changes))


def test_cost() -> None:
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 100_000,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 1_000_000,
    }
    assert judge.cost_usd(usage, batch=False) == 4.0 + 2.0 + 0.2
    assert judge.cost_usd(usage, batch=True) == 3.1


def test_save_writes_request_response_and_judgement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(judge, "OUT", tmp_path / "gt")
    record = judge.request_record("x", 1, pages(tmp_path), "single")
    summary = judge.save("x", 1, record, message(), batch=False)
    assert summary["equations"] == 1 and "invalid" not in summary
    assert sorted(p.name for p in (tmp_path / "gt" / "x").iterdir()) == [
        "judge-1.json",
        "judge-1.request.json",
        "judge-1.response.json",
    ]
    bad = judge.save("x", 2, record, message(stop_reason="max_tokens"), batch=False)
    assert "max_tokens" in bad["invalid"]
    assert not (tmp_path / "gt" / "x" / "judge-2.json").exists()


def test_only_test_papers_may_be_judged() -> None:
    with pytest.raises(judge.JudgeError, match="not a pinned test paper"):
        judge.paper_pdf("seeger-2010")


def test_no_key_no_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(judge.JudgeError, match="ANTHROPIC_API_KEY"):
        judge._client()
