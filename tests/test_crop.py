from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pdfs import make_pdf

from math_aware_source_digest import crop, marker

needs_poppler = pytest.mark.skipif(shutil.which("pdftoppm") is None, reason="needs pdftoppm")


def test_pixel_window_scales_and_pads() -> None:
    win = crop.pixel_window(crop.Box(72, 144, 144, 216), 612, 792, dpi=300, pad_pt=6)
    assert (win.x, win.y) == (275, 575)  # (72 - 6) * 300/72, (144 - 6) * 300/72
    assert (win.width, win.height) == (350, 350)


def test_pixel_window_clamps_to_the_page() -> None:
    win = crop.pixel_window(crop.Box(1, 1, 611, 791), 612, 792, dpi=72, pad_pt=6)
    assert (win.x, win.y, win.width, win.height) == (0, 0, 612, 792)


def test_box_outside_the_page() -> None:
    with pytest.raises(crop.CropError, match="outside"):
        crop.pixel_window(crop.Box(700, 10, 800, 20), 612, 792, pad_pt=0)


def test_empty_box() -> None:
    with pytest.raises(crop.CropError, match="empty"):
        crop.Box(10, 10, 10, 20)


@needs_poppler
def test_crop_renders_the_window(tmp_path: Path) -> None:
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(make_pdf([["first page"], ["second page", "E = mc^2"]]))
    out = crop.crop(pdf, 1, crop.Box(72, 60, 300, 100), tmp_path / "c" / "eq.png", dpi=300)
    win = crop.pixel_window(crop.Box(72, 60, 300, 100), 612, 792)
    assert crop.png_size(out) == (win.width, win.height)


@needs_poppler
def test_page_out_of_range(tmp_path: Path) -> None:
    pdf = tmp_path / "p.pdf"
    pdf.write_bytes(make_pdf([["only page"]]))
    with pytest.raises(crop.CropError, match="page 3"):
        crop.crop(pdf, 2, crop.Box(0, 0, 10, 10), tmp_path / "x.png")


def test_marker_blocks_relative_to_page() -> None:
    doc = {
        "block_type": "Document",
        "children": [
            {
                "id": "/page/0/Page/1",
                "block_type": "Page",
                "bbox": [0, 0, 594, 792],
                "children": [
                    {
                        "id": "/page/0/Equation/3",
                        "block_type": "Equation",
                        "bbox": [100, 200, 300, 230],
                        "html": '<p><math display="block">\\gamma_k = 1</math></p>',
                    }
                ],
            },
            {
                "id": "/page/1/Page/2",
                "block_type": "Page",
                "bbox": [10, 20, 604, 812],
                "children": [
                    {
                        "id": "/page/1/Text/0",
                        "block_type": "Text",
                        "bbox": [50, 60, 70, 80],
                        "html": "x",
                    },
                    {
                        "id": "/page/1/Equation/5",
                        "block_type": "Equation",
                        "bbox": [110, 220, 310, 250],
                        "html": "<math>y</math>",
                    },
                ],
            },
        ],
    }
    eqs = marker.equations(doc)
    assert [(e.page_index, e.box) for e in eqs] == [
        (0, crop.Box(100, 200, 300, 230)),
        (1, crop.Box(100, 200, 300, 230)),
    ]
    assert marker.latex_of(eqs[0].html) == "\\gamma_k = 1"
    assert len(marker.blocks(doc)) == 3
