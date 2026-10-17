"""Stage 2: acquire a source, and check what was downloaded before it counts.

Each check failure has a code, so that a worklist can say why a source is
missing. The download checks, the failure codes and the check of a PDF's
version follow the ideas of research-superpowers (MIT); the code here is
written anew.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

import pypdfium2 as pdfium

from .archive import UnsafeArchive, extract_tar, gunzip_limited, is_tar
from .cache import SourceCache
from .net import Fetcher
from .resolve.match import fold

MIN_PDF_BYTES = 2048
MAX_PDF_BYTES = 200 * 1024 * 1024
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class Failure(StrEnum):
    HTML_PAGE = "html-page"  # an HTML page (login wall, error page) instead of the file
    NOT_PDF = "not-pdf"
    TOO_SMALL = "too-small"
    TOO_LARGE = "too-large"
    UNREADABLE = "unreadable"  # PDFium cannot open it
    ENCRYPTED = "encrypted"
    NO_PAGES = "no-pages"
    TITLE_NOT_FOUND = "title-not-found"  # the expected title is not on the first page(s)
    NOT_JATS = "not-jats"
    MATH_AS_IMAGES = "math-as-images"
    UNSAFE_ARCHIVE = "unsafe-archive"
    NO_LATEX = "no-latex"


@dataclass
class Check:
    ok: bool
    failures: list[Failure] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    pages: int = 0


def _looks_like_html(data: bytes) -> bool:
    head = data[:1024].lstrip().lower()
    return head.startswith((b"<!doctype html", b"<html", b"<head", b"<?xml version")) and (
        b"<html" in head or b"<!doctype html" in head
    )


def first_pages_text(path: Path, pages: int = 2) -> str:
    """The text layer of the first pages, for the title check only (never for mathematics)."""
    doc = pdfium.PdfDocument(path)
    try:
        parts = []
        for i in range(min(pages, len(doc))):
            page = doc[i]
            textpage = page.get_textpage()
            parts.append(textpage.get_text_range())
            textpage.close()
            page.close()
        return "\n".join(parts)
    finally:
        doc.close()


def title_on_page(title: str, text: str) -> bool:
    """True if the title's words appear in order on the page (markup and hyphens ignored)."""
    target, page = fold(title), fold(text)
    if target and target in page:
        return True
    # Line breaks, hyphenation, markup: accept if 90% of the title's words occur on the page.
    words = [fold(w) for w in title.split() if fold(w)]
    hits = sum(1 for w in words if w in page)
    return bool(words) and hits / len(words) >= 0.9


def check_pdf(path: Path, title: str = "") -> Check:
    data = path.read_bytes()
    check = Check(ok=False)
    if _looks_like_html(data):
        check.failures.append(Failure.HTML_PAGE)
        return check
    if not data.startswith(b"%PDF-"):
        check.failures.append(Failure.NOT_PDF)
        return check
    if len(data) < MIN_PDF_BYTES:
        check.failures.append(Failure.TOO_SMALL)
    if len(data) > MAX_PDF_BYTES:
        check.failures.append(Failure.TOO_LARGE)
    try:
        doc = pdfium.PdfDocument(path)
    except pdfium.PdfiumError as ex:
        message = str(ex).lower()
        check.failures.append(Failure.ENCRYPTED if "password" in message else Failure.UNREADABLE)
        return check
    try:
        check.pages = len(doc)
    finally:
        doc.close()
    if check.pages == 0:
        check.failures.append(Failure.NO_PAGES)
    if title and check.pages and not title_on_page(title, first_pages_text(path)):
        check.failures.append(Failure.TITLE_NOT_FOUND)
    check.ok = not check.failures
    return check


# Which version a PDF is

_SUBMITTED = [r"\bpreprint\b", r"submitted to\b", r"\bunder review\b", r"not peer[- ]reviewed"]
_ACCEPTED = [
    r"accepted manuscript",
    r"author manuscript",
    r"author'?s? accepted",
    r"peer[- ]reviewed version",
    r"\bpostprint\b",
    r"\bin press\b",
    r"\bnihms\d+",
]
_PUBLISHED = [
    r"\bvol(?:ume)?\.?\s*\d+",
    r"\bpp?\.\s*\d+\s*[-\u2013]\s*\d+",
    r"©\s*(?:19|20)\d\d",
    r"\bdoi:\s*10\.\d{4,9}/",
    r"published online",
    r"all rights reserved",
]


