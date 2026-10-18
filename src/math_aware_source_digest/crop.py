"""Crop a span (equation, line, sentence, table cell) from a PDF page as a PNG.

Boxes are in PDF points with the origin at the top left of the page (as in
Marker's JSON). pypdfium2 gives the page geometry; ``pdftoppm`` (poppler,
in the devShell) renders the crop, so that no imaging library is needed.
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

CROP_DPI = 300
PAD_PT = 6.0
RENDER_TIMEOUT_S = 60


class CropError(Exception):
    pass


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float

    def __post_init__(self) -> None:
        if not (self.x1 > self.x0 and self.y1 > self.y0):
            raise CropError(f"empty box: {self}")


@dataclass(frozen=True)
class PixelWindow:
    x: int
    y: int
    width: int
    height: int


def page_size_pt(pdf: Path, page_index: int) -> tuple[float, float]:
    doc = pdfium.PdfDocument(pdf)
    try:
        if not 0 <= page_index < len(doc):
            raise CropError(f"page {page_index + 1} not in {pdf.name} ({len(doc)} pages)")
        page = doc[page_index]
        width, height = page.get_size()
        page.close()
        return float(width), float(height)
    finally:
        doc.close()


def pixel_window(
    box: Box, page_w: float, page_h: float, dpi: int = CROP_DPI, pad_pt: float = PAD_PT
) -> PixelWindow:
    """The pixel window of ``box`` plus padding, clamped to the page."""
    scale = dpi / 72.0
    x0 = max(box.x0 - pad_pt, 0.0)
    y0 = max(box.y0 - pad_pt, 0.0)
    x1 = min(box.x1 + pad_pt, page_w)
    y1 = min(box.y1 + pad_pt, page_h)
    if x1 <= x0 or y1 <= y0:
        raise CropError(f"box {box} lies outside the page ({page_w} x {page_h} pt)")
    left, top = int(x0 * scale), int(y0 * scale)
    return PixelWindow(left, top, max(round(x1 * scale) - left, 1), max(round(y1 * scale) - top, 1))


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise CropError(f"not a PNG: {path}")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def crop(
    pdf: Path, page_index: int, box: Box, out_png: Path, dpi: int = CROP_DPI, pad_pt: float = PAD_PT
) -> Path:
    """Render the crop to ``out_png`` (``page_index`` counts from 0)."""
    if shutil.which("pdftoppm") is None:
        raise CropError("pdftoppm is not on PATH: run inside `nix develop`")
    width, height = page_size_pt(pdf, page_index)
    win = pixel_window(box, width, height, dpi, pad_pt)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    stem = out_png.with_suffix("")
    cmd = [
        "pdftoppm",
        "-r",
        str(dpi),
        "-f",
        str(page_index + 1),
        "-l",
        str(page_index + 1),
        "-singlefile",
        "-png",
        "-x",
        str(win.x),
        "-y",
        str(win.y),
        "-W",
        str(win.width),
        "-H",
        str(win.height),
        str(pdf),
        str(stem),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=RENDER_TIMEOUT_S)
    except subprocess.CalledProcessError as ex:
        raise CropError(f"pdftoppm failed: {ex.stderr.decode(errors='replace')[:300]}") from ex
    except subprocess.TimeoutExpired as ex:
        raise CropError(f"pdftoppm did not finish in {RENDER_TIMEOUT_S} s") from ex
    produced = stem.with_suffix(".png")
    if produced != out_png:
        produced.replace(out_png)
    return out_png


def render_page(pdf: Path, page_index: int, out_png: Path, dpi: int = 150) -> Path:
    """A whole page image (150 dpi by default, as kept by stage 3)."""
    width, height = page_size_pt(pdf, page_index)
    return crop(pdf, page_index, Box(0, 0, width, height), out_png, dpi, pad_pt=0)
