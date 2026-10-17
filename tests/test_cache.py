from __future__ import annotations

import json
from pathlib import Path

import pytest

from math_aware_source_digest import cache, config


def test_store_bytes_is_content_addressed(tmp_path: Path) -> None:
    c = cache.SourceCache(tmp_path / "root", "doi:10.1002/mrm.22180")
    a = c.store_bytes(b"hello", "pdf")
    b = c.store_bytes(b"hello", "pdf")
    assert a == b and a.name == cache.sha256_bytes(b"hello") + ".pdf"
    assert c.dir.name.startswith("doi-10-1002-mrm-22180-")


def test_stage_is_skipped_when_inputs_are_unchanged(tmp_path: Path) -> None:
    c = cache.SourceCache(tmp_path / "root", "k")
    calls: list[int] = []

    def work(out: Path) -> dict[str, object]:
        calls.append(1)
        (out / "result.txt").write_text("done")
        return {"outputs": ["result.txt"], "value": 42}

    inputs = {"pdf": "abc", "dpi": 300, "tool": "pandoc 3.7"}
    assert c.run_stage("convert", inputs, work)["value"] == 42
    assert c.run_stage("convert", inputs, work)["value"] == 42
    assert len(calls) == 1
    c.run_stage("convert", {**inputs, "dpi": 288}, work)
    assert len(calls) == 2
    (c.stage_dir("convert") / "result.txt").unlink()
    c.run_stage("convert", {**inputs, "dpi": 288}, work)
    assert len(calls) == 3
    c.run_stage("convert", {**inputs, "dpi": 288}, work, force=True)
    assert len(calls) == 4
    manifest = json.loads(c.manifest_path.read_text())
    assert manifest["stages"]["convert"]["inputs"]["tool"] == "pandoc 3.7"


def test_cache_inside_a_repository_is_refused(tmp_path: Path) -> None:
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    with pytest.raises(config.ConfigError):
        cache.SourceCache(tmp_path / "repo" / "cache", "k")