def pdf_version(text: str) -> tuple[str | None, list[str]]:
    """Guess (submitted | accepted | published | None) from the first pages' text, with evidence.

    The record's version (Unpaywall, OpenAlex) can be wrong for a given file;
    this reads the file. Signs of a submitted or accepted manuscript win over
    signs of a publisher's layout, because manuscripts often quote the journal.
    """
    lower = text.lower()
    evidence: dict[str, list[str]] = {"submitted": [], "accepted": [], "published": []}
    for name, patterns in (
        ("submitted", _SUBMITTED),
        ("accepted", _ACCEPTED),
        ("published", _PUBLISHED),
    ):
        for pattern in patterns:
            match = re.search(pattern, lower)
            if match:
                evidence[name].append(match.group(0))
    arxiv_stamp = re.search(r"arxiv:\d{4}\.\d{4,5}v\d+", lower)
    if arxiv_stamp:
        evidence["submitted"].append(arxiv_stamp.group(0))
    for name in ("accepted", "submitted"):
        if evidence[name]:
            return name, evidence[name]
    if len(evidence["published"]) >= 2:
        return "published", evidence["published"]
    return None, evidence["published"]


# Downloads


@dataclass
class Acquired:
    path: Path | None
    form: str  # "pdf", "latex", "jats"
    check: Check
    files: list[Path] = field(default_factory=list)  # for LaTeX: the extracted files
    main_tex: Path | None = None


def download_pdf(fetcher: Fetcher, cache: SourceCache, url: str, title: str = "") -> Acquired:
    response = fetcher.get(url, cache=False)
    path = cache.store_bytes(response.content, "pdf")
    return Acquired(path, "pdf", check_pdf(path, title))


def find_main_tex(files: list[Path]) -> Path | None:
    """The file with ``\\documentclass`` and ``\\begin{document}``; if several, the largest."""
    candidates = []
    for path in files:
        if path.suffix.lower() not in (".tex", ".ltx", ""):
            continue
        text = path.read_text(errors="replace")
        if re.search(r"^\s*\\documentclass", text, re.M) and "\\begin{document}" in text:
            candidates.append(path)
    return max(candidates, key=lambda p: p.stat().st_size) if candidates else None


def download_arxiv_source(fetcher: Fetcher, cache: SourceCache, arxiv_id: str) -> Acquired:
    """arXiv's e-print: a gzipped tar, a single gzipped TeX file, or a PDF."""
    response = fetcher.get(f"https://arxiv.org/e-print/{arxiv_id}", cache=False)
    data = response.content
    stored = cache.store_bytes(data, "eprint")
    if data.startswith(b"%PDF-"):
        pdf = cache.store_bytes(data, "pdf")
        check = check_pdf(pdf)
        check.notes.append("arXiv has only a PDF for this identifier")
        return Acquired(pdf, "pdf", check)
    check = Check(ok=False)
    try:
        raw = gunzip_limited(data) if data[:2] == b"\x1f\x8b" else data
        dest = cache.stage_dir("acquire") / "arxiv-source"
        if dest.exists():
            shutil.rmtree(dest)
        if is_tar(raw):
            files = extract_tar(raw, dest)
        else:
            dest.mkdir(parents=True)
            (dest / "main.tex").write_bytes(raw)
            files = [dest / "main.tex"]
    except UnsafeArchive as ex:
        check.failures.append(Failure.UNSAFE_ARCHIVE)
        check.notes.append(str(ex))
        return Acquired(stored, "latex", check)
    main = find_main_tex(files)
    if main is None:
        check.failures.append(Failure.NO_LATEX)
        return Acquired(stored, "latex", check, files)
    check.ok = True
    return Acquired(stored, "latex", check, files, main)


def check_jats(xml: bytes) -> Check:
    check = Check(ok=False)
    head = xml[:4096].lower()
    if _looks_like_html(xml) and b"<article" not in xml[:65536].lower():
        check.failures.append(Failure.HTML_PAGE)
        return check
    if b"<article" not in xml[:65536].lower() and b"<pmc-articleset" not in head:
        check.failures.append(Failure.NOT_JATS)
        return check
    text = xml.decode("utf-8", errors="replace")
    mathml = len(re.findall(r"<(?:mml:)?math\b", text))
    tex = len(re.findall(r"<tex-math\b", text))
    image_formulas = len(
        re.findall(
            r"<(?:disp-formula|inline-formula)\b(?:(?!</(?:disp|inline)-formula>).)*?<(?:inline-)?graphic\b",
            text,
            re.S,
        )
    )
    check.notes.append(f"MathML {mathml}, TeX {tex}, formulas as images {image_formulas}")
    if image_formulas and image_formulas >= (mathml + tex):
        check.failures.append(Failure.MATH_AS_IMAGES)
    check.ok = not check.failures
    return check


def download_pmc_xml(fetcher: Fetcher, cache: SourceCache, pmcid: str) -> Acquired:
    number = pmcid.upper().removeprefix("PMC")
    params = {"db": "pmc", "id": number, "rettype": "xml", "tool": "math-aware-source-digest"}
    if fetcher.config.network.contact_email:
        params["email"] = fetcher.config.network.contact_email
    response = fetcher.get(EFETCH, params=params, cache=False)
    path = cache.store_bytes(response.content, "xml")
    return Acquired(path, "jats", check_jats(response.content))
