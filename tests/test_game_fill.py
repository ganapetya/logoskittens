"""FillInGame. Wren writes the lead-ins at prepare. Every line is a deck string. The turn calls no model."""

import json
from pathlib import Path

import pytest

from logoskittens.games.host import listed_games, load_game_prompt
from logoskittens.persistence import Store
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete


SOURCE = (
    "Vi kjørte gjennom lange tunneler før vi kom fram til fjorden. "
    "Der kjente vi den kalde luften fra isbreen. "
    "Om kvelden var vi helt utslitt etter turen."
)

# phrase, stem, retry_line, hint
TARGETS = [
    ("lange tunneler", "Vi kjørte gjennom", "Hva kjørte vi gjennom? Prøv igjen.", "To ord. Det første er lange."),
    ("den kalde luften", "Der kjente vi", "Hva kjente vi der? En gang til.", "Den begynner med den."),
    ("helt utslitt", "Om kvelden var vi", "Hvordan var vi om kvelden?", "Det første ordet er helt."),
]

ROOT = Path(__file__).resolve().parents[1]


def _deck(rows=None) -> str:
    chosen = rows if rows is not None else TARGETS
    return json.dumps(
        {
            "targets": [
                {
                    "id": f"t{index}",
                    "phrase": phrase,
                    "stem": stem,
                    "retry_line": retry,
                    "hint": hint,
                    "gloss": {"en": f"EN {phrase}"},
                }
                for index, (phrase, stem, retry, hint) in enumerate(chosen, start=1)
            ]
        }
    )


class Wren:
    def __init__(self, rows=None):
        self.rows = rows
        self.calls: list[tuple[str, str]] = []

    def __call__(self, user: str, *, system: str = "", purpose: str = "", game_id: str = ""):
        del system, game_id
        self.calls.append((purpose, user))
        if purpose != "prepare":
            raise AssertionError("FillInGame calls Wren only at prepare")
        return _deck(self.rows)


