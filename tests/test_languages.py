"""Stage K: source and target languages (H14). The source is spoken and heard. Targets are written on the card."""

import json
import sqlite3

import httpx
import pytest
from fastapi.testclient import TestClient

from logoskittens.api import create_app
from logoskittens.games.host import closed_glosses, session_targets
from logoskittens.games.models import DeckTarget, GameDeck
from logoskittens.logoscat import LogosCatClient, target_codes

TOKEN = "lkc_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
from logoskittens.persistence import Store
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete


SOURCE = """Jeg er sliten.
Veien var lang.
Vannet var kaldt.
Vi tok en pause.
"""

LINES = ["Jeg er sliten.", "Veien var lang.", "Vannet var kaldt.", "Vi tok en pause."]

GLOSS = {
    "Jeg er sliten.": {"en": "I am tired.", "he": "אני עייף.", "de": "Ich bin müde."},
    "Veien var lang.": {"en": "The road was long.", "he": "הדרך הייתה ארוכה."},
    "Vannet var kaldt.": {"en": "The water was cold.", "he": "x" * 300},
    "Vi tok en pause.": {"en": "We took a break."},
}


@pytest.fixture(autouse=True)
def _switches(monkeypatch):
    calls: list[str] = []

    def switch(language):
        calls.append(language)
        return {"ok": True, "restarted": False, "language": language}

    monkeypatch.setattr("logoskittens.api.switch_recognizer", switch)
    return calls


class Wren:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __call__(self, user: str, *, system: str = "", purpose: str = "", game_id: str = ""):
        del system, game_id
        self.calls.append((purpose, user))
        return json.dumps(
            {
                "targets": [
                    {"id": f"t{index}", "phrase": phrase, "instruction": f"Si {phrase}", "gloss": GLOSS[phrase]}
                    for index, phrase in enumerate(LINES, start=1)
                ]
            }
        )


