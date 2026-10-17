"""Decide whether a search result is the work that was asked for.

Search services return their nearest records even for a reference that does
not exist, and OpenAlex has matched a wrong DOI before (a figshare copy). A
candidate counts only if its title is nearly the same, and its first author
and year agree when they are known.
"""

from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher

TITLE_THRESHOLD = 0.92


def fold(text: str) -> str:
    """Lower case, ASCII letters and digits only (markup, accents, punctuation removed)."""
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = unicodedata.normalize("NFKD", text)
    return re.sub(r"[^a-z0-9]", "", text.encode("ascii", "ignore").decode().lower())


def clean_title(text: str) -> str:
    """The title for display: markup removed, spaces normalized."""
    # An opening tag after a letter starts a word ("of<i>k</i>-space" -> "of k-space").
    text = re.sub(r"(?<=\w)<(?!/)[^>]+>", " ", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    return " ".join(text.split())


def title_similarity(a: str, b: str) -> float:
    fa, fb = fold(a), fold(b)
    if not fa or not fb:
        return 0.0
    return SequenceMatcher(None, fa, fb).ratio()


def same_work(
    title: str,
    candidate_title: str,
    surname: str = "",
    candidate_surname: str = "",
    year: int | None = None,
    candidate_year: int | None = None,
) -> bool:
    if title_similarity(title, candidate_title) < TITLE_THRESHOLD:
        return False
    if surname and candidate_surname and fold(surname) != fold(candidate_surname):
        return False
    # Online and print dates differ by up to a year.
    return not (year and candidate_year and abs(year - candidate_year) > 1)
