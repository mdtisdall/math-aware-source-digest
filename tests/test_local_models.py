from __future__ import annotations

import json
import os
import signal
import socket
import sys
import time
from pathlib import Path

import pytest
import responses

from math_aware_source_digest.local import ollama, server

URL = "http://127.0.0.1:11434/api/chat"
SCHEMA = {
    "type": "object",
    "properties": {"latex": {"type": "string"}},
    "required": ["latex"],
    "additionalProperties": False,
}
INSTRUCT = "qwen3-vl:32b-instruct"


def reply(content: str, done_reason: str = "stop", thinking: str = "") -> dict[str, object]:
    return {
        "message": {"role": "assistant", "content": content, "thinking": thinking},
        "done_reason": done_reason,
        "prompt_eval_count": 120,
        "eval_count": 9,
    }


# Client guards


def test_remote_server_is_refused() -> None:
    with pytest.raises(ollama.LocalModelError, match="this machine"):
        ollama.OllamaClient(base="http://gpu.example.org:11434")


def test_context_cap() -> None:
    with pytest.raises(ollama.LocalModelError, match="num_ctx"):
        ollama.OllamaClient(num_ctx=262144)


@responses.activate
def test_thinking_model_is_refused_without_a_request() -> None:
    with pytest.raises(ollama.ModelRefused, match="instruct"):
        ollama.OllamaClient().chat_json("qwen3-vl:32b", "x", SCHEMA)
    assert len(responses.calls) == 0


@responses.activate
def test_model_allowed_by_name() -> None:
    responses.post(URL, json=reply('{"latex": "x"}'))
    client = ollama.OllamaClient(allowed_models=("glm-ocr:0.9b",))
    assert client.chat_json("glm-ocr:0.9b", "x", SCHEMA).data == {"latex": "x"}


@responses.activate
def test_request_carries_the_guards(tmp_path: Path) -> None:
    image = tmp_path / "crop.png"
    image.write_bytes(b"\x89PNG fake")
    responses.post(URL, json=reply('{"latex": "\\\\gamma_k"}'))
    answer = ollama.OllamaClient().chat_json(
        INSTRUCT, "Transcribe", SCHEMA, [image], num_predict=300
    )
    body = json.loads(responses.calls[0].request.body or b"")
    assert body["think"] is False and body["stream"] is False
    assert body["format"] == SCHEMA
    assert body["options"] == {"temperature": 0, "num_ctx": 16384, "num_predict": 300}
    assert len(body["messages"][0]["images"]) == 1
    assert answer.data == {"latex": "\\gamma_k"}
    assert (answer.prompt_tokens, answer.output_tokens) == (120, 9)


@pytest.mark.parametrize(
    "content, done_reason, thinking, kind",
    [
        ('{"latex": "\\\\frac{a}{', "length", "", "length"),
        ("", "stop", "Let me think about this carefully...", "thinking"),
        ("The equation is x = 1", "stop", "", "unparsable"),
        ('{"tex": "x"}', "stop", "", "schema"),
    ],
)
@responses.activate
def test_bad_answers_are_reported_not_repaired(
    content: str, done_reason: str, thinking: str, kind: str
) -> None:
    responses.post(URL, json=reply(content, done_reason, thinking))
    with pytest.raises(ollama.BadAnswer) as info:
        ollama.OllamaClient().chat_json(INSTRUCT, "x", SCHEMA)
    assert info.value.kind == kind


def test_server_not_running() -> None:
    port = free_port()
    client = ollama.OllamaClient(base=f"http://127.0.0.1:{port}", timeout_s=2)
    with pytest.raises(ollama.LocalModelError, match="does not answer"):
        client.chat_json(INSTRUCT, "x", SCHEMA)


# Server supervision (real processes on this machine)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port: int = s.getsockname()[1]
        return port


def http_server(tmp_path: Path, name: str = "test", timeout: float = 20) -> server.ManagedServer:
    port = free_port()
    return server.ManagedServer(
        name,
        [
            sys.executable,
            "-m",
            "http.server",
            str(port),
            "--bind",
            "127.0.0.1",
            "--directory",
            str(tmp_path),
        ],
        f"http://127.0.0.1:{port}/",
        tmp_path / "locks",
        tmp_path / f"{name}.log",
        start_timeout_s=timeout,
    )


def test_server_starts_and_stops(tmp_path: Path) -> None:
    with http_server(tmp_path) as srv:
        assert srv.healthy()
        srv.check_alive()
        assert (tmp_path / "locks" / "local-server.lock").exists()
    assert not (tmp_path / "locks" / "local-server.lock").exists()


def test_server_that_dies_is_detected_at_once(tmp_path: Path) -> None:
    with http_server(tmp_path) as srv:
        assert srv.process is not None
        os.killpg(srv.process.pid, signal.SIGKILL)
        srv.process.wait()
        with pytest.raises(server.ServerDied, match="exited with code"):
            srv.check_alive()


def test_server_that_exits_at_start(tmp_path: Path) -> None:
    # Like llama-server rejecting --mmproj: exits at once; no waiting forever.
    srv = server.ManagedServer(
        "bad",
        [sys.executable, "-c", "import sys; print('error: unknown option --mmproj'); sys.exit(1)"],
        f"http://127.0.0.1:{free_port()}/",
        tmp_path / "locks",
        tmp_path / "bad.log",
        start_timeout_s=60,
    )
    started = time.monotonic()
    with pytest.raises(server.ServerDied, match="--mmproj"):
        srv.start()
    assert time.monotonic() - started < 10
    srv.stop()


def test_server_that_never_gets_healthy(tmp_path: Path) -> None:
    srv = server.ManagedServer(
        "slow",
        [sys.executable, "-c", "import time; time.sleep(60)"],
        f"http://127.0.0.1:{free_port()}/",
        tmp_path / "locks",
        tmp_path / "slow.log",
        start_timeout_s=1.5,
    )
    with pytest.raises(server.ServerError, match="did not become healthy"):
        srv.start()
    assert srv.process is not None and srv.process.poll() is not None


def test_one_server_at_a_time(tmp_path: Path) -> None:
    with http_server(tmp_path, "first"):
        second = http_server(tmp_path, "second")
        with pytest.raises(server.ServerBusy, match="first"):
            second.start()
        assert second.process is None


def test_stale_lock_is_removed(tmp_path: Path) -> None:
    (tmp_path / "locks").mkdir()
    (tmp_path / "locks" / "local-server.lock").write_text("999999 old\n")
    with http_server(tmp_path) as srv:
        assert srv.healthy()


def test_missing_binary(tmp_path: Path) -> None:
    srv = server.ManagedServer(
        "x",
        ["/nonexistent/ollama", "serve"],
        "http://127.0.0.1:1/",
        tmp_path / "locks",
        tmp_path / "x.log",
    )
    with pytest.raises(server.ServerError, match="nix shell"):
        srv.start()


def test_ollama_server_settings(tmp_path: Path) -> None:
    srv = server.ollama_server("ollama", 11500, tmp_path, tmp_path / "o.log")
    assert srv.env["OLLAMA_CONTEXT_LENGTH"] == "16384"
    assert srv.env["OLLAMA_NUM_PARALLEL"] == "1"
    assert srv.env["OLLAMA_MAX_LOADED_MODELS"] == "1"
    assert srv.env["OLLAMA_HOST"] == "127.0.0.1:11500"