def _service(tmp_path) -> SessionService:
    service = SessionService(Store(tmp_path / "languages.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.store.save_logoscat_material(
        "logoscat-5",
        logoscat_user_id=1,
        workspace_session_id=5,
        language="nb",
        title="Sliten",
        text=SOURCE,
    )
    service.wren_fn = Wren()
    return service


def _settings_app(tmp_path, settings: dict | None, status: int = 200):
    service = SessionService(Store(tmp_path / "sets.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    app = create_app(service)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        if request.url.path == "/api/language-settings":
            if settings is None:
                return httpx.Response(status, json={"success": False, "error": "Unauthorized"})
            return httpx.Response(200, json={"success": True, "settings": settings})
        return httpx.Response(404, json={"success": False})

    app.state.logoscat = LogosCatClient("http://logoscat.test", transport=httpx.MockTransport(handler))
    return TestClient(app), seen


def test_logoscat_sets_become_sources_with_a_pack_and_targets(tmp_path):
    client, seen = _settings_app(
        tmp_path, {"inputLanguagesSet": ["en", "no", "it"], "outputLanguagesSet": ["no", "en", "he"]}
    )
    body = client.get("/logoscat/language-settings", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert seen == ["/api/language-settings"]
    assert body["origin"] == "logoscat"
    assert body["sources"] == [
        {"id": "en", "live": True, "reason": ""},
        {"id": "nb", "live": True, "reason": ""},
        {"id": "it", "live": False, "reason": "No speech pack yet"},
    ]
    assert [item["id"] for item in body["targets"]] == ["nb", "en", "he"]
    assert body["max_targets"] == 4
    # The source's own entry is never a target of that session.
    assert target_codes(["no", "en", "he"], "nb") == ["en", "he"]
    assert target_codes(["nb", "no", "nob", "en", "he", "ar", "de", "fr"], "en") == ["nb", "he", "ar", "de"]


def test_logged_out_uses_local_defaults_and_the_talk_starts(tmp_path, _switches):
    client, seen = _settings_app(tmp_path, {})
    body = client.get("/logoscat/language-settings").json()
    assert seen == []
    assert body["origin"] == "local"
    assert [item["id"] for item in body["sources"]] == ["en", "nb", "uk", "de", "he"]
    assert all(item["live"] for item in body["sources"])
    assert [item["id"] for item in body["targets"]] == ["en", "nb", "uk", "de", "he"]
    with client.websocket_connect("/ws") as socket:
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
                "personality_id": "peter",
                "game_id": "",
                "target_languages": ["nb"],
            }
        )
        session = socket.receive_json()
    assert session["type"] == "session"
    assert session["target_languages"] == ["nb"]


def test_empty_logoscat_sets_take_logoscat_defaults_and_a_dead_login_is_401(tmp_path):
    client, _seen = _settings_app(tmp_path, {"inputLanguagesSet": [], "outputLanguagesSet": []})
    body = client.get("/logoscat/language-settings", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert [item["id"] for item in body["sources"]] == ["en", "nb", "de"]
    assert [item["id"] for item in body["targets"]] == ["en", "nb", "de"]
    dead, _seen = _settings_app(tmp_path / "dead", None, status=401)
    response = dead.get("/logoscat/language-settings", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 401


def test_a_round_never_switches_the_recognizer_away_from_the_source(tmp_path, _switches):
    service = _service(tmp_path)
    client = TestClient(create_app(service))
    with client.websocket_connect("/ws") as socket:
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "nb",
                "material_id": "logoscat-5",
                "personality_id": "lucas",
                "game_id": "echo_chamber",
                "target_languages": ["en", "he"],
            }
        )
        session = socket.receive_json()
        assert session["type"] == "session"
        assert session["target_languages"] == ["en", "he"]
        assert socket.receive_json()["type"] == "actor"
        socket.send_json({"type": "transcript", "text": "Jeg er sliten."})
        kinds = []
        while "actor" not in kinds:
            kinds.append(socket.receive_json()["type"])
    assert _switches == ["nb"]
    assert service._stt_language(session["session_id"]) == "no"


def test_targets_reach_wren_and_glosses_show_only_after_a_target_closes(tmp_path):
    service = _service(tmp_path)
    session_id = service.select(
        "user-local", "nb", "logoscat-5", "lucas", game_id="echo_chamber", target_languages=["no", "en", "he"]
    )
    purpose, user = service.wren_fn.calls[0]
    assert purpose == "prepare"
    assert user.endswith("glosses: en, he")
    row = service.store.get_session_row(session_id)
    assert session_targets(row) == ["en", "he"]
    deck = GameDeck.model_validate_json(row.deck_json)
    # A code that was not asked for is dropped. A long gloss is cut to 200 characters.
    assert deck.targets[0].gloss == {"en": "I am tired.", "he": "אני עייף."}
    assert len(deck.targets[2].gloss["he"]) == 200
    described = service.describe(session_id)
    assert described["target_languages"] == ["en", "he"]
    assert described["game"]["glosses"] == []
    emitted: list[dict] = []
    service.perform_text(session_id, "Jeg er sliten.", emitted.append)
    game = [item for item in emitted if item["type"] == "game"][0]
    assert game["glosses"] == [
        {"id": "t1", "phrase": "Jeg er sliten.", "status": "hit", "gloss": {"en": "I am tired.", "he": "אני עייף."}}
    ]


def test_a_session_with_no_targets_stores_no_gloss_and_the_card_is_as_today(tmp_path):
    service = _service(tmp_path)
    session_id = service.select("user-local", "nb", "logoscat-5", "lucas", game_id="echo_chamber")
    _purpose, user = service.wren_fn.calls[0]
    assert "glosses:" not in user
    row = service.store.get_session_row(session_id)
    assert session_targets(row) == []
    deck = GameDeck.model_validate_json(row.deck_json)
    assert all(target.gloss == {} for target in deck.targets)
    emitted: list[dict] = []
    service.perform_text(session_id, "Jeg er sliten.", emitted.append)
    game = [item for item in emitted if item["type"] == "game"][0]
    assert game["glosses"] == []
    assert game["feedback"] == "match"


def test_decks_stored_before_this_stage_load_with_empty_glosses(tmp_path):
    old = {
        "deck_version": 1,
        "game_id": "echo_chamber",
        "language": "nb",
        "material_id": "logoscat-5",
        "targets": [{"id": "t1", "phrase": "Jeg er sliten.", "status": "hit"}],
    }
    deck = GameDeck.model_validate(old)
    assert deck.targets[0].gloss == {}
    assert closed_glosses(deck) == []
    # A database from before this stage gains the column with an empty list.
    path = tmp_path / "old.db"
    Store(path)
    with sqlite3.connect(path) as conn:
        conn.execute("ALTER TABLE sessionrow DROP COLUMN target_languages_json")
    store = Store(path)
    store.create_session("sess-old", "talking_game", {}, game_id="echo_chamber", deck_json=json.dumps(old))
    assert session_targets(store.get_session_row("sess-old")) == []
    with pytest.raises(ValueError):
        DeckTarget(id="t1", phrase="x", gloss={code: "y" for code in ("a", "b", "c", "d", "e")})


def test_the_judge_writes_why_in_the_first_target(tmp_path):
    from test_game_interviewer import SOURCE as PASSAGE, Wren as JudgeWren

    def run(targets):
        service = SessionService(Store(tmp_path / f"judge{len(targets)}.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
        service.store.save_logoscat_material(
            "logoscat-88", logoscat_user_id=1, workspace_session_id=88, language="nb", title="Frokost", text=PASSAGE
        )
        wren = JudgeWren(verdicts=[False])
        service.wren_fn = wren
        session_id = service.select(
            "user-local", "nb", "logoscat-88", "lucas", game_id="interviewer", target_languages=targets
        )
        service.perform_text(session_id, "I en kopp", lambda _payload: None)
        purpose, user, _system = wren.calls[-1]
        assert purpose == "judge"
        return user

    assert "feedback_language: he" in run(["he", "en"])
    assert "feedback_language: nb" in run([])
