"""EchoChamberGame. Wren builds the deck. The match is local."""

import json
from pathlib import Path

from logoskittens.games.host import load_game_prompt
from sqlmodel import select

from logoskittens.persistence import SessionRow, Store
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete

import pytest


SOURCE = """Jeg er sliten.
Veien var lang.
Vannet var kaldt.
Vi tok en pause.
Kvelden ble rolig.
Båten lå stille.
Lyset var svakt.
Vinden kom inn.
"""

LINES = [
    "Jeg er sliten.",
    "Veien var lang.",
    "Vannet var kaldt.",
    "Vi tok en pause.",
    "Kvelden ble rolig.",
    "Båten lå stille.",
    "Lyset var svakt.",
    "Vinden kom inn.",
]

ROOT = Path(__file__).resolve().parents[1]


def _deck(phrases: list[str]) -> str:
    return json.dumps(
        {
            "targets": [
                {"id": f"t{index}", "phrase": phrase, "instruction": f"Say {phrase}"}
                for index, phrase in enumerate(phrases, start=1)
            ]
        }
    )


def _service(tmp_path) -> SessionService:
    service = SessionService(
        Store(tmp_path / "echo.db"),
        FakeAudio(),  # type: ignore[arg-type]
        fake_complete,
    )
    service.store.save_logoscat_material(
        "logoscat-77",
        logoscat_user_id=1,
        workspace_session_id=77,
        language="en",
        title="Echo lines",
        text=SOURCE,
    )
    return service


def _bind(service: SessionService, phrases: list[str]) -> list[str]:
    purposes: list[str] = []

    def wren(user: str, *, system: str = "", purpose: str = "", game_id: str = ""):
        del user, system, game_id
        purposes.append(purpose)
        return _deck(phrases)

    service.wren_fn = wren
    return purposes


def _select(service: SessionService):
    return service.select("user-local", "en", "logoscat-77", "peter", game_id="echo_chamber")


def test_nb_prompts_are_not_the_english_files():
    games = ROOT / "config" / "prompts" / "games"
    english = (games / "echo_chamber_wren_en.md").read_text(encoding="utf-8")
    norsk = (games / "echo_chamber_wren_nb.md").read_text(encoding="utf-8")
    assert english.strip() != norsk.strip()
    assert load_game_prompt("echo_chamber", "wren", "nb") == norsk
    # Echo has no partner. Every line she says is a deck string.
    assert not (games / "echo_chamber_partner_en.md").exists()
    assert not (games / "echo_chamber_partner_nb.md").exists()


def test_a_deck_is_kept_only_inside_four_to_eight(tmp_path):
    service = _service(tmp_path)
    purposes = _bind(service, LINES[:4])
    session_id = _select(service)
    row = service.store.get_session_row(session_id)
    deck = json.loads(row.deck_json)
    assert len(deck["targets"]) == 4
    assert deck["targets"][0]["status"] == "active"
    assert purposes == ["prepare"]
    described = service.describe(session_id)
    # The opening is the first phrase, spoken by her and stored as her line.
    assert [(item["speaker"], item["text"]) for item in described["sentences"]] == [("buddy", "Jeg er sliten.")]
    assert described["game"]["phrase"] == "Jeg er sliten."
    assert described["game"]["instruction"] == "Say Jeg er sliten."
    assert described["game"]["source"] == ""

    def _count(store: Store) -> int:
        with store.open() as db:
            return len(db.exec(select(SessionRow)).all())

    short = _service(tmp_path)
    before = _count(short.store)
    short_calls = _bind(short, LINES[:3])
    with pytest.raises(ValueError, match="grounded 3"):
        short.select("user-local", "en", "logoscat-77", "peter", game_id="echo_chamber")
    assert _count(short.store) == before
    assert short_calls == ["prepare", "prepare"]
    assert "score" not in short_calls

    invented = _service(tmp_path)
    before = _count(invented.store)
    invented_calls = _bind(invented, ["Jeg er sliten.", "en linje som ikke står her", "heller ikke denne", "og ikke denne"])
    with pytest.raises(ValueError, match="grounded 1"):
        invented.select("user-local", "en", "logoscat-77", "peter", game_id="echo_chamber")
    assert _count(invented.store) == before
    assert invented_calls == ["prepare", "prepare"]

    wide = _service(tmp_path)
    before = _count(wide.store)
    nine = ["Jeg", "sliten", "Veien", "lang", "Vannet", "kaldt", "pause", "Kvelden", "Båten"]
    wide_calls = _bind(wide, nine)
    with pytest.raises(ValueError, match="grounded 9"):
        wide.select("user-local", "en", "logoscat-77", "peter", game_id="echo_chamber")
    assert _count(wide.store) == before
    assert wide_calls == ["prepare", "prepare"]


