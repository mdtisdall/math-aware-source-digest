from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

import pytest
import responses
from pdfs import make_pdf

from math_aware_source_digest import acquire, config, net
from math_aware_source_digest.acquire import Failure
from math_aware_source_digest.cache import SourceCache

TITLE = "Optimization of k-space trajectories for compressed sensing"


def write(tmp_path: Path, data: bytes, name: str = "doc.pdf") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def fetcher(
    tmp_path: Path, hosts: tuple[str, ...] = ("arxiv.org", "ncbi.nlm.nih.gov", "example.org")
) -> net.Fetcher:
    cfg = config.Config(
        cache_root=tmp_path / "cache",
        downloads=config.DownloadConfig(allowed_hosts=hosts),
        network=config.NetworkConfig(min_interval_s=0, host_intervals_s={}),
    )
    return net.Fetcher(cfg, sleep=lambda s: None)


# PDF checks


def test_good_pdf_passes(tmp_path: Path) -> None:
    pdf = write(
        tmp_path,
        make_pdf(
            [
                ["Optimization of k-space", "trajectories for compressed", "sensing", "x" * 2000],
                ["page two"],
            ]
        ),
    )
    check = acquire.check_pdf(pdf, TITLE)
    assert check.ok, check.failures
    assert check.pages == 2


def test_html_error_page(tmp_path: Path) -> None:
    page = b"<!DOCTYPE html><html><head><title>Sign in</title></head><body>Log in</body></html>"
    assert acquire.check_pdf(write(tmp_path, page)).failures == [Failure.HTML_PAGE]


def test_not_a_pdf(tmp_path: Path) -> None:
    assert acquire.check_pdf(write(tmp_path, b"PK\x03\x04zipfile")).failures == [Failure.NOT_PDF]


def test_truncated_pdf_is_unreadable(tmp_path: Path) -> None:
    check = acquire.check_pdf(write(tmp_path, b"%PDF-1.4\n" + b"garbage" * 400))
    assert Failure.UNREADABLE in check.failures


def test_small_pdf_is_flagged(tmp_path: Path) -> None:
    check = acquire.check_pdf(write(tmp_path, make_pdf([["tiny"]])))
    assert Failure.TOO_SMALL in check.failures


def test_wrong_paper_is_caught_by_the_title(tmp_path: Path) -> None:
    pdf = write(tmp_path, make_pdf([["Sampling - 50 years after Shannon", "y" * 3000]]))
    assert Failure.TITLE_NOT_FOUND in acquire.check_pdf(pdf, TITLE).failures


def test_title_across_lines_and_hyphens() -> None:
    assert acquire.title_on_page(
        TITLE, "Optimization of k-\nspace trajectories for\ncompressed sensing by Bayesian design"
    )
    assert not acquire.title_on_page(TITLE, "Optimization of trajectories")


# Version of a PDF


@pytest.mark.parametrize(
    "text, version",
    [
        ("Author Manuscript. Published in final edited form as: Magn Reson Med. 2010", "accepted"),
        ("This is the peer reviewed version of the following article", "accepted"),
        ("arXiv:1301.2831v2 [cs.IT] 12 Feb 2013\nBeyond consistent reconstructions", "submitted"),
        ("Preprint submitted to Elsevier", "submitted"),
        (
            "Magnetic Resonance in Medicine 63:116-126 (2010)\nVol. 63, pp. 116-126\n"
            "© 2009 Wiley-Liss, Inc.",
            "published",
        ),
        ("Some text without any signs", None),
    ],
)
def test_pdf_version(text: str, version: str | None) -> None:
    assert acquire.pdf_version(text)[0] == version


# arXiv sources


