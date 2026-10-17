from __future__ import annotations

from pathlib import Path

import pytest

from math_aware_source_digest import config


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_defaults_ask_for_every_download(tmp_path: Path) -> None:
    cfg = config.load(cwd=tmp_path)
    assert cfg.downloads.allowed_hosts == ()
    assert cfg.output.dir == "sources"
    assert cfg.network.host_intervals_s["arxiv.org"] == 3.0
    assert cfg.cache_root == tmp_path / "xdg-cache" / "math-aware-source-digest"


def test_project_file_found_in_parent_and_overrides_user_file(tmp_path: Path) -> None:
    user = write(
        tmp_path / "user.toml",
        '[downloads]\nallowed_hosts = ["crossref.org"]\n[output]\ndir = "refs"\n',
    )
    project = tmp_path / "project"
    write(project / "masd.toml", '[downloads]\nallowed_hosts = ["ArXiv.org."]\n')
    (project / "deep" / "er").mkdir(parents=True)
    cfg = config.load(cwd=project / "deep" / "er", user_file=user)
    assert cfg.downloads.allowed_hosts == ("arxiv.org",)
    assert cfg.output.dir == "refs"
    assert cfg.sources == (user, project / "masd.toml")


def test_host_intervals_merge(tmp_path: Path) -> None:
    write(tmp_path / "masd.toml", '[network]\nhost_intervals_s = {"api.crossref.org" = 2}\n')
    cfg = config.load(cwd=tmp_path)
    assert cfg.network.host_intervals_s == {"arxiv.org": 3.0, "api.crossref.org": 2.0}


@pytest.mark.parametrize(
    "text, message",
    [
        ("[output]\ndirr = 'x'\n", "unknown keys in [output]: dirr"),
        ("[downloads]\nallowed_hosts = 'arxiv.org'\n", "must be a list"),
        ("output = 3\n", "must be a table"),
        ("[nope]\n", "unknown keys in [top level]"),
        ("[output\n", "masd.toml"),
    ],
)
def test_invalid_files_are_refused(tmp_path: Path, text: str, message: str) -> None:
    write(tmp_path / "masd.toml", text)
    with pytest.raises(config.ConfigError, match=message.replace("[", r"\[")):
        config.load(cwd=tmp_path)


def test_cache_root_inside_a_repository_is_refused(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    write(repo / "masd.toml", f'[cache]\nroot = "{repo / "cache"}"\n')
    with pytest.raises(config.ConfigError, match="inside the git repository"):
        config.load(cwd=repo)