def test_an_exact_line_hits_and_a_miss_stays_on_the_same_card(tmp_path):
    service = _service(tmp_path)
    purposes = _bind(service, LINES[:4])
    completes = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        completes["n"] += 1
        return fake_complete(user, system=system, **kwargs)

    service.complete_fn = complete
    session_id = _select(service)
    emitted: list[dict] = []
    service.perform_text(session_id, "Jeg er sliten.", emitted.append)
    assert [item["type"] for item in emitted] == ["heard", "game", "actor"]
    assert emitted[1]["feedback"] == "match"
    assert emitted[1]["phrase"] == "Veien var lang."
    assert completes["n"] == 0
    assert purposes == ["prepare"]
    deck = json.loads(service.store.get_session_row(session_id).deck_json)
    assert deck["targets"][0]["status"] == "hit"
    assert deck["targets"][1]["status"] == "active"

    emitted.clear()
    service.perform_text(session_id, "ikke denne", emitted.append)
    assert emitted[0]["transcript"] == "ikke denne"
    assert emitted[1]["feedback"] == "miss"
    assert emitted[1]["phrase"] == "Veien var lang."
    assert emitted[1]["matches"] == 1
    assert emitted[1]["misses"] == 1
    assert emitted[1]["miss_note"]["verdict"] == "wrong"
    assert emitted[1]["miss_note"]["explanation"] == "The line was: Veien var lang."
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    heard = [item for item in stored if item["speaker"] == "human"]
    assert heard[-1]["text"] == "ikke denne"
    assert heard[-1]["verdict"] == "wrong"
    assert heard[-1]["explanation"] == "The line was: Veien var lang."
    deck = json.loads(service.store.get_session_row(session_id).deck_json)
    assert deck["targets"][1]["status"] == "active"
    assert purposes == ["prepare"]
    assert completes["n"] == 0
    buddy = [item["text"] for item in stored if item["speaker"] == "buddy"]
    assert buddy[-1] == "Veien var lang."

    emitted.clear()
    service.perform_text(session_id, "fortsatt feil", emitted.append)
    assert emitted[1]["feedback"] == "miss"
    assert emitted[1]["phrase"] == "Vannet var kaldt."
    deck = json.loads(service.store.get_session_row(session_id).deck_json)
    assert deck["targets"][1]["status"] == "missed"
    assert deck["targets"][2]["status"] == "active"
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    heard = [item for item in stored if item["speaker"] == "human"]
    assert heard[-1]["text"] == "fortsatt feil"
    assert heard[-1]["verdict"] == "wrong"
    assert heard[-1]["explanation"] == "The line was: Veien var lang."
    assert heard[-2]["explanation"] == "The line was: Veien var lang."

    emitted.clear()
    service.perform_text(session_id, "feil igjen", emitted.append)
    assert emitted[1]["feedback"] == "miss"
    assert emitted[1]["phrase"] == "Vannet var kaldt."
    assert emitted[1]["miss_note"]["verdict"] == "wrong"
    assert emitted[1]["miss_note"]["explanation"] == "The line was: Vannet var kaldt."


