"""A guarded client for a local Ollama server.

The guards come from failures seen during the design (plan section 2):

- **Instruct models only.** A "thinking" model spent its whole answer budget
  on hidden reasoning even with ``think: false``. A model is refused unless
  its name contains ``instruct`` or the configuration allows it by name, and
  an answer that is empty while the model "thought" is an error.
- **Context capped.** Without a cap, Qwen3-VL got a 262k context and took
  91 GB on a 64 GB machine. ``num_ctx`` is always sent, at most 32768.
- **Output capped and structured.** ``num_predict`` is always sent; the
  answer must be JSON that matches the request's schema. A length-capped or
  unparsable answer is reported as such (the prototype flagged one harmful
  error that way), never repaired by guessing.
- **This machine only.** The server address must be a loopback address.
"""

from __future__ import annotations

import base64
import ipaddress
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import jsonschema
import requests

DEFAULT_BASE = "http://127.0.0.1:11434"
MAX_NUM_CTX = 32768
DEFAULT_NUM_CTX = 16384
DEFAULT_NUM_PREDICT = 512
REQUEST_TIMEOUT_S = 600


class LocalModelError(Exception):
    pass


class ModelRefused(LocalModelError):
    """The model is not allowed (not an instruct model, and not allowed by name)."""


class BadAnswer(LocalModelError):
    """The answer was cut off, empty, or does not match the schema."""

    def __init__(self, message: str, kind: str, raw: str = "") -> None:
        super().__init__(message)
        self.kind = kind  # "length", "thinking", "unparsable", "schema"
        self.raw = raw


def is_loopback(url: str) -> bool:
    host = urlsplit(url).hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass
class Answer:
    data: dict[str, Any]
    seconds: float
    prompt_tokens: int
    output_tokens: int
    model: str


@dataclass
class OllamaClient:
    base: str = DEFAULT_BASE
    allowed_models: tuple[str, ...] = ()
    num_ctx: int = DEFAULT_NUM_CTX
    session: requests.Session = field(default_factory=requests.Session)
    timeout_s: float = REQUEST_TIMEOUT_S

    def __post_init__(self) -> None:
        if not is_loopback(self.base):
            raise LocalModelError(
                f"the local model server must be on this machine, not {self.base}"
            )
        if not 0 < self.num_ctx <= MAX_NUM_CTX:
            raise LocalModelError(f"num_ctx must be in 1..{MAX_NUM_CTX}, not {self.num_ctx}")

    def check_model(self, model: str) -> None:
        if model in self.allowed_models or "instruct" in model.lower():
            return
        raise ModelRefused(
            f"model {model!r} is refused: use an instruct model, or allow it by name "
            "(thinking models spend their answer budget on hidden reasoning)"
        )

    def chat_json(
        self,
        model: str,
        prompt: str,
        schema: dict[str, Any],
        images: list[Path] | None = None,
        num_predict: int = DEFAULT_NUM_PREDICT,
    ) -> Answer:
        self.check_model(model)
        message: dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            message["images"] = [base64.b64encode(p.read_bytes()).decode() for p in images]
        body = {
            "model": model,
            "messages": [message],
            "stream": False,
            "think": False,
            "format": schema,
            "options": {"temperature": 0, "num_ctx": self.num_ctx, "num_predict": num_predict},
        }
        started = time.monotonic()
        try:
            response = self.session.post(
                f"{self.base}/api/chat", json=body, timeout=self.timeout_s, allow_redirects=False
            )
        except requests.ConnectionError as ex:
            raise LocalModelError(f"the local model server at {self.base} does not answer") from ex
        except requests.Timeout as ex:
            raise LocalModelError(f"no answer within {self.timeout_s:.0f} s") from ex
        if response.status_code != 200:
            raise LocalModelError(f"HTTP {response.status_code}: {response.text[:300]}")
        reply = response.json()
        seconds = time.monotonic() - started
        message_out = reply.get("message") or {}
        content = (message_out.get("content") or "").strip()
        if not content and message_out.get("thinking"):
            raise BadAnswer("the model thought but gave no answer", "thinking")
        if reply.get("done_reason") == "length":
            raise BadAnswer(f"the answer reached num_predict={num_predict}", "length", content)
        try:
            data = json.loads(content)
        except json.JSONDecodeError as ex:
            raise BadAnswer("the answer is not JSON", "unparsable", content) from ex
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as ex:
            raise BadAnswer(
                f"the answer does not match the schema: {ex.message}", "schema", content
            ) from ex
        return Answer(
            data,
            seconds,
            int(reply.get("prompt_eval_count") or 0),
            int(reply.get("eval_count") or 0),
            model,
        )
