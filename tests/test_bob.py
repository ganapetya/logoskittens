import base64
import json
import os
import sqlite3

import pytest

from logoskittens.bob import load_settings, parse_suggestion, steer_block, suggest
from logoskittens.llm import LLMError
from logoskittens.persistence import Store
from logoskittens.session import SessionService
from logoskittens.talk import steer_applies
from logoskittens.wire import decode

from fakes import FakeAudio, fake_complete


def _recording():
    systems: list[str] = []
    backends: list[str] = []

    def complete(user: str, *, system: str, **kwargs):
        systems.append(system)
        backends.append(kwargs.get("backend", ""))
        text, record = fake_complete(user, system=system, **kwargs)
        if "private hint" in user:
            return (
                '{"line": "Crowded carriages feel like airplanes in a tunnel.", "emotion": "curiosity"}',
                record,
            )
        return text, record

    return complete, systems, backends


def _service(tmp_path, complete, monkeypatch, suggestion):
    monkeypatch.setattr("logoskittens.session.suggest", suggestion)
    service = SessionService(Store(tmp_path / "bob.db"), FakeAudio(), complete)  # type: ignore[arg-type]
    service._launch = lambda fn: fn()
    return service


def test_settings_follow_bob_json_until_an_override_is_set(monkeypatch):
    for name in (
        "BOB_ENABLED",
        "BOB_BACKEND",
        "BOB_BASE_URL",
        "BOB_MODEL",
        "BOB_THINK",
        "BOB_TIMEOUT",
        "BOB_QA",
        "BOB_API_KEY",
        "XAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings()
    assert settings.enabled is True
    assert settings.backend == "xai"
    assert settings.base_url == "https://api.x.ai/v1"
    assert settings.model == "grok-4.7"
    assert settings.think == "low"
    assert settings.timeout_s == 60
    assert settings.steer_max_chars == 200
    assert settings.every_n == 3
    assert settings.qa is False
    assert settings.api_key == ""

    monkeypatch.setenv("LLM_BACKEND", "local")
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")
    monkeypatch.setenv("BOB_MODEL", "grok-bob")
    monkeypatch.setenv("BOB_THINK", "high")
    monkeypatch.setenv("BOB_API_KEY", "")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    monkeypatch.setenv("BOB_ENABLED", "on")
    monkeypatch.setenv("BOB_EVERY", "1")
    overridden = load_settings()
    assert overridden.model == "grok-bob"
    assert overridden.every_n == 1
    assert overridden.think == "high"
    assert overridden.api_key == "xai-from-env"
    assert os.environ["LLM_BACKEND"] == "local"

    captured: dict = {}

    def complete(user: str, *, system: str, **kwargs):
        captured["kwargs"] = kwargs
        return '{"steer":"Compare trains to airplanes.","why":"stuck"}', None

    monkeypatch.setattr("logoskittens.llm.complete", complete)
    from logoskittens.llm import complete_xai

    complete_xai(
        "recent",
        system="watch",
        base_url=overridden.base_url,
        model=overridden.model,
        api_key=overridden.api_key,
        think=overridden.think,
        timeout=overridden.timeout_s,
    )
    assert captured["kwargs"]["backend"] == "grok"
    assert captured["kwargs"]["model"] == "grok-bob"
    assert captured["kwargs"]["think"] == "high"
    assert captured["kwargs"]["api_key"] == "xai-from-env"
    assert captured["kwargs"]["base_url"] == "https://api.x.ai/v1"
    assert os.environ["LLM_BACKEND"] == "local"
    assert os.environ["LLM_MODEL"] == "qwen3:8b"


def test_an_empty_key_is_refused_before_the_call(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "local")

    def complete(*_args, **_kwargs):
        raise AssertionError("xAI was called")

    monkeypatch.setattr("logoskittens.llm.complete", complete)
    from logoskittens.llm import complete_xai

    with pytest.raises(LLMError, match="BOB_API_KEY or XAI_API_KEY"):
        complete_xai(
            "recent",
            system="watch",
            base_url="https://api.x.ai/v1",
            model="grok-4.7",
            api_key="",
            think="low",
            timeout=60,
        )


def test_an_unknown_backend_fails_the_suggestion_only(monkeypatch):
    monkeypatch.setenv("BOB_ENABLED", "on")
    monkeypatch.setenv("BOB_BACKEND", "local")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    with pytest.raises(LLMError, match="Unknown BOB backend"):
        suggest("recent")


def test_a_steer_is_clamped_and_an_empty_one_stays_empty():
    steer, why, _pose = parse_suggestion(
        '{"steer":"' + ("x" * 250) + '","why":"stuck"}',
        200,
    )
    assert len(steer) == 200
    assert why == "stuck"
    assert parse_suggestion('{"steer":"","why":"moving"}', 200) == ("", "moving", "")
    steer, why, pose = parse_suggestion(
        '{"steer":"Are you swimming?","why":"ask","pose":"agreement"}',
        200,
    )
    assert (steer, pose) == ("Are you swimming?", "curiosity")
    assert parse_suggestion(
        '{"steer":"I agree with you.","why":"yes","pose":["disagreement","agreement"]}',
        200,
    )[2] == "disagreement"
    assert parse_suggestion(
        '{"steer":"The day felt heavy.","why":"sad","pose":"frustration"}',
        200,
    )[2] == "frustration"
    assert parse_suggestion('{"steer":"Compare trains.","why":"near","pose":"nope"}', 200)[2] == ""
    with pytest.raises(LLMError):
        parse_suggestion("not json", 200)


def test_the_next_open_remark_uses_the_steer_and_a_name_question_does_not(tmp_path, monkeypatch):
    monkeypatch.setenv("BOB_ENABLED", "on")
    monkeypatch.setenv("BOB_EVERY", "1")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    complete, systems, backends = _recording()
    replies = iter(
        [
            ("Compare trains to airplanes.", "The last lines stayed on trains."),
            ("", ""),
            ("Compare trains to ships.", "still narrow"),
        ]
    )

    def suggestion(_user: str, *, language_id: str = "en"):
        del language_id
        return next(replies)

    service = _service(tmp_path, complete, monkeypatch, suggestion)
    session_id = service.start()
    systems.clear()
    backends.clear()
    emitted: list[dict] = []
    service.perform_text(session_id, "We took the train.", emitted.append)
    assert [item["type"] for item in emitted] == ["heard", "actor", "bob", "bob"]
    assert emitted[1]["altered"] is False
    assert emitted[1]["steer"] == ""
    assert emitted[2]["status"] == "thinking"
    assert emitted[3]["status"] == "idle"
    assert emitted[3]["steer"] == "Compare trains to airplanes."
    assert "bob_steer" not in systems[0]

    systems.clear()
    backends.clear()
    emitted.clear()
    service.perform_text(session_id, "The carriages were crowded.", emitted.append)
    assert "Compare trains to airplanes." in systems[0]
    assert steer_block("Compare trains to airplanes.") in systems[0]
    assert emitted[0]["type"] == "heard"
    assert emitted[1]["type"] == "actor"
    assert emitted[1]["altered"] is True
    assert emitted[1]["steer"] == "Compare trains to airplanes."
    assert backends[0] == ""
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    assert stored[-1]["speaker"] == "buddy"
    assert stored[-1]["altered"] is True
    assert stored[-1]["steer"] == "Compare trains to airplanes."
    assert service.store.get_session_row(session_id).bob_steer == "Compare trains to airplanes."
    described = service.describe(session_id)
    assert described["sentences"][-1]["altered"] is True
    assert described["bob_qa"] is False

    systems.clear()
    emitted.clear()
    service.perform_text(session_id, "What is your name?", emitted.append)
    assert "Compare trains to airplanes." in systems[0]
    assert emitted[1]["altered"] is False
    assert emitted[1]["steer"] == ""
    assert json.loads(service.store.get_session_row(session_id).sentences_json)[-1]["steer"] == ""
    assert steer_applies("What is your name?", "Compare trains to airplanes.") is False
    assert steer_applies("The carriages were crowded.", "Compare trains to airplanes.") is True
    assert service.store.get_session_row(session_id).bob_steer == "Compare trains to ships."


def test_web_mode_keeps_the_reply_on_the_page_and_botnet_sends_it(tmp_path, monkeypatch):
    monkeypatch.setenv("BOB_ENABLED", "off")
    sent: list[list[str]] = []
    sent_bytes: list[int] = []
    heard: list[dict] = []

    def deliver(pcm: bytes, tokens=None):
        sent.append(list(tokens or []))
        sent_bytes.append(len(pcm))

    service = SessionService(
        Store(tmp_path / "face.db"),
        FakeAudio(),
        fake_complete,  # type: ignore[arg-type]
        deliver_pcm=deliver,
    )
    session_id = service.start()
    service.botnet = lambda: False
    service.perform_text(session_id, "The fjords were quiet.", heard.append)
    assert sent == []
    actors = [item for item in heard if item.get("type") == "actor"]
    assert actors[-1]["play_on_page"] is True
    from logoskittens.wire import decode

    web_pcm = decode(base64.b64decode(actors[-1]["solutions"][0])).speech.precomputed_audio_pcm
    assert len(web_pcm) > 0
    heard.clear()
    service.botnet = lambda: True
    service.perform_text(session_id, "The fjords were quiet.", heard.append)
    assert sent == [[]]
    assert sent_bytes == [len(web_pcm)]
    actors = [item for item in heard if item.get("type") == "actor"]
    assert actors[-1]["play_on_page"] is False
    page_pcm = decode(base64.b64decode(actors[-1]["solutions"][0])).speech.precomputed_audio_pcm
    assert page_pcm == b""


def test_a_missing_key_or_a_disabled_bob_still_returns_the_buddy_line(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("BOB was started")

    monkeypatch.setenv("BOB_ENABLED", "on")
    monkeypatch.delenv("BOB_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    service = SessionService(Store(tmp_path / "bob.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service._launch = boom
    session_id = service.start()
    emitted: list[dict] = []
    service.perform_text(session_id, "hello", emitted.append)
    assert [item["type"] for item in emitted] == ["heard", "actor"]

    monkeypatch.setenv("BOB_ENABLED", "off")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    emitted.clear()
    service.perform_text(session_id, "The carriages were crowded.", emitted.append)
    assert [item["type"] for item in emitted] == ["heard", "actor"]


def test_a_bad_think_level_marks_the_suggestion_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("BOB_ENABLED", "on")
    monkeypatch.setenv("BOB_EVERY", "1")
    monkeypatch.setenv("BOB_THINK", "off")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    service = SessionService(Store(tmp_path / "bob.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service._launch = lambda fn: fn()
    session_id = service.start()
    emitted: list[dict] = []
    service.perform_text(session_id, "We took the train.", emitted.append)
    assert emitted[1]["type"] == "actor"
    assert emitted[-1]["type"] == "bob"
    assert emitted[-1]["status"] == "failed"
    assert service.store.get_session_row(session_id).bob_steer == ""


def test_a_stale_suggestion_does_not_replace_a_newer_steer(tmp_path, monkeypatch):
    monkeypatch.setenv("BOB_ENABLED", "on")
    monkeypatch.setenv("BOB_EVERY", "1")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    held: list = []

    def suggestion(_user: str, *, language_id: str = "en"):
        del language_id
        return "Compare trains to airplanes.", "stuck"

    monkeypatch.setattr("logoskittens.session.suggest", suggestion)
    service = SessionService(Store(tmp_path / "bob.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service._launch = held.append
    session_id = service.start()
    emitted: list[dict] = []
    service.perform_text(session_id, "We took the train.", emitted.append)
    assert emitted[1]["type"] == "actor"
    assert emitted[-1]["status"] == "thinking"
    assert len(held) == 1
    with service._bob_lock:
        service._bob_token[session_id] += 1
    held[0]()
    assert service.store.get_session_row(session_id).bob_steer == ""
    service._finish_bob(session_id, service._bob_token[session_id], "en", "later", emitted.append)
    assert service.store.get_session_row(session_id).bob_steer == "Compare trains to airplanes."

    def broken(_user: str, *, language_id: str = "en"):
        del language_id
        raise RuntimeError()

    monkeypatch.setattr("logoskittens.session.suggest", broken)
    stale = len(emitted)
    held[0]()
    assert service.store.get_session_row(session_id).bob_steer == "Compare trains to airplanes."
    assert not any(item.get("status") == "failed" for item in emitted[stale:])


def test_reset_starts_an_empty_steer(tmp_path, monkeypatch):
    monkeypatch.setenv("BOB_ENABLED", "on")
    monkeypatch.setenv("BOB_EVERY", "1")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")

    def suggestion(_user: str, *, language_id: str = "en"):
        del language_id
        return "Compare trains to airplanes.", "stuck"

    service = _service(tmp_path, fake_complete, monkeypatch, suggestion)
    session_id = service.start()
    service.perform_text(session_id, "We took the train.", lambda _payload: None)
    assert service.store.get_session_row(session_id).bob_steer == "Compare trains to airplanes."
    fresh = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter")
    assert fresh != session_id
    described = service.describe(fresh)
    assert described["bob_steer"] == ""
    assert described["bob_why"] == ""
    assert described["sentences"] == []
    assert service.store.get_session_row(fresh).bob_steer == ""


def test_bob_is_asked_on_every_third_buddy_line(tmp_path, monkeypatch):
    monkeypatch.setenv("BOB_ENABLED", "on")
    monkeypatch.setenv("ROB_ENABLED", "off")
    monkeypatch.delenv("BOB_EVERY", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    seen: list[str] = []

    def suggestion(user: str, *, language_id: str = "en"):
        del language_id
        seen.append(user)
        return "Are you swimming? Love any water sports?", "the talk is about water"

    prompts: list[str] = []

    def complete(user: str, *, system: str, **kwargs):
        prompts.append(user)
        return fake_complete(user, system=system, **kwargs)

    service = _service(tmp_path, complete, monkeypatch, suggestion)
    session_id = service.start()
    prompts.clear()
    for text in ("The water was cold.", "I like this weather.", "Things are happening."):
        emitted: list[dict] = []
        service.perform_text(session_id, text, emitted.append)
        if len(seen) == 0:
            assert [item["type"] for item in emitted] == ["heard", "actor"]
    assert len(seen) == 1
    assert [item["type"] for item in emitted] == ["heard", "actor", "bob", "bob"]
    assert "mood: energetic" in seen[0]
    assert "likes: steak, a fight" in seen[0]
    assert "stance: capitalist" in seen[0]
    assert service.store.get_session_row(session_id).bob_steer == "Are you swimming? Love any water sports?"

    prompts.clear()
    emitted = []
    service.perform_text(session_id, "I feel well.", emitted.append)
    assert len(seen) == 1
    assert "Are you swimming?" in prompts[0]
    assert "Answer that first" in prompts[0]
    assert [item["type"] for item in emitted] == ["heard", "actor"]


def test_the_bob_prompt_asks_for_a_character_fit():
    from logoskittens.content import prompt_text

    text = prompt_text("bob", "en")
    assert "exercises in a forest" in text
    assert "Are you swimming?" in text
    assert "steak or a fight" in text
    assert "already moving" not in text


def test_an_accepted_steer_plays_one_mimic_and_does_not_repeat_it(tmp_path, monkeypatch):
    monkeypatch.setenv("BOB_ENABLED", "off")
    sent: list[list[str]] = []

    def deliver(_pcm: bytes, tokens=None):
        sent.append(list(tokens or []))

    def complete(user: str, *, system: str, **kwargs):
        text, record = fake_complete(user, system=system, **kwargs)
        if "private hint" in user:
            return (
                '{"line": "Crowded carriages feel like airplanes in a tunnel.", "emotion": "neutral"}',
                record,
            )
        return text, record

    service = SessionService(
        Store(tmp_path / "pose.db"),
        FakeAudio(),
        complete,  # type: ignore[arg-type]
        deliver_pcm=deliver,
    )
    session_id = service.start()
    service.store.save_bob(session_id, "Compare trains to airplanes.", "yes", "agreement")
    ignored: list[dict] = []
    service.perform_text(session_id, "What is your name?", ignored.append)
    assert sent == [[]]
    assert service.store.get_session_row(session_id).bob_pose == "agreement"
    service.perform_text(session_id, "The carriages were crowded.", ignored.append)
    assert sent[-1] == ["agreement"]
    assert service.store.get_session_row(session_id).bob_pose == ""
    assert service.store.get_session_row(session_id).bob_steer == "Compare trains to airplanes."
    service.perform_text(session_id, "The carriages were crowded.", ignored.append)
    assert sent[-1] == []


def test_a_sentence_save_does_not_clear_the_steer(tmp_path):
    store = Store(tmp_path / "bob.db")
    store.create_session("sess-bob", "free_speech", {"medium": "virtual_screen"})
    store.save_bob("sess-bob", "Compare trains to airplanes.", "stuck")
    store.save_talk("sess-bob", material_id="norway", subject_json="{}", sentences_json="[]")
    row = store.get_session_row("sess-bob")
    assert row.bob_steer == "Compare trains to airplanes."
    assert row.bob_why == "stuck"
    assert row.sentences_json == "[]"


def test_an_old_session_table_gains_the_bob_columns(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE sessionrow ("
            "id VARCHAR PRIMARY KEY, task_id VARCHAR, situation_json VARCHAR, created_at DATETIME)"
        )
    store = Store(path)
    store.create_session("sess-old", "free_speech", {"medium": "virtual_screen"})
    row = store.get_session_row("sess-old")
    assert row.bob_steer == ""
    assert row.bob_why == ""
    assert row.bob_pose == ""
