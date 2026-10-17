from __future__ import annotations

from math_aware_source_digest.resolve import match


def test_markup_and_dashes_do_not_matter() -> None:
    crossref = "Optimization of<i>k</i>\u2010space trajectories for compressed sensing"
    plain = "Optimization of k-space trajectories for compressed sensing"
    assert match.title_similarity(crossref, plain) == 1.0
    assert (
        match.clean_title(crossref)
        == "Optimization of k\u2010space trajectories for compressed sensing"
    )


def test_accents_fold() -> None:
    assert match.fold("Schölkopf") == match.fold("Scholkopf") == "scholkopf"


def test_same_work_rules() -> None:
    t = "Sampling—50 years after Shannon"
    assert match.same_work(t, "Sampling-50 years after Shannon", "Unser", "Unser", 2000, 2000)
    assert not match.same_work(t, "Sampling-50 years after Shannon", "Unser", "Shannon")
    assert not match.same_work(t, "Sampling-50 years after Shannon", year=2000, candidate_year=2005)
    assert match.same_work(t, "Sampling-50 years after Shannon", year=2000, candidate_year=2001)
    assert not match.same_work(t, "Sampling theory after Nyquist")
    assert not match.same_work("", "anything")


def test_clean_title_keeps_words_apart_only_where_needed() -> None:
    assert match.clean_title("<i>In vivo</i> imaging of T<sub>2</sub>") == "In vivo imaging of T 2"
    assert match.clean_title("A &amp; B") == "A & B"
