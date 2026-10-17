"""Safe unpacking of downloaded archives (arXiv sources).

A downloaded archive is untrusted. Members are extracted into a new, empty
directory, and an archive is refused (nothing is kept) if any member:

- has an absolute path, or a path that leaves the directory (``..``);
- is a link (symbolic or hard), a device, or a FIFO;
- makes the total size or the number of members exceed the limits (archive
  bombs).
"""

from __future__ import annotations

import gzip
import io
import shutil
import tarfile
from pathlib import Path, PurePosixPath

MAX_MEMBERS = 5000
MAX_TOTAL_BYTES = 500 * 1024 * 1024
MAX_GZIP_RATIO = 200


class UnsafeArchive(Exception):
    pass


def gunzip_limited(data: bytes, limit: int = MAX_TOTAL_BYTES) -> bytes:
    """Decompress gzip data, refusing output above ``limit`` bytes."""
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=io.BytesIO(data)) as f:
        while chunk := f.read(1 << 20):
            out.write(chunk)
            if out.tell() > limit or out.tell() > max(len(data), 1 << 20) * MAX_GZIP_RATIO:
                raise UnsafeArchive("decompressed size exceeds the limit")
    return out.getvalue()


def _check_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if path.is_absolute() or member.name.startswith(("/", "\\")):
        raise UnsafeArchive(f"absolute path in archive: {member.name}")
    if ".." in path.parts:
        raise UnsafeArchive(f"path leaves the directory: {member.name}")
    if member.issym() or member.islnk():
        raise UnsafeArchive(f"link in archive: {member.name}")
    if not (member.isfile() or member.isdir()):
        raise UnsafeArchive(f"special file in archive: {member.name}")


def extract_tar(data: bytes, dest: Path) -> list[Path]:
    """Extract a tar archive into ``dest``, which must not exist yet."""
    if dest.exists():
        raise UnsafeArchive(f"destination exists: {dest}")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        members = tar.getmembers()
        if len(members) > MAX_MEMBERS:
            raise UnsafeArchive(f"too many members: {len(members)}")
        total = 0
        for member in members:
            _check_member(member)
            total += member.size
            if total > MAX_TOTAL_BYTES:
                raise UnsafeArchive("total size exceeds the limit")
        dest.mkdir(parents=True)
        try:
            # The "data" filter also refuses what the checks above refuse.
            tar.extractall(dest, members=members, filter="data")
        except (tarfile.TarError, OSError) as ex:
            shutil.rmtree(dest, ignore_errors=True)
            raise UnsafeArchive(str(ex)) from ex
    return sorted(p for p in dest.rglob("*") if p.is_file())


def is_tar(data: bytes) -> bool:
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
            tar.next()
        return True
    except tarfile.TarError:
        return False
