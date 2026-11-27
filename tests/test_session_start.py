"""A session starts only from an explicit Start. Nothing on the socket creates one by itself."""

from fastapi.testclient import TestClient

from logoskittens.api import create_app
from logoskittens.persistence import SessionRow, Store
from logoskittens.session import NO_SESSION, SessionService

from fakes import FakeAudio, fake_complete

from sqlmodel import select

import pytest


@pytest.fixture(autouse=True)
def _no_live_recognizer(monkeypatch):
    calls: list[str] = []

    def switch(language):
        calls.append(language)
        return {"ok": True, "restarted": False, "language": language}

    monkeypatch.setattr("logoskittens.api.switch_recognizer", switch)
    return calls


def _client(tmp_path):
    completes: list[str] = []

    def complete(user, *, system, **kwargs):
        completes.append(user)
        return fake_complete(user, system=system, **kwargs)

    service = SessionService(Store(tmp_path / "start.db"), FakeAudio(), complete)  # type: ignore[arg-type]
    return TestClient(create_app(service)), service, completes


def _sessions(service) -> int:
    with service.store.open() as db:
        return len(db.exec(select(SessionRow)).all())


def _select(**extra) -> dict:
    return {
        "type": "select",
        "user_id": "user-local",
        "language_id": "en",
        "material_id": "norway_vacation_tunnels_fjords",
        "personality_id": "peter",
        **extra,
    }


@pytest.mark.parametrize(
    "message",
    [
        {"type": "transcript", "text": "hello"},
        {"type": "resume", "session_id": "sess-missing"},
        {"type": "resume"},
    ],
)
def test_nothing_but_select_creates_a_session(tmp_path, _no_live_recognizer, message):
    client, service, completes = _client(tmp_path)
    with client.websocket_connect("/ws") as socket:
        socket.send_json(message)
        reply = socket.receive_json()
    assert reply == {"type": "error", "message": NO_SESSION}
    assert _sessions(service) == 0
    assert completes == []
    assert _no_live_recognizer == []


def test_qa_is_a_start_parameter_and_belongs_to_that_session(tmp_path):
    client, service, _completes = _client(tmp_path)
    with client.websocket_connect("/ws") as first, client.websocket_connect("/ws") as second:
        first.send_json(_select(qa=True))
        one = first.receive_json()
        second.send_json(_select(qa=False))
        two = second.receive_json()
    assert one["qa"] is True
    assert two["qa"] is False
    assert service.qa_enabled(one["session_id"]) is True
    assert service.qa_enabled(two["session_id"]) is False


def test_an_imported_material_can_be_deleted_and_a_file_material_cannot(tmp_path):
    client, service, _completes = _client(tmp_path)
    service.store.save_logoscat_material(
        "logoscat-5",
        logoscat_user_id=1,
        workspace_session_id=5,
        language="en",
        title="Workspace five",
        text="The fjord was quiet.",
    )
    listed = [item["id"] for item in client.get("/catalog", params={"language_id": "en"}).json()["materials"]]
    assert "logoscat-5" in listed
    assert client.delete("/logoscat/materials/logoscat-5").json() == {"success": True, "material_id": "logoscat-5"}
    listed = [item["id"] for item in client.get("/catalog", params={"language_id": "en"}).json()["materials"]]
    assert "logoscat-5" not in listed
    assert client.delete("/logoscat/materials/logoscat-5").status_code == 404
    assert client.delete("/logoscat/materials/norway_vacation_tunnels_fjords").status_code == 400
