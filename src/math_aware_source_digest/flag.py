"""Stage 5, steps 1-3 on the PDF route: crop, transcribe again, compare, flag.

A port of the design's prototype (``eqloop.py``), slimmed as the plan says:
no notation pass, no per-symbol report, LaTeX-only answers with a short
output cap. Each span's first transcription (from the converter) is compared
with a second one by a local vision model. A span is flagged when the two
differ (strict or style), or when the second answer is cut off, empty or
unparsable. Adjudication (step 4) is a later stage.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .compare import compare
from .crop import Box, crop
from .local.ollama import Answer, BadAnswer

TRANSCRIBE_SCHEMA = {
    "type": "object",
    "properties": {"latex": {"type": "string"}},
    "required": ["latex"],
    "additionalProperties": False,
}
TRANSCRIBE_PROMPT = (
    "The image shows one display equation from a scientific paper. Transcribe it exactly into "
    "LaTeX. Take care with symbols that look alike: Greek and Latin letters (gamma and y, nu "
    "and v), hats, tildes and bars, stars and primes, subscripts and superscripts, bold, "
    "calligraphic and blackboard letters. Do not add or remove terms. Do not include the "
    'equation number. Return JSON: {"latex": "..."}'
)
NUM_PREDICT = 400


@dataclass(frozen=True)
class Span:
    span_id: str
    page_index: int
    box: Box
    first: str  # the converter's transcription


@dataclass
class Flagged:
    span_id: str
    page: int  # from 1
    first: str
    second: str
    flags: list[str] = field(default_factory=list)
    seconds: float = 0.0


Transcriber = Callable[[Path], Answer]


def transcriber(client: Any, model: str, num_predict: int = NUM_PREDICT) -> Transcriber:
    def run(image: Path) -> Answer:
        result: Answer = client.chat_json(
            model, TRANSCRIBE_PROMPT, TRANSCRIBE_SCHEMA, images=[image], num_predict=num_predict
        )
        return result

    return run


def flag_spans(
    pdf: Path, spans: Iterable[Span], transcribe: Transcriber, crop_dir: Path, dpi: int = 300
) -> list[Flagged]:
    results = []
    for span in spans:
        image = crop(pdf, span.page_index, span.box, crop_dir / f"{span.span_id}.png", dpi)
        started = time.monotonic()
        item = Flagged(span.span_id, span.page_index + 1, span.first, "")
        try:
            answer = transcribe(image)
        except BadAnswer as ex:
            item.flags.append(f"second:{ex.kind}")
            item.second = ex.raw
        else:
            item.second = str(answer.data["latex"])
            level = compare(span.first, item.second).level
            if level != "same":
                item.flags.append(f"disagree:{level}")
        item.seconds = round(time.monotonic() - started, 2)
        results.append(item)
    return results


def write_flags(results: list[Flagged], path: Path, meta: dict[str, Any]) -> None:
    data = {
        "meta": meta,
        "flagged": sum(1 for r in results if r.flags),
        "total": len(results),
        "results": [asdict(r) for r in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))
