"""Training roles come from .env_training, not from the practice .env."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from logoskittens.sim.training_env import apply_sim_talk, complete_for, load_training, talk_label


def test_a_file_sets_the_two_roles_apart(tmp_path, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    (tmp_path / ".env_training").write_text(
        "\n".join(
            [
                "BACKEND_SIM_TALK=grok",
                "SIM_TALK_BASE_URL=https://talk.example/v1",
                "SIM_TALK_MODEL=grok-talk",
                "SIM_TALK_API_KEY=talk-key",
                "BACKEND_JUDGE_PROPOSER=local",
                "JUDGE_PROPOSER_BASE_URL=http://127.0.0.1:11434/v1",
                "JUDGE_PROPOSER_MODEL=qwen3:1.7b",
            ]
        ),
        encoding="utf-8",
    )
    models = load_training(tmp_path)
    assert models.sim_talk.backend == "grok"
    assert models.sim_talk.model == "grok-talk"
    assert models.sim_talk.api_key == "talk-key"
    assert models.judge.backend == "local"
    assert models.judge.model == "qwen3:1.7b"
    assert talk_label(tmp_path) == "grok model grok-talk"


def test_missing_file_keeps_the_previous_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "from-shell")
    models = load_training(tmp_path)
    assert models.sim_talk.backend == "local"
    assert models.sim_talk.model == "qwen3:8b"
    assert models.judge.backend == "grok"
    assert models.judge.model == "grok-4.7"
    assert models.judge.api_key == "from-shell"


def test_grok_without_a_key_is_refused(tmp_path, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    (tmp_path / ".env_training").write_text("BACKEND_JUDGE_PROPOSER=grok\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JUDGE_PROPOSER_API_KEY"):
        load_training(tmp_path)


def test_apply_points_the_process_at_the_simulated_talk(tmp_path, monkeypatch):
    import os

    monkeypatch.setenv("LLM_BACKEND", "grok")
    monkeypatch.setenv("LLM_MODEL", "practice-model")
    monkeypatch.setenv("XAI_API_KEY", "practice-key")
    (tmp_path / ".env_training").write_text(
        "BACKEND_SIM_TALK=local\nSIM_TALK_BASE_URL=http://127.0.0.1:11434/v1\nSIM_TALK_MODEL=qwen3:1.7b\n",
        encoding="utf-8",
    )
    apply_sim_talk(load_training(tmp_path).sim_talk)
    assert os.environ["LLM_BACKEND"] == "local"
    assert os.environ["LLM_MODEL"] == "qwen3:1.7b"
    assert os.environ["LLM_BASE_URL"] == "http://127.0.0.1:11434/v1"


def test_a_role_can_set_its_own_think_level(tmp_path, monkeypatch):
    import os

    monkeypatch.delenv("LLM_THINK", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "practice-key")
    (tmp_path / ".env_training").write_text(
        "BACKEND_SIM_TALK=local\nSIM_TALK_MODEL=qwen3:8b\nSIM_TALK_THINK=on\n",
        encoding="utf-8",
    )
    apply_sim_talk(load_training(tmp_path).sim_talk)
    assert os.environ["LLM_THINK"] == "on"


def test_the_judge_call_uses_its_own_key(monkeypatch):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            captured["auth"] = self.headers.get("Authorization")
            captured["body"] = json.loads(self.rfile.read(length))
            body = json.dumps({"choices": [{"message": {"content": "ok"}}], "usage": {}}).encode()
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
    monkeypatch.delenv("LLM_THINK", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "practice-key")
    monkeypatch.setenv("LLM_BACKEND", "local")
    monkeypatch.setenv("LLM_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("LLM_MODEL", "practice-model")
    from logoskittens.sim.training_env import Role

    role = Role("grok", f"http://127.0.0.1:{port}/v1", "grok-judge", "judge-key")
    try:
        text, record = complete_for(role)("ping", system="pong")
    finally:
        server.shutdown()
    assert text == "ok"
    assert captured["auth"] == "Bearer judge-key"
    assert captured["body"]["model"] == "grok-judge"
    assert record.backend == "grok"
