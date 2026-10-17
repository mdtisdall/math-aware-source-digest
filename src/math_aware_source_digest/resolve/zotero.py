"""Read-only access to the user's Zotero library through Zotero's local API.

Zotero 7 serves its library at ``http://127.0.0.1:23119/api/`` when "Allow
other applications on this computer to communicate with Zotero" is on
(Settings > Advanced). This client only sends GET requests, and only to the
local machine; it never writes to the library. Better BibTeX, if installed,
gives the citation key.

The library is not a source of citation facts (those come from Crossref and
the other records); it gives identifiers (DOI, arXiv ID, ISBN) and the path of
the PDF.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import requests

LOCAL_API = "http://127.0.0.1:23119/api"
BETTER_BIBTEX = "http://127.0.0.1:23119/better-bibtex/json-rpc"


class ZoteroError(Exception):
    pass


@dataclass
class ZoteroItem:
    key: str
    item_type: str
    title: str
    doi: str = ""
    isbn: str = ""
    url: str = ""
    extra: str = ""
    pdf_paths: list[Path] = field(default_factory=list)
    citation_key: str = ""


def _is_loopback(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class LocalZotero:
    def __init__(
        self,
        base: str = LOCAL_API,
        session: requests.Session | None = None,
        timeout_s: float = 20.0,
    ) -> None:
        if not _is_loopback(base):
            raise ZoteroError(f"the Zotero local API must be on this machine, not {base}")
        self.base = base.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_s = timeout_s

    def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self.base}/{path.lstrip('/')}"
        try:
            response = self.session.get(
                url, params=params, timeout=self.timeout_s, allow_redirects=False
            )
        except requests.ConnectionError as ex:
            raise ZoteroError(
                "Zotero's local API does not answer: start Zotero 7 and turn on "
                "Settings > Advanced > 'Allow other applications on this computer to "
                "communicate with Zotero'"
            ) from ex
        if response.status_code != 200:
            raise ZoteroError(f"GET {url}: HTTP {response.status_code}")
        return response.json()

    def item(self, key: str) -> ZoteroItem:
        data = self._get(f"users/0/items/{key}", {"format": "json"})["data"]
        item = ZoteroItem(
            key=data["key"],
            item_type=data.get("itemType", ""),
            title=data.get("title", ""),
            doi=data.get("DOI", ""),
            isbn=data.get("ISBN", ""),
            url=data.get("url", ""),
            extra=data.get("extra", ""),
            citation_key=data.get("citationKey", ""),
        )
        for child in self._get(f"users/0/items/{key}/children", {"format": "json"}):
            path = self._attachment_path(child)
            if path is not None:
                item.pdf_paths.append(path)
        if not item.citation_key:
            item.citation_key = self.better_bibtex_key(key)
        return item

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        params = {"q": query, "limit": str(limit), "format": "json", "itemType": "-attachment"}
        return [entry["data"] for entry in self._get("users/0/items", params)]

    @staticmethod
    def _attachment_path(entry: dict[str, Any]) -> Path | None:
        data = entry.get("data") or {}
        if data.get("itemType") != "attachment" or data.get("contentType") != "application/pdf":
            return None
        href = ((entry.get("links") or {}).get("enclosure") or {}).get("href", "")
        if href.startswith("file://"):
            return Path(unquote(urlsplit(href).path))
        return None

    def better_bibtex_key(self, key: str) -> str:
        """The Better BibTeX citation key, or "" if Better BibTeX does not answer."""
        body = {"jsonrpc": "2.0", "method": "item.citationkey", "params": [[f"1:{key}"]]}
        try:
            response = self.session.post(
                BETTER_BIBTEX, json=body, timeout=self.timeout_s, allow_redirects=False
            )
            result = response.json().get("result") or {}
        except (requests.RequestException, ValueError):
            return ""
        return str(result.get(f"1:{key}") or "") if isinstance(result, dict) else ""
