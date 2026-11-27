import base64
import json
import sqlite3

import pytest

from logoskittens.persistence import Store
from logoskittens.personalities import list_personalities
from logoskittens.llm import LLMError
from logoskittens.rob import load_settings, parse_pedantic, parse_suggestion, rob_due
from logoskittens.session import SessionService
from logoskittens.teachers import get_teacher
from logoskittens.wire import decode

from fakes import FakeAudio, fake_complete


CORRECTION = "Name the tunnel you mean."


def _service(tmp_path, monkeypatch, suggestion, complete=fake_complete):
    monkeypatch.setattr("logoskittens.session.rob_suggest", suggestion)
    monkeypatch.setenv("ROB_ENABLED", "on")
    monkeypatch.setenv("BOB_ENABLED", "off")
    monkeypatch.delenv("ROB_EVERY", raising=False)
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    service = SessionService(Store(tmp_path / "rob.db"), FakeAudio(), complete)  # type: ignore[arg-type]
    service._launch = lambda fn: fn()
    return service


def _silence(_user: str, *, language_id: str = "en"):
    del language_id
    return "", "The human lines were already clear."


def test_settings_follow_rob_json_and_the_gap_is_two_to_four(monkeypatch):
    for name in (
        "ROB_ENABLED",
        "ROB_BACKEND",
        "ROB_BASE_URL",
        "ROB_MODEL",
        "ROB_THINK",
        "ROB_TIMEOUT",
        "ROB_API_KEY",
        "ROB_EVERY",
        "XAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = load_settings()
    assert settings.enabled is True
    assert settings.backend == "xai"
    assert settings.model == "grok-4.7"
    assert settings.think == "low"
    assert settings.every_n == 3
    assert settings.line_max_chars == 240
    assert settings.explanation_max_chars == 600
    assert settings.pedantic_every_responses == 2
    assert settings.api_key == ""
    monkeypatch.setenv("ROB_EVERY", "4")
    monkeypatch.setenv("ROB_API_KEY", "rob-key")
    assert load_settings().every_n == 4
    assert load_settings().api_key == "rob-key"
    monkeypatch.setenv("ROB_EVERY", "1")
    with pytest.raises(ValueError, match="2, 3, or 4"):
        load_settings()
    assert rob_due(2, 3) is False
    assert rob_due(3, 3) is True


def test_savelij_is_a_teacher_and_not_a_buddy_choice():
    teacher = get_teacher("en")
    assert teacher is not None
    assert teacher.name == "Savelij"
    assert teacher.actor_id == "teacher-one"
    assert teacher.voice_id == "en_US-ryan-medium"
    norsk = get_teacher("nb")
    assert norsk is not None
    assert norsk.name == "Savelij"
    assert norsk.actor_id == "teacher-one"
    assert norsk.voice_id == "no_NO-talesyntese-medium"
    assert [item.id for item in list_personalities("en")] == ["peter", "mary"]
    assert [item.id for item in list_personalities("nb")] == ["lucas", "ingrid"]


def test_a_gap_of_three_calls_rob_once_and_savelij_says_that_sentence(tmp_path, monkeypatch):
    seen: list[str] = []

    def suggestion(user: str, *, language_id: str = "en"):
        del language_id
        seen.append(user)
        return CORRECTION, "The tunnel was unnamed."

    service = _service(tmp_path, monkeypatch, suggestion)
    session_id = service.start()
    described = service.describe(session_id)
    assert described["teacher_name"] == "Savelij"
    assert "Pedantic" in described["teacher_summary"]
    assert service.catalog("user-local", "en")["teacher_name"] == "Savelij"
    assert service.catalog("user-local", "nb")["teacher_name"] == "Savelij"
    assert [item["id"] for item in service.describe(session_id)["personalities"]] == ["peter", "mary"]
    lines = ["The water was cold.", "I like this weather.", "Things are happening."]
    emitted: list[dict] = []
    for text in lines[:2]:
        emitted = []
        service.perform_text(session_id, text, emitted.append)
        assert [item["type"] for item in emitted] == ["heard", "actor"]
        assert seen == []
    emitted = []
    service.perform_text(session_id, lines[2], emitted.append)
    assert len(seen) == 1
    assert "The water was cold." in seen[0]
    assert "Things are happening." in seen[0]
    assert [item["type"] for item in emitted] == ["heard", "actor", "rob", "rob", "actor"]
    buddy = decode(base64.b64decode(emitted[1]["solutions"][0]))
    teacher = decode(base64.b64decode(emitted[-1]["solutions"][0]))
    assert buddy.actor_id == "buddy-one"
    assert CORRECTION not in buddy.speech.text
    assert teacher.actor_id == "teacher-one"
    assert teacher.speech.text == CORRECTION
    assert teacher.speech.voice_model_id == "en_US-ryan-medium"
    assert emitted[-1]["speaker"] == "Savelij"
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    assert stored[0]["speaker"] == "human"
    assert stored[0]["text"] == "The water was cold."
    assert stored[-1]["speaker"] == "teacher"
    assert stored[-1]["text"] == CORRECTION
    row = service.store.get_session_row(session_id)
    assert row.rob_line == CORRECTION
    assert row.rob_quiet is False
    assert row.rob_cursor == 6

    for text in ("The road was new.", "The boat was small."):
        emitted = []
        service.perform_text(session_id, text, emitted.append)
        assert len(seen) == 1
    emitted = []
    service.perform_text(session_id, "The hill was steep.", emitted.append)
    assert len(seen) == 2
    assert "The water was cold." not in seen[1]
    assert "The road was new." in seen[1]
    assert "The hill was steep." in seen[1]


def test_silence_leaves_savelij_quiet(tmp_path, monkeypatch):
    service = _service(tmp_path, monkeypatch, _silence)
    session_id = service.start()
    emitted: list[dict] = []
    for text in ("The water was cold.", "I like this weather.", "Things are happening."):
        emitted = []
        service.perform_text(session_id, text, emitted.append)
    assert not any(
        decode(base64.b64decode(item["solutions"][0])).actor_id == "teacher-one"
        for item in emitted
        if item["type"] == "actor"
    )
    assert emitted[-1]["type"] == "rob"
    assert emitted[-1]["quiet"] is True
    assert emitted[-1]["line"] == ""
    assert "already clear" in emitted[-1]["why"]
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    assert all(item["speaker"] != "teacher" for item in stored)


def test_a_late_rob_result_is_dropped_when_a_newer_call_started(tmp_path, monkeypatch):
    monkeypatch.setenv("ROB_EVERY", "2")
    held: list = []

    def suggestion(_user: str, *, language_id: str = "en"):
        del language_id
        return CORRECTION, "unnamed"

    monkeypatch.setattr("logoskittens.session.rob_suggest", suggestion)
    monkeypatch.setenv("ROB_ENABLED", "on")
    monkeypatch.setenv("BOB_ENABLED", "off")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    service = SessionService(Store(tmp_path / "rob.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service._launch = held.append
    session_id = service.start()
    emitted: list[dict] = []
    service.perform_text(session_id, "The water was cold.", emitted.append)
    service.perform_text(session_id, "I like this weather.", emitted.append)
    assert emitted[-1]["status"] == "thinking"
    assert len(held) == 1
    with service._rob_lock:
        service._rob_token[session_id] += 1
    held[0]()
    assert service.store.get_session_row(session_id).rob_line == ""
    service._finish_rob(session_id, service._rob_token[session_id], "en", "later", emitted.append)
    assert service.store.get_session_row(session_id).rob_line == CORRECTION
    assert any(item.get("speaker") == "Savelij" for item in emitted)


def test_web_plays_savelij_and_botnet_sends_him_only_to_the_teacher(tmp_path, monkeypatch):
    def suggestion(_user: str, *, language_id: str = "en"):
        del language_id
        return CORRECTION, "unnamed"

    calls: list[str] = []

    def deliver(pcm: bytes, tokens=None, language: str = "", role: str = "buddy"):
        del pcm, tokens, language
        calls.append(role)

    service = _service(tmp_path, monkeypatch, suggestion)
    service.deliver_pcm = deliver
    service.botnet = lambda: False
    session_id = service.start()
    emitted: list[dict] = []
    for text in ("The water was cold.", "I like this weather.", "Things are happening."):
        emitted = []
        service.perform_text(session_id, text, emitted.append)
    assert calls == []
    teacher = [item for item in emitted if item.get("speaker") == "Savelij"]
    assert teacher[-1]["play_on_page"] is True
    page = decode(base64.b64decode(teacher[-1]["solutions"][0]))
    assert len(page.speech.precomputed_audio_pcm) > 0

    calls.clear()
    service.botnet = lambda: True
    fresh = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter")
    for text in ("The water was cold.", "I like this weather.", "Things are happening."):
        emitted = []
        service.perform_text(fresh, text, emitted.append)
    assert calls == ["buddy", "buddy", "buddy", "teacher"]
    teacher = [item for item in emitted if item.get("speaker") == "Savelij"]
    assert teacher[-1]["play_on_page"] is False
    quiet = decode(base64.b64decode(teacher[-1]["solutions"][0]))
    assert quiet.speech.precomputed_audio_pcm == b""
    buddy = decode(base64.b64decode(emitted[1]["solutions"][0]))
    assert buddy.actor_id == "buddy-one"
    assert buddy.speech.precomputed_audio_pcm == b""


def test_norsk_uses_the_same_teacher(tmp_path, monkeypatch):
    seen: list[tuple[str, str]] = []

    def suggestion(user: str, *, language_id: str = "en"):
        seen.append((language_id, user))
        return "Si navnet på tunnelen.", "uten navn"

    service = _service(tmp_path, monkeypatch, suggestion)
    session_id = service.select("user-local", "nb", "norway_vacation_tunnels_fjords", "lucas")
    assert service.describe(session_id)["teacher_name"] == "Savelij"
    emitted: list[dict] = []
    for text in ("Vannet var kaldt.", "Jeg liker været.", "Ting skjer."):
        emitted = []
        service.perform_text(session_id, text, emitted.append)
    assert len(seen) == 1
    assert seen[0][0] == "nb"
    assert "Vannet var kaldt." in seen[0][1]
    teacher = decode(base64.b64decode(emitted[-1]["solutions"][0]))
    assert teacher.actor_id == "teacher-one"
    assert teacher.speech.text == "Si navnet på tunnelen."
    assert teacher.speech.voice_model_id == "no_NO-talesyntese-medium"
    buddy = decode(base64.b64decode(emitted[1]["solutions"][0]))
    assert buddy.actor_id == "buddy-one"
    assert "Si navnet" not in buddy.speech.text


def test_the_rob_prompt_asks_for_one_sentence():
    from logoskittens.content import prompt_text

    text = prompt_text("rob", "en")
    assert "pedantic" in text
    assert "unapologetic" in text
    assert '"correction"' in text
    assert "Do not correct the buddy" in text
    norsk = prompt_text("rob", "nb")
    assert "pedantisk" in norsk
    assert "Ikke rett kameraten" in norsk
    assert "Do not correct the buddy" not in norsk
    pedantic = prompt_text("rob_pedantic", "en")
    assert '"explanation"' in pedantic
    assert "every numbered human sentence" in pedantic
    pedantic_nb = prompt_text("rob_pedantic", "nb")
    assert "nummererte" in pedantic_nb
    assert "every numbered" not in pedantic_nb


def test_parse_keeps_one_sentence_or_silence():
    line, why = parse_suggestion(
        '{"correction": "Name the tunnel you mean. Then tell a story.", "why": "unnamed"}',
        240,
    )
    assert line == "Name the tunnel you mean."
    assert why == "unnamed"
    line, why = parse_suggestion('{"correction": "", "why": "clear enough"}', 240)
    assert line == ""
    assert why == "clear enough"
    with pytest.raises(LLMError):
        parse_suggestion("no json", 240)


def test_parse_pedantic_keeps_one_note_per_sentence():
    notes = parse_pedantic(
        '{"notes": ['
        '{"correction": "Say this. And more.", "why": "short", "explanation": ""},'
        '{"correction": "", "why": "", "explanation": "Do not keep this."}'
        "]}",
        ["Heard one.", "Heard two."],
        line_max=240,
        explanation_max=80,
        language_id="en",
    )
    assert notes[0][0] == "Say this."
    assert notes[0][1] == "short"
    assert notes[0][2].startswith('In "Heard one." say "Say this." instead.')
    assert len(notes[0][2]) <= 80
    assert notes[1] == ("", "", "")
    norsk = parse_pedantic(
        '{"notes": [{"correction": "Si dette.", "why": "kort", "explanation": ""}]}',
        ["Hørt."],
        line_max=240,
        explanation_max=600,
        language_id="nb",
    )
    assert norsk[0][2].startswith("I «Hørt.» si «Si dette.» i stedet.")
    with pytest.raises(LLMError):
        parse_pedantic("no json", ["A."], line_max=240, explanation_max=600, language_id="en")


def test_pedantic_waits_for_two_responses_and_stores_each_correction(tmp_path, monkeypatch):
    seen: list[tuple[str, list[str], str]] = []

    def suggestion(user: str, human_lines: list[str], *, language_id: str = "en"):
        seen.append((language_id, list(human_lines), user))
        notes = []
        for line in human_lines:
            if "weather" in line:
                notes.append(
                    (
                        "I like this weather today.",
                        "too bare",
                        "In the weather sentence say I like this weather today. It names the day.",
                    )
                )
            else:
                notes.append(("", "", ""))
        return notes

    def relaxed(*_args, **_kwargs):
        raise AssertionError("relaxed Rob ran")

    monkeypatch.setattr("logoskittens.session.rob_suggest_pedantic", suggestion)
    monkeypatch.setattr("logoskittens.session.rob_suggest", relaxed)
    monkeypatch.setenv("ROB_ENABLED", "on")
    monkeypatch.setenv("BOB_ENABLED", "off")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    service = SessionService(Store(tmp_path / "pedantic.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service._launch = lambda fn: fn()
    session_id = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", teacher_mode="pedantic")
    assert service.describe(session_id)["teacher_mode"] == "pedantic"
    emitted: list[dict] = []
    service.perform_text(session_id, "The water was cold.", emitted.append)
    assert seen == []
    assert "teacher-notes" not in [item["type"] for item in emitted]
    emitted = []
    service.perform_text(session_id, "I like this weather. Things are happening.", emitted.append)
    assert len(seen) == 1
    assert seen[0][0] == "en"
    assert seen[0][1] == ["The water was cold.", "I like this weather.", "Things are happening."]
    assert "1. human: The water was cold." in seen[0][2]
    assert "2. human: I like this weather." in seen[0][2]
    assert not any(
        item["type"] == "actor" and decode(base64.b64decode(item["solutions"][0])).actor_id == "teacher-one"
        for item in emitted
    )
    notes = next(item for item in emitted if item["type"] == "teacher-notes")
    assert len(notes["notes"]) == 1
    assert "pcm" not in notes["notes"][0]
    assert "weather sentence" in notes["notes"][0]["explanation"]
    described = service.describe(session_id)
    assert "pcm" not in json.dumps(described)
    weather = next(item for item in described["sentences"] if item["text"] == "I like this weather.")
    cold = next(item for item in described["sentences"] if item["text"] == "The water was cold.")
    assert weather["note_id"] == notes["notes"][0]["note_id"]
    assert "note_id" not in cold
    assert all(item["speaker"] != "teacher" for item in described["sentences"])
    stored = service.store.get_teacher_note(notes["notes"][0]["note_id"])
    assert stored is not None
    assert stored.pcm
    assert stored.explanation.startswith("In the weather sentence")
    from fastapi.testclient import TestClient
    from logoskittens.api import create_app

    client = TestClient(create_app(service))
    found = client.get("/teacher-notes/" + stored.id, params={"session_id": session_id})
    assert found.status_code == 200
    assert found.json()["pcm"]
    assert found.json()["explanation"] == stored.explanation
    missing = client.get("/teacher-notes/" + stored.id, params={"session_id": "sess-other"})
    assert missing.status_code == 404


def test_pedantic_bad_json_stores_no_note(tmp_path, monkeypatch):
    def suggestion(_user: str, _lines: list[str], *, language_id: str = "en"):
        del language_id
        raise LLMError("rob suggestion was not JSON")

    monkeypatch.setattr("logoskittens.session.rob_suggest_pedantic", suggestion)
    monkeypatch.setenv("ROB_ENABLED", "on")
    monkeypatch.setenv("BOB_ENABLED", "off")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    service = SessionService(Store(tmp_path / "bad.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service._launch = lambda fn: fn()
    session_id = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", teacher_mode="pedantic")
    emitted: list[dict] = []
    service.perform_text(session_id, "The water was cold.", emitted.append)
    service.perform_text(session_id, "I like this weather.", emitted.append)
    assert emitted[-1]["type"] == "rob"
    assert emitted[-1]["status"] == "failed"
    assert service.store.teacher_note_ids(session_id) == {}
    assert service.store.get_session_row(session_id).rob_cursor > 0


def test_switching_mode_does_not_rewind_the_cursor(tmp_path, monkeypatch):
    relaxed_seen: list[str] = []
    pedantic_seen: list[list[str]] = []

    def relaxed(user: str, *, language_id: str = "en"):
        del language_id
        relaxed_seen.append(user)
        return CORRECTION, "unnamed"

    def pedantic(_user: str, human_lines: list[str], *, language_id: str = "en"):
        del language_id
        pedantic_seen.append(list(human_lines))
        return [("", "", "") for _line in human_lines]

    service = _service(tmp_path, monkeypatch, relaxed)
    monkeypatch.setattr("logoskittens.session.rob_suggest_pedantic", pedantic)
    session_id = service.start()
    for text in ("The water was cold.", "I like this weather.", "Things are happening."):
        service.perform_text(session_id, text, lambda _message: None)
    cursor = service.store.get_session_row(session_id).rob_cursor
    assert cursor == 6
    assert len(relaxed_seen) == 1
    service.set_teacher_mode(session_id, "pedantic")
    assert service.store.get_session_row(session_id).rob_cursor == cursor
    assert service.describe(session_id)["teacher_mode"] == "pedantic"
    service.perform_text(session_id, "The road was new.", lambda _message: None)
    assert pedantic_seen == []
    service.perform_text(session_id, "The boat was small.", lambda _message: None)
    assert pedantic_seen == [["The road was new.", "The boat was small."]]
    assert len(relaxed_seen) == 1


def test_an_old_session_table_gains_the_rob_columns(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE sessionrow ("
            "id VARCHAR PRIMARY KEY, task_id VARCHAR, situation_json VARCHAR, created_at DATETIME)"
        )
    store = Store(path)
    store.create_session("sess-old", "free_speech", {"medium": "virtual_screen"})
    row = store.get_session_row("sess-old")
    assert row.rob_cursor == 0
    assert row.rob_line == ""
    assert row.rob_why == ""
    assert row.rob_quiet is False
    assert row.teacher_mode == "relaxed"
