from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest
import requests
import responses

from math_aware_source_digest import config, net
from math_aware_source_digest.resolve import Resolver, sources
from math_aware_source_digest.resolve.zotero import LocalZotero, ZoteroError

FIXTURES = Path(__file__).parent / "fixtures" / "resolve"
ALL_HOSTS = (
    "crossref.org",
    "datacite.org",
    "openalex.org",
    "semanticscholar.org",
    "unpaywall.org",
    "ebi.ac.uk",
    "openlibrary.org",
)
SEEGER = "10.1002/mrm.22180"


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


def make_resolver(
    tmp_path: Path,
    hosts: tuple[str, ...] = ALL_HOSTS,
    email: str = "",
    zotero: LocalZotero | None = None,
) -> Resolver:
    cfg = config.Config(
        cache_root=tmp_path / "cache",
        downloads=config.DownloadConfig(allowed_hosts=hosts),
        network=config.NetworkConfig(contact_email=email, min_interval_s=0.0, host_intervals_s={}),
    )
    return Resolver(net.Fetcher(cfg, sleep=lambda s: None), zotero)


def mock_seeger(s2: Any = None) -> None:
    responses.get(f"{sources.CROSSREF}/{SEEGER}", json=fixture("crossref-seeger-2010.json"))
    responses.get(f"{sources.OPENALEX}/doi:{SEEGER}", json=fixture("openalex-seeger-2010.json"))
    responses.post(
        re.compile(re.escape(sources.SEMANTIC_SCHOLAR)),
        json=s2 if s2 is not None else fixture("s2.json")[:1],
    )
    responses.get(
        re.compile(re.escape(sources.EUROPE_PMC)), json=fixture("europepmc-seeger-2010.json")
    )


@responses.activate
def test_doi_citation_comes_from_crossref_with_provenance(tmp_path: Path) -> None:
    mock_seeger()
    res = make_resolver(tmp_path).resolve("https://doi.org/10.1002/MRM.22180")
    assert res.found
    c = res.citation
    assert c["title"].value.startswith("Optimization of k")
    assert c["title"].provenance.source == "crossref"
    assert [a.family for a in c["authors"].value] == ["Seeger", "Nickisch", "Pohmann", "Schölkopf"]
    # The printed issue's year, not the online date (2009), and which field it came from.
    assert c["year"].value == 2010
    assert c["year"].provenance.detail == "published-print"
    assert (c["volume"].value, c["issue"].value, c["page"].value) == ("63", "1", "116-126")
    assert c["container"].value == "Magnetic Resonance in Medicine"


@responses.activate
def test_secondary_records_add_identifiers_and_copies_not_citation_fields(tmp_path: Path) -> None:
    mock_seeger()
    res = make_resolver(tmp_path).resolve(SEEGER)
    assert res.identifiers["pmid"].value == "19859957"
    assert res.identifiers["arxiv"].value == "0903.0001"
    assert res.identifiers["arxiv"].provenance.source == "openalex"
    forms = {(c.form, c.version) for c in res.copies}
    assert ("arxiv-source", "submitted") in forms
    assert ("pdf", "published") in forms
    assert res.citation["year"].provenance.source == "crossref"  # OpenAlex says 2009


@responses.activate
def test_unpaywall_is_skipped_without_contact_email(tmp_path: Path) -> None:
    mock_seeger()
    res = make_resolver(tmp_path).resolve(SEEGER)
    assert any("Unpaywall skipped" in w for w in res.warnings)
    assert not any("unpaywall" in str(call.request.url) for call in responses.calls)


@responses.activate
def test_unpaywall_with_contact_email(tmp_path: Path) -> None:
    mock_seeger()
    responses.get(
        re.compile(re.escape(f"{sources.UNPAYWALL}/{SEEGER}")),
        json={
            "oa_locations": [
                {
                    "url_for_pdf": "https://example.edu/accepted.pdf",
                    "version": "acceptedVersion",
                    "license": "cc-by",
                }
            ]
        },
    )
    res = make_resolver(tmp_path, email="me@example.org").resolve(SEEGER)
    accepted = [c for c in res.copies if c.version == "accepted"]
    assert accepted and accepted[0].licence == "cc-by"
    assert accepted[0].provenance.source == "unpaywall"


