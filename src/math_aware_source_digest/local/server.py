"""Start, watch and stop one local model server at a time.

During the design, Marker waited forever after its ``llama-server`` died at
start (an old build rejected ``--mmproj``). Here a server is started by the
tool, must answer its health check within a time limit, and is checked to be
alive before each use; if it exits, the caller gets :class:`ServerDied` with
the exit code and the end of its log, at once.

Only one server runs at a time (64 GB is not enough for two large models): a
lock file under the cache root holds the PID of the running server.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from collections.abc import Sequence
from pathlib import Path
from types import TracebackType

import requests

from .ollama import is_loopback

START_TIMEOUT_S = 180.0
POLL_S = 0.5
LOG_TAIL_BYTES = 2000

# Settings for `ollama serve` (plan section 3): a capped context, one request
# and one model at a time.
OLLAMA_ENV = {
    "OLLAMA_CONTEXT_LENGTH": "16384",
    "OLLAMA_NUM_PARALLEL": "1",
    "OLLAMA_MAX_LOADED_MODELS": "1",
}


class ServerError(Exception):
    pass


class ServerDied(ServerError):
    pass


class ServerBusy(ServerError):
    pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class ManagedServer:
    def __init__(
        self,
        name: str,
        command: Sequence[str],
        health_url: str,
        lock_dir: Path,
        log_path: Path,
        env: dict[str, str] | None = None,
        start_timeout_s: float = START_TIMEOUT_S,
    ) -> None:
        if not is_loopback(health_url):
            raise ServerError(f"the health URL must be on this machine: {health_url}")
        self.name = name
        self.command = list(command)
        self.health_url = health_url
        self.lock_path = lock_dir / "local-server.lock"
        self.log_path = log_path
        self.env = {**os.environ, **(env or {})}
        self.start_timeout_s = start_timeout_s
        self.process: subprocess.Popen[bytes] | None = None

    # Lock

    def _check_lock(self) -> None:
        """Refuse to start while another managed server is alive; remove a stale lock."""
        if not self.lock_path.exists():
            return
        text = self.lock_path.read_text().split()
        pid = int(text[0]) if text and text[0].isdigit() else 0
        if pid and _pid_alive(pid):
            other = text[1] if len(text) > 1 else "?"
            raise ServerBusy(
                f"another local server ({other}, PID {pid}) is running; "
                "stop it first (one server at a time)"
            )
        self.lock_path.unlink()

    def _take_lock(self) -> None:
        assert self.process is not None
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_path.write_text(f"{self.process.pid} {self.name}\n")

    def _release_lock(self) -> None:
        if self.process is not None and self.lock_path.exists():
            text = self.lock_path.read_text().split()
            if text and text[0] == str(self.process.pid):
                self.lock_path.unlink()

    # Life cycle

    def log_tail(self) -> str:
        if not self.log_path.exists():
            return ""
        data = self.log_path.read_bytes()[-LOG_TAIL_BYTES:]
        return data.decode(errors="replace")

    def check_alive(self) -> None:
        """Raise :class:`ServerDied` if the server process has exited."""
        if self.process is None:
            raise ServerDied(f"{self.name} was not started")
        code = self.process.poll()
        if code is not None:
            raise ServerDied(f"{self.name} exited with code {code}. Log:\n{self.log_tail()}")

    def healthy(self) -> bool:
        try:
            return requests.get(self.health_url, timeout=2).status_code == 200
        except requests.RequestException:
            return False

    def start(self) -> None:
        self._check_lock()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        log = self.log_path.open("wb")
        try:
            self.process = subprocess.Popen(
                self.command,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=self.env,
                start_new_session=True,
            )
        except FileNotFoundError as ex:
            raise ServerError(
                f"{self.command[0]} not found: start it from its nix shell "
                "(it is not in the default devShell)"
            ) from ex
        finally:
            log.close()
        self._take_lock()
        deadline = time.monotonic() + self.start_timeout_s
        while time.monotonic() < deadline:
            self.check_alive()
            if self.healthy():
                return
            time.sleep(POLL_S)
        self.stop()
        raise ServerError(
            f"{self.name} did not become healthy within "
            f"{self.start_timeout_s:.0f} s. Log:\n{self.log_tail()}"
        )

    def stop(self, grace_s: float = 10.0) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=grace_s)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        self._release_lock()

    def __enter__(self) -> ManagedServer:
        self.start()
        return self

    def __exit__(
        self, kind: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.stop()


def ollama_server(binary: str, port: int, lock_dir: Path, log_path: Path) -> ManagedServer:
    env = {**OLLAMA_ENV, "OLLAMA_HOST": f"127.0.0.1:{port}"}
    return ManagedServer(
        "ollama", [binary, "serve"], f"http://127.0.0.1:{port}/api/version", lock_dir, log_path, env
    )
