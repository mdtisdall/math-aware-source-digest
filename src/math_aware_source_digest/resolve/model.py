"""What the resolver returns. Every value carries the record that it came from."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Version = Literal["submitted", "accepted", "published"]


@dataclass(frozen=True)
class Provenance:
    source: str  # "crossref", "datacite", "openalex", "semanticscholar", "unpaywall", ...
    url: str  # the request that gave the value
    detail: str = ""  # for example which date field a year came from


@dataclass(frozen=True)
class Value:
    value: Any
    provenance: Provenance


@dataclass(frozen=True)
class Author:
    family: str
    given: str = ""


@dataclass(frozen=True)
class Copy:
    """A place where a version of the work can be acquired."""

    url: str
    form: str  # "arxiv-source", "pmc-xml", "pdf", "landing-page"
    version: Version | None
    licence: str | None
    provenance: Provenance


@dataclass(frozen=True)
class Update:
    """A correction, erratum, retraction or other notice about the work."""

    doi: str
    type: str
    label: str
    date: str
    provenance: Provenance


@dataclass
class Resolution:
    query: str
    citation: dict[str, Value] = field(default_factory=dict)
    identifiers: dict[str, Value] = field(default_factory=dict)  # doi, arxiv, pmcid, pmid, ...
    copies: list[Copy] = field(default_factory=list)
    updates: list[Update] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unresolved: str = ""  # the reason, when no record was found

    @property
    def found(self) -> bool:
        return not self.unresolved

    def set_citation(self, name: str, value: Any, provenance: Provenance) -> None:
        """Keep the first value for a field; the primary record is read first."""
        if value in (None, "", [], ()):
            return
        self.citation.setdefault(name, Value(value, provenance))

    def set_identifier(self, name: str, value: Any, provenance: Provenance) -> None:
        if value in (None, ""):
            return
        existing = self.identifiers.get(name)
        if existing is None:
            self.identifiers[name] = Value(value, provenance)
        elif str(existing.value).lower() != str(value).lower():
            self.warnings.append(
                f"{name}: {provenance.source} gives {value}, "
                f"{existing.provenance.source} gave {existing.value}; kept the first"
            )

    def add_copy(self, copy: Copy) -> None:
        if all(c.url != copy.url for c in self.copies):
            self.copies.append(copy)

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["found"] = self.found
        return data
