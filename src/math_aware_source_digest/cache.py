"""The cache: one directory for each source, under the cache root.

    <cache root>/sources/<slug>-<hash>/
        files/<sha256>.<ext>    downloads and other inputs, named by content
        stages/<stage>/         the output of each stage
        manifest.json           for each stage: its fingerprint and outputs

A stage is skipped when its fingerprint (the hashes of its inputs, its
settings, and the versions of its tools and models) is the same as in the
manifest and its outputs still exist. A small runner was preferred to a
workflow tool (Snakemake, doit): the stages are few, their inputs include
model answers rather than only files, and the manifest doubles as the
verification record's list of tools and versions.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .config import check_cache_root


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint(value: Any) -> str:
    """A stable hash of JSON-like settings."""
    return sha256_bytes(json.dumps(value, sort_keys=True, default=str).encode())


def source_slug(key: str) -> str:
    """A directory name for a source key such as ``doi:10.1002/mrm.22180``."""
    readable = re.sub(r"[^a-z0-9]+", "-", key.lower()).strip("-")[:60]
    return f"{readable}-{sha256_bytes(key.encode())[:10]}"


class SourceCache:
    def __init__(self, root: Path, key: str) -> None:
        check_cache_root(root)
        self.key = key
        self.dir = root / "sources" / source_slug(key)
        self.files = self.dir / "files"
        self.stages = self.dir / "stages"
        self.manifest_path = self.dir / "manifest.json"

    # Files

    def store_bytes(self, data: bytes, ext: str) -> Path:
        """Store content once, named by its hash; return its path."""
        self.files.mkdir(parents=True, exist_ok=True)
        path = self.files / f"{sha256_bytes(data)}.{ext.lstrip('.')}"
        if not path.exists():
            with tempfile.NamedTemporaryFile(dir=self.files, delete=False) as tmp:
                tmp.write(data)
            Path(tmp.name).replace(path)
        return path

    def store_file(self, source: Path, ext: str | None = None) -> Path:
        """Copy a file (for example a PDF from the user's library) into the cache."""
        self.files.mkdir(parents=True, exist_ok=True)
        path = self.files / f"{sha256_file(source)}.{(ext or source.suffix).lstrip('.')}"
        if not path.exists():
            shutil.copyfile(source, path)
        return path

    # Manifest and stages

    def manifest(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            return {"key": self.key, "stages": {}}
        data: dict[str, Any] = json.loads(self.manifest_path.read_text())
        return data

    def _write_manifest(self, data: dict[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.manifest_path.with_suffix(".part")
        tmp.write_text(json.dumps(data, indent=1, sort_keys=True, default=str))
        tmp.replace(self.manifest_path)

    def stage_dir(self, name: str) -> Path:
        return self.stages / name

    def run_stage(
        self,
        name: str,
        inputs: dict[str, Any],
        work: Callable[[Path], dict[str, Any]],
        force: bool = False,
    ) -> dict[str, Any]:
        """Run ``work(stage_dir)`` unless an identical run is recorded.

        ``inputs`` holds everything the result depends on (file hashes,
        settings, tool and model versions). ``work`` returns the stage's
        result as JSON-like data; paths in it, relative to the stage
        directory, are listed under the key ``outputs``.
        """
        manifest = self.manifest()
        record = manifest["stages"].get(name)
        print_ = fingerprint(inputs)
        out_dir = self.stage_dir(name)
        if (
            not force
            and record is not None
            and record.get("fingerprint") == print_
            and all((out_dir / p).exists() for p in record["result"].get("outputs", []))
        ):
            result: dict[str, Any] = record["result"]
            return result

        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True)
        started = time.time()
        result = work(out_dir)
        manifest = self.manifest()  # another stage may have written in the meantime
        manifest["stages"][name] = {
            "fingerprint": print_,
            "inputs": inputs,
            "result": result,
            "seconds": round(time.time() - started, 3),
            "finished": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        self._write_manifest(manifest)
        return result
