from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from pdfs import make_pdf

from math_aware_source_digest import flag
from math_aware_source_digest.crop import Box
from math_aware_source_digest.local.ollama import Answer, BadAnswer

pytestmark = pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="needs pdftoppm")


def test_flags(tmp_path: Path) -> None:
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(make_pdf([["eq one", "eq two", "eq three", "eq four"]]))
    spans = [
        flag.Span("eq1", 0, Box(72, 60, 300, 80), r"\gamma_k = 1"),
        flag.Span("eq2", 0, Box(72, 80, 300, 100), r"\tilde\phi"),
        flag.Span("eq3", 0, Box(72, 100, 300, 120), r"\mathbf{x}"),
        flag.Span("eq4", 0, Box(72, 120, 300, 140), r"a + b"),
    ]
    answers = {"eq1": r"y_k = 1", "eq2": r"\tilde{\phi}", "eq3": r"x"}

    def fake(image: Path) -> Answer:
        assert image.exists()
        if image.stem == "eq4":
            raise BadAnswer("cut off", "length", '{"latex": "a +')
        return Answer({"latex": answers[image.stem]}, 0.1, 10, 5, "fake")

    results = flag.flag_spans(pdf, spans, fake, tmp_path / "crops")
    assert [r.flags for r in results] == [
        ["disagree:strict"],
        [],
        ["disagree:style"],
        ["second:length"],
    ]
    flag.write_flags(results, tmp_path / "flags.json", {"model": "fake"})
    data = json.loads((tmp_path / "flags.json").read_text())
    assert (data["flagged"], data["total"]) == (3, 4)


def test_transcriber_uses_the_short_latex_only_request() -> None:
    calls = []

    class Client:
        def chat_json(
            self,
            model: str,
            prompt: str,
            schema: dict[str, object],
            images: list[Path],
            num_predict: int,
        ) -> Answer:
            calls.append((model, schema, num_predict))
            return Answer({"latex": "x"}, 0, 0, 0, model)

    flag.transcriber(Client(), "qwen3-vl:32b-instruct")(Path("c.png"))
    assert calls == [("qwen3-vl:32b-instruct", flag.TRANSCRIBE_SCHEMA, flag.NUM_PREDICT)]
