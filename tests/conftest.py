"""Shared fixtures. No test may open a network connection, except to this machine."""

from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


class NetworkBlocked(RuntimeError):
    pass


LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _is_loopback(address: Any) -> bool:
    return isinstance(address, tuple) and bool(address) and address[0] in LOOPBACK


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse every connection except to this machine (local servers under test)."""
    real_connect = socket.socket.connect
    real_create = socket.create_connection

    def connect(self: socket.socket, address: Any) -> None:
        if self.family == socket.AF_UNIX or _is_loopback(address):
            return real_connect(self, address)
        raise NetworkBlocked(f"tests must not open network connections ({address})")

    def create_connection(address: Any, *args: Any, **kwargs: Any) -> socket.socket:
        if _is_loopback(address):
            return real_create(address, *args, **kwargs)
        raise NetworkBlocked(f"tests must not open network connections ({address})")

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "create_connection", create_connection)


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep the user's real configuration and cache out of every test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    yield