def test_norsk_prompts_load_for_a_listed_game(tmp_path):
    service = SessionService(Store(tmp_path / "echo-nb.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    text = (ROOT / "config" / "raw_materials" / "nb" / "norway_vacation_tunnels_fjords.txt").read_text(encoding="utf-8")
    phrases = [
        "Veien gikk gjennom lange tunneler",
        "Vi stoppet over en fjord",
        "Jeg tenker fortsatt på den kalde luften",
        "hvor grønne skråningene var",
    ]
    for phrase in phrases:
        assert phrase in text
    _bind(service, phrases)
    session_id = service.select(
        "user-local",
        "nb",
        "norway_vacation_tunnels_fjords",
        "lucas",
        game_id="echo_chamber",
    )
    listed = {item["id"]: item for item in service.catalog("user-local", "nb")["games"]}
    assert listed["echo_chamber"]["title"] == "EkkoGame"
    assert service.describe(session_id)["game"]["phrase"] == phrases[0]


def _counting_complete(calls: list[str]):
    def complete(user: str, *, system: str, **kwargs):
        calls.append(user)
        return fake_complete(user, system=system, **kwargs)

    return complete


def _buddy_lines(service: SessionService, session_id: str) -> list[str]:
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    return [item["text"] for item in stored if item["speaker"] == "buddy"]


def test_the_last_hit_speaks_the_closing_and_not_the_same_line(tmp_path):
    service = _service(tmp_path)
    _bind(service, LINES[:4])
    calls: list[str] = []
    service.complete_fn = _counting_complete(calls)
    session_id = _select(service)
    for line in LINES[:3]:
        service.perform_text(session_id, line, [].append)
    emitted: list[dict] = []
    service.perform_text(session_id, LINES[3], emitted.append)
    game = [item for item in emitted if item["type"] == "game"][0]
    assert game["finished"] is True
    assert game["feedback"] == "match"
    assert game["matches"] == 4
    assert game["total"] == 4
    assert [item["type"] for item in emitted].count("actor") == 1
    buddy = _buddy_lines(service, session_id)
    assert " ".join(buddy[-2:]) == "That was the last line. You got 4 of 4."
    assert buddy.count(LINES[3]) == 1
    assert calls == []


def test_a_second_miss_on_the_last_line_also_closes_with_the_tally(tmp_path):
    service = _service(tmp_path)
    _bind(service, LINES[:4])
    session_id = _select(service)
    for line in LINES[:3]:
        service.perform_text(session_id, line, [].append)
    service.perform_text(session_id, "feil", [].append)
    assert _buddy_lines(service, session_id)[-1] == LINES[3]
    emitted: list[dict] = []
    service.perform_text(session_id, "feil igjen", emitted.append)
    game = [item for item in emitted if item["type"] == "game"][0]
    assert game["finished"] is True
    assert game["feedback"] == "miss"
    assert " ".join(_buddy_lines(service, session_id)[-2:]) == "That was the last line. You got 3 of 4."


def test_a_turn_after_the_round_is_refused_and_calls_no_model(tmp_path):
    service = _service(tmp_path)
    _bind(service, LINES[:4])
    calls: list[str] = []
    service.complete_fn = _counting_complete(calls)
    session_id = _select(service)
    for line in LINES[:4]:
        service.perform_text(session_id, line, [].append)
    before = service.store.get_session_row(session_id).sentences_json
    for _ in range(2):
        emitted: list[dict] = []
        service.perform_text(session_id, LINES[3], emitted.append)
        assert [item["type"] for item in emitted] == ["game"]
        assert emitted[0]["finished"] is True
        assert emitted[0]["feedback"] == ""
    assert service.store.get_session_row(session_id).sentences_json == before
    assert calls == []


def test_a_miss_keeps_the_expected_line_for_the_word_diff(tmp_path):
    service = _service(tmp_path)
    _bind(service, LINES[:4])
    session_id = _select(service)
    emitted: list[dict] = []
    service.perform_text(session_id, "Jeg er slitten.", emitted.append)
    note = [item for item in emitted if item["type"] == "game"][0]["miss_note"]
    assert note["expected"] == "Jeg er sliten."
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    human = [item for item in stored if item["speaker"] == "human"][-1]
    assert human["text"] == "Jeg er slitten."
    assert human["expected"] == "Jeg er sliten."
    assert human["verdict"] == "wrong"
    assert _buddy_lines(service, session_id)[-1] == "Jeg er sliten."
