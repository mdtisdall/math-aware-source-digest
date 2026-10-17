from __future__ import annotations

import json
from pathlib import Path

import pytest

from math_aware_source_digest import cli


def test_config_prints_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    assert cli.main(["config"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["downloads"]["allowed_hosts"] == []


def test_policy_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "masd.toml").write_text('[downloads]\nallowed_hosts = ["arxiv.org"]\n')
    monkeypatch.chdir(tmp_path)
    assert cli.main(["policy", "https://arxiv.org/e-print/1"]) == 0
    assert cli.main(["policy", "https://evil.org/x"]) == 1
    assert "needs approval" in capsys.readouterr().out


def test_configuration_error_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "masd.toml").write_text("[output\n")
    monkeypatch.chdir(tmp_path)
    assert cli.main(["config"]) == 2


def test_resolve_reports_unresolved_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)  # empty policy: every lookup needs approval
    assert cli.main(["resolve", "10.1002/mrm.22180"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out[0]["found"] is False
    assert "needs the user's approval" in out[0]["unresolved"]