@responses.activate
def test_made_up_reference_resolves_to_nothing(tmp_path: Path) -> None:
    responses.get(
        re.compile(re.escape(sources.CROSSREF) + r"\?"),
        json=fixture("crossref-search-made-up.json"),
    )
    res = make_resolver(tmp_path).resolve("Quantum gravitational lensing of tea cosies")
    assert not res.found
    assert "no record matched" in res.unresolved
    assert res.citation == {}


@responses.activate
def test_title_search_accepts_a_matching_record(tmp_path: Path) -> None:
    mock_seeger()
    search = {
        "message": {
            "items": [
                {
                    "DOI": "10.9999/other",
                    "title": ["Something else entirely"],
                    "author": [{"family": "X"}],
                },
                {
                    "DOI": SEEGER.upper(),
                    "title": [
                        "Optimization of k-space trajectories for compressed "
                        "sensing by Bayesian experimental design"
                    ],
                    "author": [{"family": "Seeger"}],
                    "issued": {"date-parts": [[2009]]},
                },
            ]
        }
    }
    responses.get(re.compile(re.escape(sources.CROSSREF) + r"\?"), json=search)
    title = "Optimization of k-space trajectories for compressed sensing by Bayesian experimental"
    res = make_resolver(tmp_path).resolve(title + " design")
    assert res.found
    assert res.identifiers["doi"].value == SEEGER
    assert res.identifiers["doi"].provenance.detail == "title search"


@responses.activate
def test_retractions_and_corrections_are_reported(tmp_path: Path) -> None:
    doi = "10.1016/s0140-6736(97)11096-0"
    responses.get(
        re.compile(re.escape(f"{sources.CROSSREF}/10.1016")),
        json=fixture("crossref-retracted.json"),
    )
    responses.get(re.compile(re.escape(sources.OPENALEX)), status=404)
    responses.post(re.compile(re.escape(sources.SEMANTIC_SCHOLAR)), json=[None])
    responses.get(re.compile(re.escape(sources.EUROPE_PMC)), json={"resultList": {"result": []}})
    res = make_resolver(tmp_path).resolve(doi)
    kinds = {u.type for u in res.updates}
    assert {"retraction", "correction"} <= kinds
    assert all(u.provenance.source == "crossref" for u in res.updates)


@responses.activate
def test_arxiv_identifier_uses_datacite(tmp_path: Path) -> None:
    responses.get(
        f"{sources.DATACITE}/10.48550/arxiv.1301.2831",
        json=fixture("datacite-arxiv-1301.2831.json"),
    )
    responses.post(re.compile(re.escape(sources.SEMANTIC_SCHOLAR)), json=[None])
    res = make_resolver(tmp_path).resolve("arXiv:1301.2831v2")
    assert res.found
    assert res.citation["title"].provenance.source == "datacite"
    assert res.citation["year"].value == 2013
    assert any("version v2" in w for w in res.warnings)
    assert res.copies[0].url == "https://arxiv.org/e-print/1301.2831"
    sent = json.loads(responses.calls[-1].request.body or b"")
    assert sent == {"ids": ["ARXIV:1301.2831"]}


@responses.activate
def test_pmcid_goes_through_europe_pmc(tmp_path: Path) -> None:
    responses.get(
        re.compile(re.escape(sources.EUROPE_PMC)), json=fixture("europepmc-pmc4142121.json")
    )
    responses.get(
        f"{sources.CROSSREF}/10.1002/mrm.24751",
        json={
            "message": {
                "DOI": "10.1002/mrm.24751",
                "title": ["ESPIRiT"],
                "author": [{"family": "Uecker"}],
            }
        },
    )
    responses.get(re.compile(re.escape(sources.OPENALEX)), status=404)
    responses.post(re.compile(re.escape(sources.SEMANTIC_SCHOLAR)), json=[None])
    res = make_resolver(tmp_path).resolve("PMC4142121")
    assert res.found
    assert res.identifiers["doi"].provenance.source == "europepmc"
    assert res.identifiers["pmid"].value == "23649942"
    assert any(c.form == "pmc-xml" for c in res.copies)