def _start(tmp_path, rows=None, targets=None):
    service = SessionService(Store(tmp_path / "fill.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.store.save_logoscat_material(
        "logoscat-21", logoscat_user_id=1, workspace_session_id=21, language="nb", title="Fjorden", text=SOURCE
    )
    wren = Wren(rows)
    service.wren_fn = wren

    def complete(user, *, system, **kwargs):
        raise AssertionError("FillInGame does not call the local partner")

    service.complete_fn = complete
    session_id = service.select(
        "user-local", "nb", "logoscat-21", "lucas", game_id="fill_blank", target_languages=targets or []
    )
    return service, session_id, wren


def _turn(service, session_id, text):
    emitted: list[dict] = []
    service.perform_text(session_id, text, emitted.append)
    games = [item for item in emitted if item["type"] == "game"]
    actors = [item for item in emitted if item["type"] == "actor"]
    return games[0], actors, emitted


def _stored(service, session_id, speaker):
    rows = json.loads(service.store.get_session_row(session_id).sentences_json)
    return [item for item in rows if item["speaker"] == speaker]


def test_prompts_are_per_language_and_the_game_is_listed():
    games = ROOT / "config" / "prompts" / "games"
    english = (games / "fill_blank_wren_en.md").read_text(encoding="utf-8")
    norsk = (games / "fill_blank_wren_nb.md").read_text(encoding="utf-8")
    assert english.strip() != norsk.strip()
    assert load_game_prompt("fill_blank", "wren", "nb") == norsk
    assert not (games / "fill_blank_partner_en.md").exists()
    rows = {item["id"]: item for item in listed_games("nb")}
    assert rows["fill_blank"]["title"] == "UtfyllingGame"
    assert {item["id"]: item for item in listed_games("en")}["fill_blank"]["title"] == "FillInGame"


def test_the_opening_is_the_first_stem_and_no_model_runs_on_it(tmp_path):
    service, session_id, wren = _start(tmp_path)
    assert [item["text"] for item in _stored(service, session_id, "buddy")] == ["Vi kjørte gjennom"]
    assert [purpose for purpose, _user in wren.calls] == ["prepare"]
    described = service.describe(session_id)
    assert described["game"]["phrase"] == ""
    assert described["game"]["hint"] == ""
    assert "lange tunneler" not in json.dumps(described["game"])


def test_a_hit_speaks_the_next_stem_and_the_last_hit_speaks_nothing(tmp_path):
    service, session_id, wren = _start(tmp_path)
    game, actors, emitted = _turn(service, session_id, "lange tunneler")
    assert game["feedback"] == "match"
    assert [item["type"] for item in emitted] == ["heard", "game", "actor"]
    assert len(actors) == 1
    assert _stored(service, session_id, "buddy")[-1]["text"] == "Der kjente vi"
    _turn(service, session_id, "den kalde luften")
    game, actors, _emitted = _turn(service, session_id, "Vi var helt utslitt.")
    assert game["feedback"] == "match"
    assert game["finished"] is True
    assert actors == []
    # The last hit has no closing line. FillInGame says nothing at the end.
    assert _stored(service, session_id, "buddy")[-1]["text"] == "Om kvelden var vi"
    assert [purpose for purpose, _user in wren.calls] == ["prepare"]
    # A turn after the round stores nothing and speaks nothing.
    before = len(_stored(service, session_id, "human"))
    game, actors, _emitted = _turn(service, session_id, "hei")
    assert game["finished"] is True and actors == []
    assert len(_stored(service, session_id, "human")) == before


def test_a_miss_shows_the_hint_and_speaks_the_retry_line(tmp_path):
    service, session_id, _wren = _start(tmp_path)
    game, actors, _emitted = _turn(service, session_id, "lange veier")
    assert game["feedback"] == "miss"
    assert game["hint"] == "To ord. Det første er lange."
    assert len(actors) == 1
    # The stored log splits her line into sentences.
    said = [item["text"] for item in _stored(service, session_id, "buddy")][-2:]
    assert " ".join(said) == "Hva kjørte vi gjennom? Prøv igjen."


def test_the_first_miss_hides_the_phrase_and_the_second_reveals_it(tmp_path):
    service, session_id, _wren = _start(tmp_path)
    game, _actors, _emitted = _turn(service, session_id, "mørke huler")
    assert "lange tunneler" not in json.dumps(game["miss_note"])
    assert "lange tunneler" not in game["feedback_text"]
    first = _stored(service, session_id, "human")[-1]
    assert first["text"] == "mørke huler"
    assert "lange tunneler" not in json.dumps(first)
    assert first["verdict"] == "wrong"
    game, actors, _emitted = _turn(service, session_id, "smale veier")
    assert game["miss_note"]["expected"] == "lange tunneler"
    assert "lange tunneler" in game["feedback_text"]
    second = _stored(service, session_id, "human")[-1]
    assert second["expected"] == "lange tunneler"
    # The target is missed, so the next line is the next stem. With no targets there is no gloss.
    assert _stored(service, session_id, "buddy")[-1]["text"] == "Der kjente vi"
    assert game["glosses"] == []


def test_a_synonym_is_a_miss_and_the_heard_text_is_stored_either_way(tmp_path):
    service, session_id, _wren = _start(tmp_path)
    game, _actors, _emitted = _turn(service, session_id, "lange tunnelene")
    assert game["feedback"] == "miss"
    assert _stored(service, session_id, "human")[-1]["text"] == "lange tunnelene"
    game, _actors, _emitted = _turn(service, session_id, "Ja, lange tunneler.")
    assert game["feedback"] == "match"
    assert _stored(service, session_id, "human")[-1]["text"] == "Ja, lange tunneler."


def test_glosses_show_when_a_target_closes(tmp_path):
    service, session_id, _wren = _start(tmp_path, targets=["en"])
    game, _actors, _emitted = _turn(service, session_id, "lange tunneler")
    assert game["glosses"] == [
        {"id": "t1", "phrase": "lange tunneler", "status": "hit", "gloss": {"en": "EN lange tunneler"}}
    ]


def test_a_stem_or_retry_with_the_phrase_and_a_revealing_hint_are_refused_at_prepare(tmp_path):
    rows = [
        ("lange tunneler", "Vi kjørte gjennom lange tunneler", "Prøv igjen.", ""),
        ("den kalde luften", "Der kjente vi", "Si den kalde luften.", ""),
        ("helt utslitt", "Om kvelden var vi", "Hvordan var vi?", "Svaret er helt utslitt."),
    ]
    with pytest.raises(ValueError, match="grounded 1"):
        _start(tmp_path, rows=rows)
    service, session_id, _wren = _start(tmp_path / "ok", rows=TARGETS[:2] + [rows[2]])
    game, _actors, _emitted = _turn(service, session_id, "feil")
    assert game["hint"] == "To ord. Det første er lange."
    deck = json.loads(service.store.get_session_row(session_id).deck_json)
    assert deck["targets"][2]["hint"] == ""
