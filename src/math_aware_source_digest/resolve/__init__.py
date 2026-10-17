"""Stage 1: resolve DOIs, arXiv IDs, ISBNs, titles and Zotero items to records."""

from .ids import Identifier, parse
from .model import Author, Copy, Provenance, Resolution, Update, Value
from .resolver import Resolver

__all__ = [
    "Author",
    "Copy",
    "Identifier",
    "Provenance",
    "Resolution",
    "Resolver",
    "Update",
    "Value",
    "parse",
]
