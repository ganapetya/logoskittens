"""The recognizer language travels with the audio, and a pair may name the chat model."""

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx

from logoskittens.audio import AudioClient
from logoskittens.llm import complete


def test_transcribe_sends_the_language(monkeypatch):
    captured: dict = {}

    def fake_post(url, content, headers, timeout, params=None):
        del url, content, timeout
        captured["headers"] = headers
        captured["params"] = params

        class Response:
            status_code = 200
            text = ""

            def json(self):
                return {"text": "Hei"}

        return Response()

    monkeypatch.setattr(httpx, "post", fake_post)
    text = AudioClient("http://audio").transcribe(
        b"abc", "audio/wav", language="en", prompt="ferries, fjord"
    )
    assert text == "Hei"
    assert captured["headers"]["X-Stt-Language"] == "en"
    assert captured["params"]["prompt"] == "ferries, fjord"


def test_inference_body_names_the_language():
    spec = importlib.util.spec_from_file_location(
        "audio_server", Path("audio-engine/server.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    body = module._inference_body(b"RIFF", "en", "bound", "ferries, fjord")
    assert b'name="language"' in body
    assert b"\r\nen\r\n" in body
    assert b'name="prompt"' in body
    assert b"ferries, fjord" in body


def test_a_voice_id_keeps_its_speaker():
    spec = importlib.util.spec_from_file_location(
        "audio_server_voice", Path("audio-engine/server.py")
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._split_voice("no_NO-nvcc-medium@KON") == ("no_NO-nvcc-medium", "KON")
    assert module._split_voice("no_NO-talesyntese-medium") == ("no_NO-talesyntese-medium", None)
    assert module._speaker_id({"KON": 3, "MON": 6}, "KON") == 3
    assert module._speaker_id({"KON": 3}, "MSV") is None


def test_pair_model_and_context_cap(monkeypatch, tmp_path):
    captured: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            captured["body"] = json.loads(self.rfile.read(length))
            payload = json.dumps({"message": {"content": "ok"}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, _format, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    monkeypatch.delenv("LLM_THINK", raising=False)
    monkeypatch.setenv("LLM_BACKEND", "local")
    monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{port}/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")
    monkeypatch.setenv("COMPARISON_LOG", str(tmp_path / "cmp.jsonl"))
    try:
        text, record = complete(
            "ping",
            system="pong",
            model="other:8b",
            num_ctx=9000,
        )
    finally:
        server.shutdown()
    assert text == "ok"
    assert captured["body"]["model"] == "other:8b"
    assert captured["body"]["think"] is False
    assert captured["body"]["options"]["num_ctx"] == 4096
    assert record.model == "other:8b"