@responses.activate
def test_semantic_scholar_is_one_batch_for_many_inputs(tmp_path: Path) -> None:
    for doi in ("10.1234/a", "10.1234/b", "10.1234/c"):
        responses.get(
            f"{sources.CROSSREF}/{doi}", json={"message": {"DOI": doi, "title": [f"Paper {doi}"]}}
        )
    responses.get(re.compile(re.escape(sources.OPENALEX)), status=404)
    responses.get(re.compile(re.escape(sources.EUROPE_PMC)), json={"resultList": {"result": []}})
    responses.post(
        re.compile(re.escape(sources.SEMANTIC_SCHOLAR)),
        json=[None, {"title": "Paper 10.1234/b", "externalIds": {"ArXiv": "2001.00001"}}, None],
    )
    results = make_resolver(tmp_path).resolve_many(["10.1234/a", "10.1234/b", "10.1234/c"])
    batches = [c for c in responses.calls if c.request.method == "POST"]
    assert len(batches) == 1
    assert results[1].identifiers["arxiv"].value == "2001.00001"


@responses.activate
def test_secondary_record_with_another_title_is_ignored(tmp_path: Path) -> None:
    mock_seeger(s2=[{"title": "A figshare copy of something else", "externalIds": {"ArXiv": "1"}}])
    res = make_resolver(tmp_path).resolve(SEEGER)
    assert any("different title" in w for w in res.warnings)
    assert res.identifiers["arxiv"].provenance.source == "openalex"


@responses.activate
def test_conflicting_identifiers_keep_the_first_and_warn(tmp_path: Path) -> None:
    mock_seeger(
        s2=[
            {
                "title": "Optimization of k-space trajectories for compressed sensing by "
                "Bayesian experimental design",
                "externalIds": {"PubMed": "11111111"},
            }
        ]
    )
    res = make_resolver(tmp_path).resolve(SEEGER)
    assert res.identifiers["pmid"].value == "11111111"  # Semantic Scholar runs before OpenAlex
    assert any("pmid" in w and "kept the first" in w for w in res.warnings)


@responses.activate
def test_hosts_outside_the_policy_are_not_contacted(tmp_path: Path) -> None:
    responses.get(f"{sources.CROSSREF}/{SEEGER}", json=fixture("crossref-seeger-2010.json"))
    res = make_resolver(tmp_path, hosts=("crossref.org",)).resolve(SEEGER)
    assert res.found
    assert any("needs the user's approval" in w for w in res.warnings)
    assert {str(c.request.url).split("/")[2] for c in responses.calls} == {"api.crossref.org"}


@responses.activate
def test_unknown_doi(tmp_path: Path) -> None:
    responses.get(re.compile(re.escape(sources.CROSSREF)), status=404)
    responses.get(re.compile(re.escape(sources.DATACITE)), status=404)
    res = make_resolver(tmp_path).resolve("10.9999/does-not-exist")
    assert not res.found
    assert "no Crossref or DataCite record" in res.unresolved


@responses.activate
def test_isbn_uses_open_library_with_author_names(tmp_path: Path) -> None:
    responses.get(
        f"{sources.OPEN_LIBRARY}/9780387220734.json",
        json={
            "title": "Statistical and Computational Inverse Problems",
            "publishers": ["Springer"],
            "publish_date": "2005",
            "authors": [{"key": "/authors/OL1A"}, {"key": "/authors/OL2A"}],
        },
    )
    responses.get("https://openlibrary.org/authors/OL1A.json", json={"name": "Jari Kaipio"})
    responses.get("https://openlibrary.org/authors/OL2A.json", json={"name": "E. Somersalo"})
    res = make_resolver(tmp_path).resolve("0387220739")
    assert res.found
    assert [a.family for a in res.citation["authors"].value] == ["Kaipio", "Somersalo"]
    assert res.citation["year"].value == 2005