def tgz(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


MAIN = b"\\documentclass{article}\n\\begin{document}\n\\input{sec}\n\\end{document}\n"


@responses.activate
def test_arxiv_tarball(tmp_path: Path) -> None:
    responses.get(
        "https://arxiv.org/e-print/1301.2831",
        body=tgz({"ms.tex": MAIN, "sec.tex": b"$x$", "fig.png": b"\x89PNG"}),
    )
    got = acquire.download_arxiv_source(
        fetcher(tmp_path), SourceCache(tmp_path / "c", "k"), "1301.2831"
    )
    assert got.check.ok and got.main_tex is not None and got.main_tex.name == "ms.tex"


@responses.activate
def test_arxiv_single_gzipped_tex(tmp_path: Path) -> None:
    responses.get("https://arxiv.org/e-print/math-ph/0401050", body=gzip.compress(MAIN))
    got = acquire.download_arxiv_source(
        fetcher(tmp_path), SourceCache(tmp_path / "c", "k"), "math-ph/0401050"
    )
    assert got.check.ok and got.main_tex is not None


@responses.activate
def test_arxiv_pdf_only(tmp_path: Path) -> None:
    responses.get("https://arxiv.org/e-print/2001.00001", body=make_pdf([["z" * 3000]]))
    got = acquire.download_arxiv_source(
        fetcher(tmp_path), SourceCache(tmp_path / "c", "k"), "2001.00001"
    )
    assert got.form == "pdf"
    assert "only a PDF" in got.check.notes[0]


@responses.activate
def test_arxiv_malicious_tarball(tmp_path: Path) -> None:
    responses.get("https://arxiv.org/e-print/2001.00002", body=tgz({"../../escape.tex": MAIN}))
    got = acquire.download_arxiv_source(
        fetcher(tmp_path), SourceCache(tmp_path / "c", "k"), "2001.00002"
    )
    assert got.check.failures == [Failure.UNSAFE_ARCHIVE]
    assert not list(tmp_path.rglob("escape.tex"))


@responses.activate
def test_arxiv_without_latex(tmp_path: Path) -> None:
    responses.get("https://arxiv.org/e-print/2001.00003", body=tgz({"readme.txt": b"hello"}))
    got = acquire.download_arxiv_source(
        fetcher(tmp_path), SourceCache(tmp_path / "c", "k"), "2001.00003"
    )
    assert got.check.failures == [Failure.NO_LATEX]


@responses.activate
def test_download_outside_policy_is_not_made(tmp_path: Path) -> None:
    with pytest.raises(net.ApprovalRequired):
        acquire.download_pdf(
            fetcher(tmp_path, hosts=()),
            SourceCache(tmp_path / "c", "k"),
            "https://example.org/paper.pdf",
        )
    assert len(responses.calls) == 0


# JATS


JATS_MATHML = (
    b'<?xml version="1.0"?><pmc-articleset><article><body><disp-formula>'
    b"<mml:math><mml:mi>x</mml:mi></mml:math></disp-formula></body></article>"
    b"</pmc-articleset>"
)
JATS_IMAGES = (
    b'<?xml version="1.0"?><pmc-articleset><article><body><disp-formula id="e1">'
    b'<graphic xlink:href="eq1.gif"/></disp-formula><inline-formula>'
    b'<inline-graphic xlink:href="i1.gif"/></inline-formula></body></article>'
    b"</pmc-articleset>"
)


def test_jats_with_mathml_passes() -> None:
    assert acquire.check_jats(JATS_MATHML).ok


def test_jats_with_math_as_images_fails() -> None:
    check = acquire.check_jats(JATS_IMAGES)
    assert check.failures == [Failure.MATH_AS_IMAGES]
    assert "formulas as images 2" in check.notes[0]


def test_jats_error_page() -> None:
    page = b"<!DOCTYPE html><html><body>Error</body></html>"
    assert acquire.check_jats(page).failures == [Failure.HTML_PAGE]


@responses.activate
def test_pmc_xml_download(tmp_path: Path) -> None:
    responses.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", body=JATS_MATHML)
    got = acquire.download_pmc_xml(
        fetcher(tmp_path), SourceCache(tmp_path / "c", "k"), "PMC4142121"
    )
    assert got.check.ok
    assert "id=4142121" in str(responses.calls[0].request.url)
