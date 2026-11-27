import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from logoskittens.llm import LLMError, complete


def test_import_does_not_require_a_key():
    # Importing the module already happened. Calling the grok path without a key
    # fails before any network request.
    previous = os.environ.get("XAI_API_KEY")
    os.environ["LLM_BACKEND"] = "grok"
    os.environ["XAI_API_KEY"] = ""
    try:
        with pytest.raises(LLMError, match="XAI_API_KEY"):
            complete("ping", system="pong")
    finally:
        if previous is None:
            os.environ.pop("XAI_API_KEY", None)
        else:
            os.environ["XAI_API_KEY"] = previous


def test_a_grok_call_is_logged_without_the_key(tmp_path, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            body = json.dumps(
                {
                    "choices": [{"message": {"content": "pong"}}],
                    "usage": {"prompt_tokens": 3, "completion_tokens": 1},
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("XAI_API_KEY", "secret-key-should-not-appear")
    monkeypatch.setenv("GROK_BASE_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv("GROK_MODEL", "grok-4.7")
    monkeypatch.setenv("LOGOSKITTENS_CALL_LOG", str(log_path))
    try:
        text, record = complete("ping", system="pong", backend="grok")
    finally:
        server.shutdown()
    assert text == "pong"
    assert record.model == "grok-4.7"
    log = log_path.read_text(encoding="utf-8")
    assert f"POST http://127.0.0.1:{port}/v1/chat/completions" in log
    assert "HTTP 200" in log
    assert "secret-key-should-not-appear" not in log


def test_configured_backend_writes_a_comparison_record(tmp_path, monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            captured["path"] = self.path
            captured["body"] = json.loads(self.rfile.read(length))
            body = json.dumps(
                {
                    "message": {"role": "assistant", "content": "pong"},
                    "prompt_eval_count": 4,
                    "eval_count": 1,
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    log_path = tmp_path / "compare.jsonl"
    captured: dict = {}
    monkeypatch.setenv("LLM_BACKEND", "local")
    monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.delenv("LLM_THINK", raising=False)
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("COMPARISON_LOG", str(log_path))
    try:
        text, record = complete("ping", system="reply pong")
    finally:
        server.shutdown()
    assert text == "pong"
    assert captured["path"] == "/api/chat"
    assert captured["body"]["think"] is False
    assert captured["body"]["format"] == "json"
    assert captured["body"]["options"]["num_ctx"] == 4096
    assert record.backend == "local"
    assert record.model == "test-model"
    assert record.prompt_tokens == 4
    written = json.loads(log_path.read_text().strip())
    assert written["completion_tokens"] == 1
    assert written["latency_ms"] >= 0


def test_think_level_is_sent_to_the_backend(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            captured["body"] = json.loads(self.rfile.read(length))
            if self.path.startswith("/api/chat"):
                payload = {"message": {"content": "pong"}}
            else:
                payload = {"choices": [{"message": {"content": "pong"}}], "usage": {}}
            body = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    captured: dict = {}
    try:
        monkeypatch.setenv("LLM_BACKEND", "local")
        monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{port}/v1")
        monkeypatch.setenv("LLM_MODEL", "qwen3:8b")
        monkeypatch.setenv("LLM_THINK", "low")
        complete("ping", system="pong")
        assert captured["body"]["think"] == "low"
        monkeypatch.setenv("LLM_THINK", "on")
        complete("ping", system="pong")
        assert captured["body"]["think"] is True
        monkeypatch.setenv("XAI_API_KEY", "secret")
        monkeypatch.setenv("GROK_BASE_URL", f"http://127.0.0.1:{port}/v1")
        monkeypatch.setenv("LLM_THINK", "low")
        complete("ping", system="pong", backend="grok")
        assert captured["body"]["reasoning_effort"] == "low"
        assert "think" not in captured["body"]
    finally:
        server.shutdown()


def test_a_grok_off_switch_is_refused(monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "secret")
    monkeypatch.setenv("LLM_THINK", "off")
    with pytest.raises(LLMError, match="cannot turn reasoning off"):
        complete("ping", system="pong", backend="grok", base_url="http://127.0.0.1:9/v1", model="grok-4.7")
