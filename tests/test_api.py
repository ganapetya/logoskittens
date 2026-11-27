import base64

from fastapi.testclient import TestClient

from logoskittens.api import create_app
from logoskittens.persistence import Store
from logoskittens.session import SessionService
from logoskittens.wire import decode

from fakes import FakeAudio, fake_complete

import pytest


@pytest.fixture(autouse=True)
def _no_live_recognizer(monkeypatch):
    monkeypatch.setattr(
        "logoskittens.api.switch_recognizer",
        lambda language: {"ok": True, "restarted": False, "language": language},
    )


def _client(tmp_path):
    service = SessionService(
        Store(tmp_path / "api.db"),
        FakeAudio(),  # type: ignore[arg-type]
        fake_complete,
    )
    return TestClient(create_app(service)), service


def test_a_turn_returns_one_buddy_solution(tmp_path):
    client, service = _client(tmp_path)
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        hello = socket.receive_json()
        assert hello["type"] == "session"
        assert hello["language_id"] == "en"
        assert hello["material_id"] == "norway_vacation_tunnels_fjords"
        assert "fjord" in hello["theme"].lower() or "Norway" in hello["theme"]
        assert hello["sentences"] == []
        assert hello["subject"]["important_words"] == ["ferries", "slopes"]
        session_id = hello["session_id"]
        socket.send_json({"type": "transcript", "text": "yes"})
        heard = socket.receive_json()
        actor = socket.receive_json()
    assert heard["type"] == "heard"
    assert heard["transcript"] == "yes"
    assert heard["final"] is False
    assert actor["type"] == "actor"
    assert actor["final"] is True
    solution = decode(base64.b64decode(actor["solutions"][0]))
    assert solution.actor_id == "buddy-one"
    assert solution.speech.precomputed_audio_pcm
    snapshot = service.snapshot(session_id)
    assert snapshot["turns"][0]["user_text"] == "yes"
    assert snapshot["sentences"][-1]["speaker"] == "buddy"
    assert len(snapshot["sentences"]) >= 2


def test_a_second_turn_continues_the_same_subject(tmp_path):
    client, _service = _client(tmp_path)
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        hello = socket.receive_json()
        socket.send_json({"type": "transcript", "text": "yes"})
        socket.receive_json()
        socket.receive_json()
        socket.send_json({"type": "transcript", "text": "The tunnels were long."})
        socket.receive_json()
        second = socket.receive_json()
    assert second["final"] is True
    assert decode(base64.b64decode(second["solutions"][0])).actor_id == "buddy-one"
    reread = client.get(f"/sessions/{hello['session_id']}").json()
    assert reread["material_id"] == hello["material_id"]
    assert len(reread["sentences"]) >= 4


def test_a_bad_subject_keeps_the_socket_open(tmp_path):
    from logoskittens.llm import ComparisonRecord

    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            return "not a card", ComparisonRecord(
                backend="fake", model="fake", latency_ms=0, prompt_tokens=0, completion_tokens=0
            )
        return fake_complete(user, system=system, **kwargs)

    service = SessionService(Store(tmp_path / "api.db"), FakeAudio(), complete)  # type: ignore[arg-type]
    client = TestClient(create_app(service))
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        failed = socket.receive_json()
        socket.send_json({"type": "start"})
        hello = socket.receive_json()
    assert failed["type"] == "error"
    assert "subject card" in failed["message"]
    assert hello["type"] == "session"
    assert hello["sentences"] == []


def test_a_nocaptions_token_does_not_call_the_buddy(tmp_path):
    client, service = _client(tmp_path)
    service.audio.transcribe = lambda *_args, **_kwargs: "<|nocaptions|>"  # type: ignore[method-assign]
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        socket.receive_json()
        socket.send_json({"type": "audio", "mime": "audio/wav", "data": base64.b64encode(b"noise").decode()})
        turn = socket.receive_json()
    assert turn["type"] == "heard"
    assert turn["transcript"] == ""
    assert turn["notice"] == "No speech detected."


def test_silent_audio_does_not_call_the_buddy(tmp_path):
    client, _service = _client(tmp_path)
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        socket.receive_json()
        socket.send_json({"type": "audio", "mime": "audio/wav", "data": base64.b64encode(b"silence").decode()})
        turn = socket.receive_json()
    assert turn["type"] == "heard"
    assert turn["transcript"] == ""
    assert turn["final"] is True
    assert turn["notice"] == "No speech detected."


