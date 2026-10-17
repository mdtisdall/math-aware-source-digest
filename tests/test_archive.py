from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

import pytest

from math_aware_source_digest import archive


def tar_of(members: list[tuple[tarfile.TarInfo, bytes]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for info, data in members:
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data) if data else None)
    return buf.getvalue()


def file_member(name: str, data: bytes = b"x") -> tuple[tarfile.TarInfo, bytes]:
    return tarfile.TarInfo(name), data


def test_normal_archive_extracts(tmp_path: Path) -> None:
    data = tar_of(
        [file_member("main.tex", b"\\documentclass{article}"), file_member("sec/intro.tex", b"hi")]
    )
    files = archive.extract_tar(data, tmp_path / "out")
    assert [p.relative_to(tmp_path / "out").as_posix() for p in files] == [
        "main.tex",
        "sec/intro.tex",
    ]


@pytest.mark.parametrize("name", ["../evil.tex", "a/../../evil.tex", "/etc/evil", "a/../../../x"])
def test_path_traversal_is_refused(tmp_path: Path, name: str) -> None:
    with pytest.raises(archive.UnsafeArchive):
        archive.extract_tar(tar_of([file_member(name)]), tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert not (tmp_path / "evil.tex").exists()


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE])
def test_links_are_refused(tmp_path: Path, kind: bytes) -> None:
    info = tarfile.TarInfo("link")
    info.type = kind
    info.linkname = "/etc/passwd"
    with pytest.raises(archive.UnsafeArchive, match="link"):
        archive.extract_tar(tar_of([(info, b"")]), tmp_path / "out")


def test_devices_are_refused(tmp_path: Path) -> None:
    info = tarfile.TarInfo("dev")
    info.type = tarfile.CHRTYPE
    with pytest.raises(archive.UnsafeArchive, match="special"):
        archive.extract_tar(tar_of([(info, b"")]), tmp_path / "out")


def test_too_many_members(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive, "MAX_MEMBERS", 3)
    data = tar_of([file_member(f"f{i}") for i in range(4)])
    with pytest.raises(archive.UnsafeArchive, match="too many"):
        archive.extract_tar(data, tmp_path / "out")


def test_gzip_bomb_is_refused() -> None:
    bomb = gzip.compress(b"\0" * (30 * 1024 * 1024))
    with pytest.raises(archive.UnsafeArchive, match="exceeds"):
        archive.gunzip_limited(bomb, limit=10 * 1024 * 1024)


def test_existing_destination_is_refused(tmp_path: Path) -> None:
    (tmp_path / "out").mkdir()
    with pytest.raises(archive.UnsafeArchive, match="exists"):
        archive.extract_tar(tar_of([file_member("a")]), tmp_path / "out")
