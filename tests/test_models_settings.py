"""OpenAI beside Grok, and the Settings page's Models tab: page beats .env, keys never come back."""

import json

import httpx
import pytest
from fakes import FakeAudio, fake_complete
from fastapi.testclient import TestClient

from logoskittens import models
from logoskittens.api import create_app
from logoskittens.llm import ComparisonRecord, complete
from logoskittens.persistence import Store
from logoskittens.session import SessionService

OPENAI_KEY = "sk-openai-secret-wxyz"
XAI_KEY = "xai-page-secret-abcd"


class Captured:
    def __init__(self, text: str = '{"ok": true}'):
        self.calls: list[dict] = []
        self.text = text

    def __call__(self, url, *, headers, json, timeout):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": self.text}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
            request=httpx.Request("POST", url),
        )


def _client(tmp_path) -> tuple[TestClient, Store]:
    store = Store(tmp_path / "models.db")
    service = SessionService(store, FakeAudio(), fake_complete)
    return TestClient(create_app(service)), store


def test_openai_sends_json_format_and_effort_without_temperature(monkeypatch):
    fake = Captured()
    monkeypatch.setattr("logoskittens.llm.httpx.post", fake)
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-test")
    text, record = complete("ping", system="Return JSON.", backend="openai", think="low")
    assert text == '{"ok": true}'
    assert record.backend == "openai" and record.model == "gpt-test"
    call = fake.calls[0]
    assert call["url"] == "https://api.openai.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == f"Bearer {OPENAI_KEY}"
    assert "temperature" not in call["json"]
    assert call["json"]["response_format"] == {"type": "json_object"}
    assert call["json"]["reasoning_effort"] == "low"


