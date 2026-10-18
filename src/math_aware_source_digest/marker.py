"""Read Marker's JSON output: blocks with their page, box and content."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from .crop import Box

_PAGE_ID = re.compile(r"^/page/(\d+)/")
_MATH = re.compile(r"<math[^>]*>(.*?)</math>", re.S)


@dataclass(frozen=True)
class Block:
    page_index: int  # from 0
    block_type: str
    box: Box  # PDF points, relative to the page's top left
    html: str
    block_id: str


def walk(
    block: dict[str, Any], page: int | None = None
) -> Iterator[tuple[int | None, dict[str, Any]]]:
    match = _PAGE_ID.match(block.get("id") or "")
    if match:
        page = int(match.group(1))
    yield page, block
    for child in block.get("children") or []:
        yield from walk(child, page)


def latex_of(html: str) -> str:
    """The LaTeX inside Marker's ``<math>`` element (or the text, if none)."""
    match = _MATH.search(html or "")
    return (match.group(1) if match else re.sub(r"<[^>]+>", "", html or "")).strip()


def blocks(doc: dict[str, Any], block_type: str | None = None) -> list[Block]:
    """All blocks (or those of one type), with boxes made relative to their page."""
    origins: dict[int, tuple[float, float]] = {}
    found = []
    for page, block in walk(doc):
        if page is None or not block.get("bbox"):
            continue
        if block.get("block_type") == "Page":
            origins[page] = (float(block["bbox"][0]), float(block["bbox"][1]))
            continue
        if block_type and block.get("block_type") != block_type:
            continue
        found.append((page, block))
    out = []
    for page, block in found:
        ox, oy = origins.get(page, (0.0, 0.0))
        x0, y0, x1, y1 = (float(v) for v in block["bbox"])
        out.append(
            Block(
                page,
                block["block_type"],
                Box(x0 - ox, y0 - oy, x1 - ox, y1 - oy),
                block.get("html") or "",
                block.get("id") or "",
            )
        )
    return out


def equations(doc: dict[str, Any]) -> list[Block]:
    return blocks(doc, "Equation")