def test_resolution_serializes(tmp_path: Path) -> None:
    from math_aware_source_digest.resolve import Provenance, Resolution

    res = Resolution(query="x")
    res.set_citation("title", "T", Provenance("crossref", "u"))
    data = json.loads(json.dumps(res.to_json()))
    assert data["citation"]["title"]["provenance"]["source"] == "crossref"
    assert data["found"] is True


# Zotero


def test_zotero_client_refuses_remote_hosts() -> None:
    with pytest.raises(ZoteroError, match="this machine"):
        LocalZotero("http://zotero.example.org:23119/api")
    LocalZotero("http://localhost:23119/api")
    LocalZotero("http://[::1]:23119/api")


@responses.activate
def test_zotero_item_gives_doi_and_pdf_path_then_crossref(tmp_path: Path) -> None:
    base = "http://127.0.0.1:23119/api/users/0/items"
    responses.get(
        f"{base}/YCVGJZLT",
        json={
            "data": {
                "key": "YCVGJZLT",
                "itemType": "journalArticle",
                "title": "Optimization...",
                "DOI": SEEGER,
            }
        },
    )
    responses.get(
        f"{base}/YCVGJZLT/children",
        json=[
            {
                "data": {"itemType": "attachment", "contentType": "application/pdf"},
                "links": {
                    "enclosure": {"href": "file:///Users/u/Zotero/storage/ABC/Seeger%202010.pdf"}
                },
            },
            {"data": {"itemType": "note"}},
        ],
    )
    responses.post(
        "http://127.0.0.1:23119/better-bibtex/json-rpc",
        json={"result": {"1:YCVGJZLT": "seeger2010optimization"}},
    )
    mock_seeger()
    res = make_resolver(tmp_path, zotero=LocalZotero()).resolve("zotero:YCVGJZLT")
    assert res.found
    assert res.identifiers["citation_key"].value == "seeger2010optimization"
    assert res.citation["title"].provenance.source == "crossref"
    pdfs = [c for c in res.copies if c.provenance.source == "zotero"]
    assert pdfs[0].url == "file:///Users/u/Zotero/storage/ABC/Seeger%202010.pdf"
    # Read-only: GET to Zotero; the only POST is Better BibTeX's key lookup.
    urls = [(c.request.method, str(c.request.url)) for c in responses.calls]
    zotero = [(m, u) for m, u in urls if "127.0.0.1" in u and "better-bibtex" not in u]
    assert {m for m, _ in zotero} == {"GET"}


@responses.activate
def test_zotero_not_running_gives_a_clear_message(tmp_path: Path) -> None:
    responses.get(re.compile(r"http://127\.0\.0\.1:23119/"), body=requests.ConnectionError())
    res = make_resolver(tmp_path, zotero=LocalZotero()).resolve("zotero:ABCDEFGH")
    assert not res.found
    assert "Allow other applications" in res.unresolved


@responses.activate
def test_zotero_with_the_local_api_off_says_how_to_turn_it_on(tmp_path: Path) -> None:
    responses.get(
        re.compile(r"http://127\.0\.0\.1:23119/"), status=403, body="Local API is not enabled"
    )
    res = make_resolver(tmp_path, zotero=LocalZotero()).resolve("zotero:ABCDEFGH")
    assert not res.found
    assert "local API is off" in res.unresolved
    assert "Allow other applications" in res.unresolved


@responses.activate
def test_arxiv_paper_records_the_journal_doi_separately(tmp_path: Path) -> None:
    responses.get(
        f"{sources.DATACITE}/10.48550/arxiv.1301.2831",
        json=fixture("datacite-arxiv-1301.2831.json"),
    )
    responses.post(
        re.compile(re.escape(sources.SEMANTIC_SCHOLAR)),
        json=[
            {
                "title": "Beyond consistent reconstructions: optimality and sharp bounds for "
                "generalized sampling, and application to the uniform resampling problem",
                "externalIds": {"DOI": "10.1137/120895846", "ArXiv": "1301.2831"},
            }
        ],
    )
    res = make_resolver(tmp_path).resolve("1301.2831")
    assert res.identifiers["doi"].value == "10.48550/arxiv.1301.2831"
    assert res.identifiers["published_doi"].value == "10.1137/120895846"
    assert not any("kept the first" in w for w in res.warnings)
