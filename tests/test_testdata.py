from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import responses

from math_aware_source_digest import cli, config, net, testdata
from math_aware_source_digest.cache import sha256_bytes

LIST = Path(__file__).resolve().parents[1] / "testdata" / "papers.toml"


def test_the_pinned_list_follows_the_rules() -> None:
    papers = testdata.load(LIST)
    assert len(papers) >= 9
    assert {p.key for p in papers if "judged" in p.roles} == {
        "student-1908",
        "hestenes-stiefel-1952",
        "zach-knoll-pock-2023",
        "blumenthal-2026",
        "harris-kleefeld-2019",
        "smith-schmidt-mcgee-1962",
        "blucker-1968",
    }
    assert all(p.licence in testdata.ALLOWED_LICENCES for p in papers)


def paper(**changes: object) -> testdata.Paper:
    base = testdata.Paper(
        key="x-2000",
        id="doi:10.1/x",
        title="X",
        url="https://example.org/x.pdf",
        fetch="auto",
        sha256=sha256_bytes(b"%PDF-1.4 x"),
        bytes=10,
        pages=1,
        licence="CC-BY-4.0",
        licence_source="test",
        roles=("judged",),
        form="scan",
        faces="",
        tests="",
    )
    return dataclasses.replace(base, **changes)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "change, message",
    [
        ({"licence": "CC-BY-NC-4.0"}, "not allowed for test data"),
        ({"licence": "all-rights-reserved"}, "not allowed"),
        ({"roles": ("favourite",)}, "roles"),
        ({"fetch": "maybe"}, "fetch"),
        ({"url": "http://example.org/x.pdf"}, "https"),
        ({"sha256": "ABC"}, "sha256"),
        ({"licence_source": ""}, "licence_source"),
    ],
)
def test_rules(change: dict[str, object], message: str) -> None:
    assert any(message in p for p in testdata.check([paper(**change)]))


def test_duplicates() -> None:
    problems = testdata.check([paper(), paper(key="y-2001", id="doi:10.1/y")])
    assert problems == [f"duplicate sha256: {paper().sha256}"]


def cfg(tmp_path: Path) -> config.Config:
    return config.Config(
        cache_root=tmp_path / "cache",
        network=config.NetworkConfig(min_interval_s=0, host_intervals_s={}),
    )


@responses.activate
def test_fetch_checks_the_hash(tmp_path: Path) -> None:
    responses.get("https://example.org/x.pdf", body=b"%PDF-1.4 x")
    c = cfg(tmp_path)
    path = testdata.fetch(paper(), c, net.Fetcher(c, sleep=lambda s: None))
    assert path.read_bytes() == b"%PDF-1.4 x"
    assert testdata.fetch(paper(), c) == path  # cached: no second request
    assert len(responses.calls) == 1


@responses.activate
def test_fetch_refuses_a_different_file(tmp_path: Path) -> None:
    responses.get("https://example.org/x.pdf", body=b"%PDF-1.4 changed")
    c = cfg(tmp_path)
    with pytest.raises(testdata.TestDataError, match="not the pinned"):
        testdata.fetch(paper(), c, net.Fetcher(c, sleep=lambda s: None))
    assert paper().cached_path(c) is None


@responses.activate
def test_fetch_follows_a_redirect_on_the_same_site_only(tmp_path: Path) -> None:
    responses.get(
        "https://example.org/x.pdf",
        status=302,
        headers={"Location": "https://cdn.example.org/x.pdf"},
    )
    responses.get("https://cdn.example.org/x.pdf", body=b"%PDF-1.4 x")
    c = cfg(tmp_path)
    assert testdata.fetch(paper(), c, net.Fetcher(c, sleep=lambda s: None)).is_file()
    responses.get(
        "https://example.net/y.pdf",
        status=302,
        headers={"Location": "https://validate.botcheck.example/?u=1"},
    )
    other = paper(key="y", id="doi:10.1/y", url="https://example.net/y.pdf", sha256="0" * 64)
    with pytest.raises(testdata.TestDataError, match="another site"):
        testdata.fetch(other, c, net.Fetcher(c, sleep=lambda s: None))


def test_manual_papers_explain_what_to_do(tmp_path: Path) -> None:
    with pytest.raises(testdata.TestDataError, match="by hand"):
        testdata.fetch(paper(fetch="manual"), cfg(tmp_path))


def test_import_recognizes_the_hash(tmp_path: Path) -> None:
    c = cfg(tmp_path)
    good = tmp_path / "download.pdf"
    good.write_bytes(b"%PDF-1.4 x")
    assert testdata.import_file(good, [paper(fetch="manual")], c).key == "x-2000"
    assert paper().cached_path(c) is not None
    bad = tmp_path / "other.pdf"
    bad.write_bytes(b"%PDF-1.4 other")
    with pytest.raises(testdata.TestDataError, match="matches no pinned"):
        testdata.import_file(bad, [paper()], c)


def test_cli_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["testdata", "list", "--list", str(LIST)]) == 0
    out = capsys.readouterr().out
    assert "student-1908" in out and "committed" in out


def test_committed_papers_are_present_and_intact() -> None:
    papers = testdata.load(LIST)
    assert testdata.verify(papers, LIST) == []
    zach = next(p for p in papers if p.key == "zach-knoll-pock-2023")
    assert (LIST.parent.parent / zach.exact_source / "main.tex").is_file()


def test_pdf_path_prefers_the_committed_copy_and_checks_it(tmp_path: Path) -> None:
    listed = tmp_path / "testdata" / "papers.toml"
    (tmp_path / "testdata" / "papers").mkdir(parents=True)
    committed = tmp_path / "testdata" / "papers" / "x-2000.pdf"
    committed.write_bytes(b"%PDF-1.4 x")
    assert testdata.pdf_path(paper(), listed, cfg(tmp_path)) == committed
    committed.write_bytes(b"%PDF-1.4 tampered")
    with pytest.raises(testdata.TestDataError, match="differs"):
        testdata.pdf_path(paper(), listed, cfg(tmp_path))
    committed.unlink()
    with pytest.raises(testdata.TestDataError, match="no committed or cached"):
        testdata.pdf_path(paper(), listed, cfg(tmp_path))


def test_verify_reports_missing_and_changed(tmp_path: Path) -> None:
    listed = tmp_path / "testdata" / "papers.toml"
    (tmp_path / "testdata" / "papers").mkdir(parents=True)
    assert "missing" in testdata.verify([paper()], listed)[0]
    (tmp_path / "testdata" / "papers" / "x-2000.pdf").write_bytes(b"other")
    assert "does not match" in testdata.verify([paper()], listed)[0]


@responses.activate
def test_verify_remote(tmp_path: Path) -> None:
    c = cfg(tmp_path)
    responses.get("https://example.org/x.pdf", body=b"%PDF-1.4 x")
    assert testdata.verify_remote(paper(), c, net.Fetcher(c, sleep=lambda s: None)) == "same"
    responses.replace(responses.GET, "https://example.org/x.pdf", body=b"%PDF-1.4 new version")
    verdict = testdata.verify_remote(paper(), c, net.Fetcher(c, sleep=lambda s: None))
    assert verdict.startswith("changed")
    assert testdata.verify_remote(paper(fetch="manual"), c).startswith("not checked")