def test_openai_without_a_key_names_the_variable(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from logoskittens.llm import LLMError

    with pytest.raises(LLMError, match="OPENAI_API_KEY"):
        complete("ping", system="pong", backend="openai")


def test_the_page_moves_the_buddy_to_openai_over_env(monkeypatch):
    fake = Captured()
    monkeypatch.setattr("logoskittens.llm.httpx.post", fake)
    monkeypatch.setenv("LLM_BACKEND", "local")
    monkeypatch.setenv("LLM_BASE_URL", "http://ollama:11434/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")
    monkeypatch.setenv("LLM_THINK", "off")
    models.replace(
        models.ModelSettings(
            keys={"openai": OPENAI_KEY},
            elements={"buddy": models.ElementChoice(provider="openai", model="gpt-page")},
        )
    )
    _text, record = complete("hi", system="Return JSON.")
    assert record.backend == "openai" and record.model == "gpt-page"
    # LLM_THINK=off belongs to Ollama; a buddy moved to OpenAI gets low.
    assert fake.calls[0]["json"]["reasoning_effort"] == "low"
    models.reset()
    assert models.buddy().provider == "local"


def test_bob_rob_and_wren_follow_the_page_and_reset_to_env(monkeypatch):
    from logoskittens import bob, rob
    from logoskittens.games import wren

    monkeypatch.setenv("XAI_API_KEY", "xai-env-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert bob.load_settings().backend == "xai"
    assert bob.load_settings().source == "env"
    models.replace(
        models.ModelSettings(
            keys={"openai": OPENAI_KEY},
            elements={name: models.ElementChoice(provider="openai") for name in ("bob", "rob", "wren")},
        )
    )
    for loader in (bob.load_settings, rob.load_settings, wren.load_settings):
        settings = loader()
        assert settings.backend == "openai"
        assert settings.base_url == "https://api.openai.com/v1"
        assert settings.api_key == OPENAI_KEY
        assert settings.model != "grok-4.7"
        assert settings.think == "low"
        assert settings.source == "page"
    models.reset()
    assert rob.load_settings().backend == "xai"
    assert rob.load_settings().api_key == "xai-env-key"


def test_a_page_xai_key_beats_the_env_key(monkeypatch):
    from logoskittens import bob

    monkeypatch.setenv("XAI_API_KEY", "xai-env-key")
    models.replace(models.ModelSettings(keys={"xai": XAI_KEY}))
    settings = bob.load_settings()
    assert settings.api_key == XAI_KEY
    assert settings.key_source == "page"


def test_wren_is_ready_with_only_an_openai_key(monkeypatch):
    from logoskittens.games.host import wren_ready

    monkeypatch.setenv("WREN_ENABLED", "on")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("WREN_API_KEY", raising=False)
    assert not wren_ready()
    models.replace(
        models.ModelSettings(keys={"openai": OPENAI_KEY}, elements={"wren": models.ElementChoice(provider="openai")})
    )
    assert wren_ready()


def test_wren_calls_openai_when_the_page_says_so(monkeypatch):
    from logoskittens.games import wren

    fake = Captured('{"line": "hi"}')
    monkeypatch.setattr("logoskittens.llm.httpx.post", fake)
    monkeypatch.setenv("WREN_ENABLED", "on")
    models.replace(
        models.ModelSettings(
            keys={"openai": OPENAI_KEY},
            elements={"wren": models.ElementChoice(provider="openai", model="gpt-wren", think="medium")},
        )
    )
    assert wren.call(game_id="taboo", purpose="test", system="Return JSON.", user="go") == '{"line": "hi"}'
    body = fake.calls[0]["json"]
    assert body["model"] == "gpt-wren" and body["reasoning_effort"] == "medium"


def test_the_routes_keep_keys_hidden_and_survive_a_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "xai-env-secret-1234")
    client, store = _client(tmp_path)
    shown = client.get("/models/settings").json()
    xai = next(item for item in shown["keys"] if item["provider"] == "xai")
    assert xai == {
        "provider": "xai",
        "label": "Grok (xAI)",
        "set": True,
        "source": "env",
        "hint": "…1234",
        "env_name": "XAI_API_KEY",
    }
    assert [item["id"] for item in shown["elements"]] == ["buddy", "bob", "rob", "wren"]
    saved = client.put(
        "/models/settings",
        json={"keys": {"openai": OPENAI_KEY}, "elements": {"rob": {"provider": "openai", "model": "gpt-rob"}}},
    )
    assert saved.status_code == 200
    assert OPENAI_KEY not in saved.text and "xai-env-secret-1234" not in saved.text
    rob_row = next(item for item in saved.json()["elements"] if item["id"] == "rob")
    assert (rob_row["provider"], rob_row["model"], rob_row["source"]) == ("openai", "gpt-rob", "page")
    # A restart reads the row back.
    models.reset()
    models.load(store)
    assert models.current().key("openai") == OPENAI_KEY
    assert models.current().choice("rob").model == "gpt-rob"
    # Reset Rob to .env, then forget the OpenAI key.
    reset = client.delete("/models/element/rob").json()
    assert next(item for item in reset["elements"] if item["id"] == "rob")["provider"] == "xai"
    forgotten = client.delete("/models/key/openai").json()
    assert next(item for item in forgotten["keys"] if item["provider"] == "openai")["set"] is False
    assert json.loads(store.get_model_settings().elements_json) == {}


def test_the_routes_refuse_local_for_bob_and_a_bad_think_level(tmp_path):
    client, _store = _client(tmp_path)
    assert client.put("/models/settings", json={"elements": {"bob": {"provider": "local"}}}).status_code == 400
    bad = client.put("/models/settings", json={"elements": {"wren": {"provider": "openai", "think": "off"}}})
    assert bad.status_code == 400
    assert client.put("/models/settings", json={"keys": {"anthropic": "x"}}).status_code == 400


def test_the_key_test_lists_chat_models_only(tmp_path, monkeypatch):
    def fake_get(url, *, headers, timeout):
        assert headers["Authorization"] == f"Bearer {OPENAI_KEY}"
        data = [{"id": i} for i in ("gpt-b", "gpt-a", "text-embedding-3-small", "whisper-1", "tts-1")]
        return httpx.Response(200, json={"data": data}, request=httpx.Request("GET", url))

    monkeypatch.setattr("logoskittens.model_routes.httpx.get", fake_get)
    client, _store = _client(tmp_path)
    tested = client.post("/models/test", json={"provider": "openai", "key": OPENAI_KEY}).json()
    assert tested == {"ok": True, "error": "", "models": ["gpt-a", "gpt-b"]}
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert client.post("/models/test", json={"provider": "xai"}).json()["ok"] is False


def test_training_accepts_openai(tmp_path, monkeypatch):
    from logoskittens.sim.training_env import load_training

    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    (tmp_path / ".env_training").write_text("BACKEND_SIM_TALK=openai\nBACKEND_JUDGE_PROPOSER=openai\n", encoding="utf-8")
    roles = load_training(tmp_path)
    assert roles.judge.backend == "openai"
    assert roles.judge.base_url == "https://api.openai.com/v1"
    assert roles.judge.api_key == OPENAI_KEY


def test_comparison_record_shape_is_unchanged():
    assert set(ComparisonRecord.__dataclass_fields__) == {
        "backend",
        "model",
        "latency_ms",
        "prompt_tokens",
        "completion_tokens",
    }


def test_env_backend_openai_drops_the_json_grok_url_and_model(monkeypatch):
    from logoskittens import bob

    monkeypatch.setenv("BOB_BACKEND", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    settings = bob.load_settings()
    assert settings.backend == "openai"
    assert settings.base_url == "https://api.openai.com/v1"
    assert settings.model == "gpt-5-mini"
    assert settings.api_key == OPENAI_KEY
    assert settings.source == "env"


def test_a_retry_with_think_off_reaches_openai_and_grok_as_low(monkeypatch):
    """The buddy's re-ask passes think="off". It used to raise before any request, and the turn died silently."""
    fake = Captured()
    monkeypatch.setattr("logoskittens.llm.httpx.post", fake)
    monkeypatch.setenv("OPENAI_API_KEY", OPENAI_KEY)
    monkeypatch.setenv("XAI_API_KEY", "xai-env-key")
    complete("again", system="Return JSON.", backend="openai", think="off")
    complete("again", system="Return JSON.", backend="grok", think="off")
    assert [call["json"]["reasoning_effort"] for call in fake.calls] == ["low", "low"]
