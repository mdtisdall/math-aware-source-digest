from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from jinja2.exceptions import SecurityError

from math_aware_source_digest import cli, entry

EXAMPLE = Path(__file__).parent / "fixtures" / "entry" / "example-2024.json"


def example() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(EXAMPLE.read_text())
    return data


# Keys


@pytest.mark.parametrize(
    "surnames, year, existing, key",
    [
        (["Seeger", "Nickisch", "Pohmann", "Schölkopf"], 2010, [], "seeger-2010"),
        (["Kaipio", "Somersalo"], 2007, [], "kaipio-somersalo-2007"),
        (["Unser"], 2000, [], "unser-2000"),
        (["Adcock", "Hansen", "Poon"], 2013, ["adcock-2013"], "adcock-2013a"),
        (["Adcock", "Hansen", "Poon"], 2013, ["adcock-2013", "adcock-2013a"], "adcock-2013b"),
        (["van der Vaart"], 1998, [], "van-der-vaart-1998"),
        (["Gödel"], None, [], "godel-nd"),
        ([], 1959, [], "anon-1959"),
    ],
)
def test_make_key(surnames: list[str], year: int | None, existing: list[str], key: str) -> None:
    assert entry.make_key(surnames, year, existing) == key


# Validation


def test_example_is_valid() -> None:
    assert not entry.validate(example())


def mutate(path: list[Any], value: Any) -> dict[str, Any]:
    data = copy.deepcopy(example())
    target = data
    for step in path[:-1]:
        target = target[step]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return data


@pytest.mark.parametrize(
    "path, value, message",
    [
        (["spans", 2, "reason"], KeyError, "'reason' is a required property"),
        (["citation", "page", "reason"], KeyError, "'reason' is a required property"),
        (["citation", "title"], KeyError, "'title' is a required property"),
        (["spans", 0, "status"], "probably fine", "is not one of"),
        (["spans", 0, "latex"], KeyError, "is not valid under any of the given schemas"),
        (["key"], "Seeger 2010", "does not match"),
        (["results", 0, "spans"], ["eq-3", "eq-99"], "unknown span eq-99"),
        (["results", 0, "statement"], "Then {{s:nope}}.", "unknown span nope"),
        (["notation", 0, "symbol"], "missing-symbol", "unknown span missing-symbol"),
        (["spans", 1, "id"], "eq-3", "duplicate id eq-3"),
        (["extra"], 1, "Additional properties"),
        (["results", 0, "location"], {}, "should be non-empty"),
    ],
)
def test_invalid_entries_are_refused(path: list[Any], value: Any, message: str) -> None:
    problems = entry.validate(mutate(path, value))
    assert problems
    assert any(message in e for e in problems.errors), problems.errors


def test_invalid_entry_is_not_written(tmp_path: Path) -> None:
    with pytest.raises(entry.EntryError, match="not written"):
        entry.write_entry(mutate(["spans", 2, "reason"], KeyError), tmp_path)
    assert list(tmp_path.iterdir()) == []


# Rendering


def test_render_default_template() -> None:
    md = entry.render(example())
    assert md.startswith("# Example, Ada (2024). A fictional paper on sampling")
    for heading in entry.HEADINGS.values():
        assert f"## {heading}" in md
    assert r"$\tilde{\varphi}$ [phi-tilde]" in md  # span references expanded
    # The LaTeX of each span is verbatim in a code block (a table would turn \| into |).
    eq3 = next(s for s in example()["spans"] if s["id"] == "eq-3")["latex"]
    assert f"```latex\n  {eq3}\n  ```" in md
    assert "- Licence: cc-by (unpaywall)" in md.splitlines()
    assert "unverified: the first page shows no page numbers" in md
    assert "**Erratum**: 10.0000/fictional-erratum" in md
    assert "Lemma 2 (lemma)" in md
    assert "Assumptions stated in the source:" in md
    assert "qwen3-vl:32b-instruct ollama 0.40.3 (adjudicator)" in md


def test_render_sections_and_headings_are_configurable() -> None:
    cfg = entry.RenderConfig(sections=("summary", "coverage"), headings={"coverage": "Omitted"})
    md = entry.render(example(), cfg)
    assert "## Summary" in md and "## Omitted" in md
    assert "## Citation" not in md and "## Results" not in md


def test_unknown_section_is_refused() -> None:
    with pytest.raises(entry.EntryError, match="unknown sections"):
        entry.render(example(), entry.RenderConfig(sections=("summary", "focus")))


def test_project_template(tmp_path: Path) -> None:
    template = tmp_path / "mine.md.j2"
    template.write_text("KEY={{ e.key }}\n{% include 'sections/summary.md.j2' %}")
    md = entry.render(example(), entry.RenderConfig(template=template))
    assert md.startswith("KEY=example-2024")
    assert "[phi-tilde]" in md


def test_template_sandbox_blocks_attribute_escape(tmp_path: Path) -> None:
    template = tmp_path / "evil.md.j2"
    template.write_text("{{ e.__class__.__mro__ }}")
    with pytest.raises(SecurityError, match="unsafe"):
        entry.render(example(), entry.RenderConfig(template=template))


# Writing and the index


def test_write_entry_and_index(tmp_path: Path) -> None:
    entry.write_entry(example(), tmp_path)
    second = example()
    second["key"] = "example-2024a"
    second["spans"] = [s for s in second["spans"] if s["id"] != "gamma"]
    second["notation"] = second["notation"][:1]
    second["summary"] = "Plain summary."
    second["results"][0]["assumptions"] = []
    entry.write_entry(second, tmp_path)
    index = entry.write_index(tmp_path).read_text()
    lines = [line for line in index.splitlines() if line.startswith("- [")]
    assert len(lines) == 2
    assert "Example (2024)" in lines[0]
    assert "spans: 0 exact, 2 verified, 1 unverified; citation unverified: page" in lines[0]
    assert "licence: cc-by" in lines[0]
    assert (tmp_path / "example-2024.md").read_text().startswith("# Example")


def test_cli_render_and_validate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "masd.toml").write_text('[output]\ndir = "refs"\nheadings = { spans = "Spans" }\n')
    (tmp_path / "refs").mkdir()
    (tmp_path / "refs" / "example-2024.json").write_text(EXAMPLE.read_text())
    monkeypatch.chdir(tmp_path)
    assert cli.main(["validate", "refs/example-2024.json"]) == 0
    assert cli.main(["render"]) == 0
    assert "## Spans" in (tmp_path / "refs" / "example-2024.md").read_text()
    assert (tmp_path / "refs" / "README.md").exists()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(mutate(["spans", 2, "reason"], KeyError)))
    assert cli.main(["validate", str(bad)]) == 1
    assert "required property" in capsys.readouterr().out
