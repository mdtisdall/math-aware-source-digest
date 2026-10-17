from __future__ import annotations

from pathlib import Path

import pytest

from math_aware_source_digest.resolve import ids


@pytest.mark.parametrize(
    "text, kind, value, version",
    [
        ("10.1002/mrm.22180", "doi", "10.1002/mrm.22180", ""),
        (
            "https://doi.org/10.1088/0266-5611/29/1/015008",
            "doi",
            "10.1088/0266-5611/29/1/015008",
            "",
        ),
        ("doi:10.1109/5.843002.", "doi", "10.1109/5.843002", ""),
        ("DOI: 10.1002/MRM.22180", "doi", "10.1002/mrm.22180", ""),
        ("10.48550/arXiv.1301.2831", "arxiv", "1301.2831", ""),
        ("arXiv:2302.14545v3", "arxiv", "2302.14545", "v3"),
        ("https://arxiv.org/abs/1108.4146", "arxiv", "1108.4146", ""),
        ("https://arxiv.org/pdf/1505.01619v2.pdf", "arxiv", "1505.01619", "v2"),
        ("math-ph/0401050", "arxiv", "math-ph/0401050", ""),
        ("math.ST/0601001v1", "arxiv", "math.ST/0601001", "v1"),
        ("PMC4142121", "pmcid", "PMC4142121", ""),
        ("pmid: 19859957", "pmid", "19859957", ""),
        ("978-0-387-22073-4", "isbn", "9780387220734", ""),
        ("0387220739", "isbn", "9780387220734", ""),
        ("zotero:YCVGJZLT", "zotero", "YCVGJZLT", ""),
        ("Sampling:  50 years after Shannon", "title", "Sampling: 50 years after Shannon", ""),
        ("978-0-387-22073-5", "title", "978-0-387-22073-5", ""),  # bad check digit
    ],
)
def test_parse(text: str, kind: str, value: str, version: str) -> None:
    ident = ids.parse(text)
    assert (ident.kind, ident.value, ident.version) == (kind, value, version)


def test_pdf_path(tmp_path: Path) -> None:
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    assert ids.parse(str(pdf)) == ids.Identifier("pdf", str(pdf.resolve()))


def test_missing_pdf_is_a_title() -> None:
    assert ids.parse("/no/such/paper.pdf").kind == "title"


def test_empty_input_is_refused() -> None:
    with pytest.raises(ValueError):
        ids.parse("   ")
