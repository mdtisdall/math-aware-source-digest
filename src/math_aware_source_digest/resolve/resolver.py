"""Stage 1: resolve inputs to records, identifiers and copies.

The primary record gives the citation: Crossref for a DOI, DataCite for an
arXiv identifier, Open Library for an ISBN. OpenAlex, Semantic Scholar, the
PMC ID converter and Unpaywall add identifiers (arXiv, PMC) and open copies;
their citation fields are never used in place of the primary record's. A
title is searched in Crossref, and a result counts only if it matches
(:mod:`.match`): a reference that does not exist resolves to nothing.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..net import Fetcher, NetError
from . import sources
from .ids import Identifier, parse
from .model import Copy, Provenance, Resolution
from .zotero import LocalZotero, ZoteroError


def _arxiv_copies(res: Resolution) -> None:
    arxiv = res.identifiers.get("arxiv")
    if arxiv:
        prov = Provenance("derived", "", f"from the arXiv identifier ({arxiv.provenance.source})")
        res.add_copy(
            Copy(
                f"https://arxiv.org/e-print/{arxiv.value}", "arxiv-source", "submitted", None, prov
            )
        )


def _pmc_copies(res: Resolution) -> None:
    pmcid = res.identifiers.get("pmcid")
    if pmcid:
        number = str(pmcid.value).removeprefix("PMC")
        url = (
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
            f"?db=pmc&id={number}&rettype=xml"
        )
        prov = Provenance("derived", "", f"from the PMC identifier ({pmcid.provenance.source})")
        res.add_copy(Copy(url, "pmc-xml", None, None, prov))


class Resolver:
    def __init__(self, fetcher: Fetcher, zotero: LocalZotero | None = None) -> None:
        self.fetcher = fetcher
        self.zotero = zotero

    def resolve_many(self, inputs: Sequence[str]) -> list[Resolution]:
        results = [self._primary(text) for text in inputs]
        self._semantic_scholar(results)
        for res in results:
            if res.found:
                self._secondary(res)
        return results

    def resolve(self, text: str) -> Resolution:
        return self.resolve_many([text])[0]

    # Primary records

    def _primary(self, text: str) -> Resolution:
        res = Resolution(query=text)
        try:
            ident = parse(text)
        except ValueError as ex:
            res.unresolved = str(ex)
            return res
        try:
            self._primary_for(res, ident)
        except NetError as ex:
            res.unresolved = f"lookup failed: {ex}"
        except ZoteroError as ex:
            res.unresolved = str(ex)
        return res

    def _primary_for(self, res: Resolution, ident: Identifier) -> None:
        f = self.fetcher
        given = Provenance("input", "", res.query)
        if ident.kind == "doi":
            res.set_identifier("doi", ident.value, given)
            if not sources.crossref_work(f, res, ident.value) and not sources.datacite_work(
                f, res, ident.value
            ):
                res.unresolved = f"no Crossref or DataCite record for DOI {ident.value}"
        elif ident.kind == "arxiv":
            res.set_identifier("arxiv", ident.value, given)
            if ident.version:
                res.warnings.append(
                    f"the input names version {ident.version}; "
                    "the record describes the identifier as a whole"
                )
            if not sources.datacite_work(f, res, f"10.48550/arxiv.{ident.value}"):
                res.unresolved = f"no DataCite record for arXiv:{ident.value}"
        elif ident.kind in ("pmcid", "pmid"):
            res.set_identifier(ident.kind, ident.value, given)
            query = f"PMCID:{ident.value}" if ident.kind == "pmcid" else f"EXT_ID:{ident.value}"
            sources.europe_pmc_ids(f, res, query)
            doi = res.identifiers.get("doi")
            if not doi or not sources.crossref_work(f, res, str(doi.value)):
                res.unresolved = f"no DOI record found for {ident}"
        elif ident.kind == "isbn":
            res.set_identifier("isbn", ident.value, given)
            if not sources.open_library_isbn(f, res, ident.value):
                res.unresolved = f"no Open Library record for ISBN {ident.value}"
        elif ident.kind == "zotero":
            self._from_zotero(res, ident.value)
        elif ident.kind == "title":
            found, url = sources.crossref_search(f, ident.value)
            if found is None:
                res.unresolved = "no record matched the title (it may not exist)"
            else:
                res.set_identifier("doi", found, Provenance("crossref", url, "title search"))
                sources.crossref_work(f, res, found)
        elif ident.kind == "pdf":
            res.unresolved = (
                "a PDF without an identifier: give its DOI, arXiv ID or title "
                "(title extraction from the PDF comes later)"
            )

    def _from_zotero(self, res: Resolution, key: str) -> None:
        if self.zotero is None:
            res.unresolved = "Zotero access is not configured"
            return
        item = self.zotero.item(key)
        prov = Provenance("zotero", f"zotero:{key}")
        res.set_identifier("zotero", key, prov)
        res.set_identifier("citation_key", item.citation_key, prov)
        for path in item.pdf_paths:
            res.add_copy(Copy(path.as_uri(), "pdf", None, None, prov))
        for text in (item.doi, item.isbn):
            if text:
                inner = parse(text)
                if inner.kind in ("doi", "isbn", "arxiv"):
                    self._primary_for(res, inner)
                    return
        if item.title:
            self._primary_for(res, Identifier("title", item.title))
        else:
            res.unresolved = f"Zotero item {key} has no DOI, ISBN or title"

    # Secondary records

    def _semantic_scholar(self, results: list[Resolution]) -> None:
        wanted: list[tuple[Resolution, str]] = []
        for res in results:
            if not res.found:
                continue
            doi = str(res.identifiers["doi"].value) if "doi" in res.identifiers else ""
            if doi and not doi.startswith("10.48550/"):
                wanted.append((res, f"DOI:{doi}"))
            elif "arxiv" in res.identifiers:
                wanted.append((res, f"ARXIV:{res.identifiers['arxiv'].value}"))
        for start in range(0, len(wanted), 500):
            chunk = wanted[start : start + 500]
            try:
                papers, url = sources.semantic_scholar_batch(self.fetcher, [w[1] for w in chunk])
            except NetError as ex:
                for res, _ in chunk:
                    res.warnings.append(f"Semantic Scholar skipped: {ex}")
                continue
            for (res, _), paper in zip(chunk, papers, strict=True):
                sources.read_semantic_scholar(res, paper, url)

    def _secondary(self, res: Resolution) -> None:
        f = self.fetcher
        doi = res.identifiers.get("doi")
        steps: list[tuple[str, Callable[[], bool]]] = []
        if doi and not str(doi.value).startswith("10.48550/"):
            d = str(doi.value)
            steps = [
                ("OpenAlex", lambda: sources.openalex_work(f, res, d)),
                ("Unpaywall", lambda: sources.unpaywall(f, res, d)),
            ]
            if "pmcid" not in res.identifiers:
                steps.append(("Europe PMC", lambda: sources.europe_pmc_ids(f, res, f"DOI:{d}")))
        for name, step in steps:
            try:
                step()
            except NetError as ex:
                res.warnings.append(f"{name} skipped: {ex}")
        _arxiv_copies(res)
        _pmc_copies(res)