def test_selecting_material_starts_a_new_session(tmp_path, monkeypatch):
    switched: list[str] = []
    monkeypatch.setattr(
        "logoskittens.api.switch_recognizer",
        lambda language: switched.append(language) or {"ok": True, "restarted": True},
    )
    client, _service = _client(tmp_path)
    with client.websocket_connect("/ws") as socket:
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
            }
        )
        first = socket.receive_json()
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
            }
        )
        second = socket.receive_json()
    assert first["session_id"] != second["session_id"]
    assert switched == ["en", "en"]
    listed = client.get("/catalog").json()
    assert listed["languages"] == [
        {"id": "de", "display_name": "Deutsch"},
        {"id": "en", "display_name": "English"},
        {"id": "he", "display_name": "עברית"},
        {"id": "nb", "display_name": "Norsk"},
        {"id": "uk", "display_name": "Українська"},
    ]
    materials = {item["id"]: item["title"] for item in listed["materials"]}
    assert materials["norway_vacation_tunnels_fjords"] == "Vacation in Norway"
    assert materials["friendly_chat"] == "Friendly chat"
    assert materials["spider_brackfast"] == "Spider Brackfast"
    assert [item["id"] for item in listed["personalities"]] == ["peter", "mary"]


def test_peter_is_the_default_and_reset_returns_to_him(tmp_path):
    client, _service = _client(tmp_path)
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        hello = socket.receive_json()
        assert hello["buddy_name"] == "Peter"
        assert hello["personality_id"] == "peter"
        socket.send_json({"type": "transcript", "text": "What is your name?"})
        socket.receive_json()
        actor = socket.receive_json()
        voice = decode(base64.b64decode(actor["solutions"][0])).speech.voice_model_id
        assert voice == "en_US-ryan-medium"
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
                "personality_id": "mary",
            }
        )
        mary = socket.receive_json()
        assert mary["type"] == "session"
        assert mary["session_id"] != hello["session_id"]
        assert mary["buddy_name"] == "Mary"
        assert mary["personality_id"] == "mary"
        assert mary["sentences"] == []
        socket.send_json({"type": "transcript", "text": "Are you a woman or a man?"})
        socket.receive_json()
        mary_actor = socket.receive_json()
        mary_voice = decode(base64.b64decode(mary_actor["solutions"][0])).speech.voice_model_id
        assert mary_voice == "en_US-lessac-medium"
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
                "personality_id": "",
            }
        )
        again = socket.receive_json()
        assert again["buddy_name"] == "Peter"
        assert again["personality_id"] == "peter"
        assert again["sentences"] == []
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
                "personality_id": "nobody",
            }
        )
        fallback = socket.receive_json()
        assert fallback["type"] == "session"
        assert fallback["personality_id"] == "peter"
        assert fallback["buddy_name"] == "Peter"
        socket.send_json({"type": "start"})
        recovered = socket.receive_json()
    assert recovered["type"] == "session"
    assert recovered["personality_id"] == "peter"


def test_one_material_text_is_read_on_demand_and_odd_ids_are_refused(tmp_path):
    client, service = _client(tmp_path)
    service.store.save_logoscat_material(
        "logoscat-31", logoscat_user_id=1, workspace_session_id=31, language="nb", title="Ferie", text="Vi reiste."
    )
    body = client.get("/materials/norway_vacation_tunnels_fjords", params={"language_id": "nb"}).json()
    assert body["id"] == "norway_vacation_tunnels_fjords"
    assert body["language"] == "nb"
    assert body["title"] and "fjord" in body["text"].lower()
    assert client.get("/materials/logoscat-31", params={"language_id": "nb"}).json()["text"] == "Vi reiste."
    # A downloaded session in another language, an unknown id, and a path-like language are all not found.
    assert client.get("/materials/logoscat-31", params={"language_id": "en"}).status_code == 404
    assert client.get("/materials/nothing_here", params={"language_id": "nb"}).status_code == 404
    assert client.get("/materials/friendly_chat", params={"language_id": "../nb"}).status_code == 404
    # The catalog list still carries no sentences.
    listed = client.get("/catalog", params={"language_id": "nb"}).json()["materials"]
    assert listed and all("text" not in item for item in listed)
