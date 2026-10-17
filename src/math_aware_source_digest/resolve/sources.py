"""Clients for the bibliographic services. Each reads one record into a Resolution.

All requests go through :class:`~math_aware_source_digest.net.Fetcher`, so the
download policy, the spacing per host and the cache apply. The services'
Python libraries (habanero, pyalex) make their own requests and would bypass
them; these clients call the REST APIs directly.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from ..net import Fetcher, NetError
from .match import clean_title, same_work
from .model import Author, Copy, Provenance, Resolution, Update, Version

CROSSREF = "https://api.crossref.org/works"
DATACITE = "https://api.datacite.org/dois"
OPENALEX = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR = "https://api.semanticscholar.org/graph/v1/paper/batch"
UNPAYWALL = "https://api.unpaywall.org/v2"
EUROPE_PMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
OPEN_LIBRARY = "https://openlibrary.org/isbn"
TOOL = "math-aware-source-digest"

_ARXIV_IN_URL = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:v\d+)?(?:\.pdf)?(?:[?#]|$)")


def _not_found(ex: NetError) -> bool:
    return "HTTP 404" in str(ex)


def _date_parts(record: dict[str, Any], key: str) -> list[int] | None:
    parts = (record.get(key) or {}).get("date-parts") or [[]]
    first = parts[0] if parts else []
    return [int(p) for p in first if p is not None] or None


# Crossref


def crossref_year(record: dict[str, Any]) -> tuple[int | None, str]:
    """The year of the printed issue when there is one, else of the first publication."""
    for key in ("published-print", "issued", "published-online", "published"):
        parts = _date_parts(record, key)
        if parts:
            return parts[0], key
    return None, ""


def read_crossref(res: Resolution, record: dict[str, Any], url: str) -> None:
    prov = Provenance("crossref", url)
    titles = record.get("title") or []
    res.set_citation("title", clean_title(titles[0]) if titles else "", prov)
    subtitle = record.get("subtitle") or []
    res.set_citation("subtitle", clean_title(subtitle[0]) if subtitle else "", prov)
    authors = [
        Author(a.get("family") or a.get("name") or "", a.get("given") or "")
        for a in record.get("author") or []
    ]
    res.set_citation("authors", authors, prov)
    editors = [
        Author(a.get("family") or "", a.get("given") or "") for a in record.get("editor") or []
    ]
    res.set_citation("editors", editors, prov)
    year, which = crossref_year(record)
    res.set_citation("year", year, Provenance("crossref", url, which))
    containers = record.get("container-title") or []
    res.set_citation("container", containers[0] if containers else "", prov)
    for name in ("volume", "issue", "page", "publisher", "type", "edition-number"):
        res.set_citation(name.replace("-number", ""), record.get(name), prov)
    res.set_citation("isbn", record.get("ISBN"), prov)
    res.set_identifier("doi", (record.get("DOI") or "").lower(), prov)
    for relation in record.get("updated-by") or []:
        res.updates.append(
            Update(
                doi=(relation.get("DOI") or "").lower(),
                type=relation.get("type") or "",
                label=relation.get("label") or "",
                date="-".join(str(p) for p in _date_parts(relation, "updated") or []),
                provenance=Provenance(
                    "crossref", url, f"updated-by ({relation.get('source', '')})"
                ),
            )
        )
    for relation in record.get("update-to") or []:
        res.warnings.append(
            f"this record is itself a {relation.get('type', 'notice')} "
            f"about {relation.get('DOI', '?')}"
        )


def crossref_work(fetcher: Fetcher, res: Resolution, doi: str) -> bool:
    url = f"{CROSSREF}/{quote(doi, safe='/')}"
    try:
        record = fetcher.get(url).json()["message"]
    except NetError as ex:
        if _not_found(ex):
            return False
        raise
    read_crossref(res, record, url)
    return True


def crossref_search(
    fetcher: Fetcher, title: str, surname: str = "", year: int | None = None, rows: int = 5
) -> tuple[str | None, str]:
    """Return (DOI, request URL) of the record that matches, or (None, URL)."""
    query = " ".join(p for p in (title, surname, str(year or "")) if p)
    params = {
        "query.bibliographic": query,
        "rows": str(rows),
        "select": "DOI,title,author,issued,published-print",
    }
    response = fetcher.get(CROSSREF, params=params)
    for item in response.json()["message"].get("items") or []:
        titles = item.get("title") or [""]
        first: dict[str, Any] = next(iter(item.get("author") or []), {})
        candidate_year, _ = crossref_year(item)
        if same_work(title, titles[0], surname, first.get("family", ""), year, candidate_year):
            return (item.get("DOI") or "").lower(), response.url
    return None, response.url


# DataCite (arXiv DOIs)


def datacite_work(fetcher: Fetcher, res: Resolution, doi: str) -> bool:
    url = f"{DATACITE}/{quote(doi, safe='/')}"
    try:
        attrs = fetcher.get(url).json()["data"]["attributes"]
    except NetError as ex:
        if _not_found(ex):
            return False
        raise
    prov = Provenance("datacite", url)
    titles = attrs.get("titles") or []
    res.set_citation("title", clean_title(titles[0]["title"]) if titles else "", prov)
    authors = [
        Author(c.get("familyName") or c.get("name") or "", c.get("givenName") or "")
        for c in attrs.get("creators") or []
    ]
    res.set_citation("authors", authors, prov)
    res.set_citation(
        "year", attrs.get("publicationYear"), Provenance("datacite", url, "publicationYear")
    )
    res.set_citation("publisher", attrs.get("publisher"), prov)
    res.set_citation("type", (attrs.get("types") or {}).get("resourceTypeGeneral"), prov)
    res.set_identifier("doi", (attrs.get("doi") or "").lower(), prov)
    return True


# OpenAlex


def read_openalex(res: Resolution, work: dict[str, Any], url: str) -> None:
    prov = Provenance("openalex", url)
    title = res.citation.get("title")
    if title and work.get("title") and not same_work(title.value, work["title"]):
        res.warnings.append(f"OpenAlex record has a different title: {work['title']!r}; ignored")
        return
    ids = work.get("ids") or {}
    if ids.get("pmcid"):
        res.set_identifier("pmcid", "PMC" + ids["pmcid"].rstrip("/").split("PMC")[-1], prov)
    if ids.get("pmid"):
        res.set_identifier("pmid", ids["pmid"].rstrip("/").rsplit("/", 1)[-1], prov)
    res.set_identifier("openalex", (work.get("id") or "").rsplit("/", 1)[-1], prov)
    for loc in work.get("locations") or []:
        for link in (loc.get("landing_page_url") or "", loc.get("pdf_url") or ""):
            match = _ARXIV_IN_URL.search(link)
            if match:
                res.set_identifier("arxiv", match.group(1), prov)
        version: Version | None = None
        raw_version = loc.get("version")
        if raw_version in ("submittedVersion", "acceptedVersion", "publishedVersion"):
            version = raw_version.removesuffix("Version")
        if loc.get("pdf_url"):
            res.add_copy(Copy(loc["pdf_url"], "pdf", version, loc.get("license"), prov))


def openalex_work(fetcher: Fetcher, res: Resolution, doi: str) -> bool:
    url = f"{OPENALEX}/doi:{quote(doi, safe='/')}"
    try:
        work = fetcher.get(url).json()
    except NetError as ex:
        if _not_found(ex):
            return False
        raise
    read_openalex(res, work, url)
    return True


# Semantic Scholar (batch)


def semantic_scholar_batch(
    fetcher: Fetcher, ids: list[str]
) -> tuple[list[dict[str, Any] | None], str]:
    """Look up to 500 IDs ("DOI:...", "ARXIV:...") in one request."""
    if len(ids) > 500:
        raise ValueError("Semantic Scholar takes at most 500 IDs per batch")
    url = f"{SEMANTIC_SCHOLAR}?fields=title,externalIds,year"
    response = fetcher.post_json(url, {"ids": ids})
    return response.json(), url


def read_semantic_scholar(res: Resolution, paper: dict[str, Any] | None, url: str) -> None:
    if not paper:
        return
    title = res.citation.get("title")
    if title and paper.get("title") and not same_work(title.value, paper["title"]):
        res.warnings.append(
            f"Semantic Scholar record has a different title: {paper['title']!r}; ignored"
        )
        return
    prov = Provenance("semanticscholar", url)
    ext = paper.get("externalIds") or {}
    res.set_identifier("arxiv", ext.get("ArXiv"), prov)
    if ext.get("PubMedCentral"):
        res.set_identifier("pmcid", "PMC" + str(ext["PubMedCentral"]).removeprefix("PMC"), prov)
    res.set_identifier("pmid", ext.get("PubMed"), prov)
    doi = str(ext.get("DOI") or "").lower()
    current = res.identifiers.get("doi")
    if doi and current and str(current.value).startswith("10.48550/") and doi != current.value:
        # The input was an arXiv paper; this DOI names its version of record.
        res.set_identifier("published_doi", doi, prov)
    elif doi:
        res.set_identifier("doi", doi, prov)


# Unpaywall (needs a contact email; skipped without one)


def unpaywall(fetcher: Fetcher, res: Resolution, doi: str) -> bool:
    email = fetcher.config.network.contact_email
    if not email:
        res.warnings.append(
            "Unpaywall skipped: it needs network.contact_email in the configuration"
        )
        return False
    url = f"{UNPAYWALL}/{quote(doi, safe='/')}"
    try:
        record = fetcher.get(url, params={"email": email}).json()
    except NetError as ex:
        if _not_found(ex):
            return False
        raise
    prov = Provenance("unpaywall", url)
    for loc in record.get("oa_locations") or []:
        version: Version | None = None
        raw = loc.get("version")
        if raw in ("submittedVersion", "acceptedVersion", "publishedVersion"):
            version = raw.removesuffix("Version")
        link = loc.get("url_for_pdf") or loc.get("url")
        if link:
            form = "pdf" if loc.get("url_for_pdf") else "landing-page"
            res.add_copy(Copy(link, form, version, loc.get("license"), prov))
    return True


# Europe PMC (PMID, PMCID and DOI of an article). The NCBI ID converter at
# pmc.ncbi.nlm.nih.gov refuses the requests library (HTTP 403, 2026-10-17).


def europe_pmc_ids(fetcher: Fetcher, res: Resolution, query: str) -> bool:
    """Look up "DOI:...", "PMCID:PMC..." or "EXT_ID:<pmid>" and read the identifiers."""
    params = {"query": query, "format": "json", "resultType": "lite"}
    response = fetcher.get(EUROPE_PMC, params=params)
    prov = Provenance("europepmc", response.url)
    results = (response.json().get("resultList") or {}).get("result") or []
    if len(results) != 1:
        if len(results) > 1:
            res.warnings.append(f"Europe PMC: {len(results)} records for {query}; none used")
        return False
    record = results[0]
    res.set_identifier("pmcid", record.get("pmcid"), prov)
    res.set_identifier("pmid", record.get("pmid"), prov)
    res.set_identifier("doi", (record.get("doi") or "").lower(), prov)
    return True


# Open Library (books)


def open_library_isbn(fetcher: Fetcher, res: Resolution, isbn: str) -> bool:
    url = f"{OPEN_LIBRARY}/{isbn}.json"
    try:
        edition = fetcher.get(url).json()
    except NetError as ex:
        if _not_found(ex):
            return False
        raise
    prov = Provenance("openlibrary", url)
    res.set_citation("title", clean_title(edition.get("title") or ""), prov)
    res.set_citation("subtitle", edition.get("subtitle"), prov)
    res.set_citation("publisher", ", ".join(edition.get("publishers") or []), prov)
    res.set_citation("edition", edition.get("edition_name"), prov)
    match = re.search(r"\b(1[5-9]\d\d|20\d\d)\b", edition.get("publish_date") or "")
    res.set_citation(
        "year",
        int(match.group(1)) if match else None,
        Provenance("openlibrary", url, "publish_date"),
    )
    res.set_citation("isbn", [isbn], prov)
    res.set_citation("type", "book", prov)
    authors = []
    for ref in edition.get("authors") or []:
        key = ref.get("key", "")
        if not re.fullmatch(r"/authors/OL\d+A", key):
            continue
        author_url = f"https://openlibrary.org{key}.json"
        name = " ".join((fetcher.get(author_url).json().get("name") or "").split())
        if name:
            *given, family = name.split(" ")
            authors.append(Author(family, " ".join(given)))
    res.set_citation("authors", authors, prov)
    if not authors:
        res.warnings.append("Open Library edition has no authors; give them or use another record")
    return True
