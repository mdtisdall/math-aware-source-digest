"""Parse and normalize the identifiers that a user can give for a source."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Kind = Literal["doi", "arxiv", "pmcid", "pmid", "isbn", "zotero", "pdf", "title"]

_DOI = re.compile(r"(10\.\d{4,9}/\S+)", re.IGNORECASE)
_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_ARXIV_NEW = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")
_ARXIV_OLD = re.compile(r"^([a-z][a-z\-]*(?:\.[A-Z]{2})?/\d{7})(v\d+)?$")
_ARXIV_PREFIX = re.compile(
    r"^(?:arxiv:\s*|https?://(?:www\.|export\.)?arxiv\.org/(?:abs|pdf|e-print)/)", re.IGNORECASE
)
_PMCID = re.compile(r"^PMC(\d+)$", re.IGNORECASE)
_PMID = re.compile(r"^pmid:\s*(\d+)$", re.IGNORECASE)
_ZOTERO = re.compile(r"^zotero:([A-Z0-9]{8})$")
_ISBN = re.compile(r"^(?:isbn:?\s*)?([0-9Xx][0-9Xx\- ]{8,16}[0-9Xx])$", re.IGNORECASE)


@dataclass(frozen=True)
class Identifier:
    kind: Kind
    value: str
    version: str = ""  # an arXiv version such as "v2", if the input named one

    def __str__(self) -> str:
        return f"{self.kind}:{self.value}{self.version}"


def normalize_doi(text: str) -> str | None:
    """Return the DOI in lower case, without a resolver prefix or trailing punctuation."""
    match = _DOI.search(_DOI_PREFIX.sub("", text.strip()))
    if not match:
        return None
    return match.group(1).rstrip(".,;)]}>\"'").lower()


def parse_arxiv(text: str) -> tuple[str, str] | None:
    """Return (identifier, version) of an arXiv identifier or URL, else None."""
    core = _ARXIV_PREFIX.sub("", text.strip()).removesuffix(".pdf")
    for pattern in (_ARXIV_NEW, _ARXIV_OLD):
        match = pattern.match(core)
        if match:
            return match.group(1), match.group(2) or ""
    return None


def _isbn10_ok(digits: str) -> bool:
    total = sum((10 - i) * (10 if c in "Xx" else int(c)) for i, c in enumerate(digits))
    return digits[:9].isdigit() and total % 11 == 0


def _isbn13_ok(digits: str) -> bool:
    if not digits.isdigit():
        return False
    return sum((3 if i % 2 else 1) * int(c) for i, c in enumerate(digits)) % 10 == 0


def normalize_isbn(text: str) -> str | None:
    """Return the ISBN-13 for a valid ISBN-10 or ISBN-13, else None."""
    match = _ISBN.match(text.strip())
    if not match:
        return None
    digits = re.sub(r"[\- ]", "", match.group(1)).upper()
    if len(digits) == 13 and _isbn13_ok(digits):
        return digits
    if len(digits) == 10 and _isbn10_ok(digits):
        core = "978" + digits[:9]
        check = (10 - sum((3 if i % 2 else 1) * int(c) for i, c in enumerate(core)) % 10) % 10
        return core + str(check)
    return None


def parse(text: str) -> Identifier:
    """Classify one input. Anything that is not a known identifier is a title."""
    stripped = text.strip()
    if not stripped:
        raise ValueError("empty input")
    if (match := _ZOTERO.match(stripped)) is not None:
        return Identifier("zotero", match.group(1))
    if (match := _PMCID.match(stripped)) is not None:
        return Identifier("pmcid", f"PMC{match.group(1)}")
    if (match := _PMID.match(stripped)) is not None:
        return Identifier("pmid", match.group(1))
    if (arxiv := parse_arxiv(stripped)) is not None:
        return Identifier("arxiv", arxiv[0], arxiv[1])
    if _DOI_PREFIX.match(stripped) or re.match(r"^10\.\d{4,9}/", stripped):
        doi = normalize_doi(stripped)
        if doi:
            # arXiv DOIs name the preprint: treat them as arXiv identifiers.
            if doi.startswith("10.48550/arxiv."):
                found = parse_arxiv(doi.removeprefix("10.48550/arxiv."))
                if found:
                    return Identifier("arxiv", found[0], found[1])
            return Identifier("doi", doi)
    if (isbn := normalize_isbn(stripped)) is not None:
        return Identifier("isbn", isbn)
    if stripped.lower().endswith(".pdf") and Path(stripped).expanduser().is_file():
        return Identifier("pdf", str(Path(stripped).expanduser().resolve()))
    return Identifier("title", " ".join(stripped.split()))
