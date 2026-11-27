"""Stage U, H16: catalog metadata for the game picker. Availability, reasons, tags, options, and the last round."""

import json

import pytest
from sqlmodel import select

from logoskittens.games.echo_chamber import EchoPlugin
from logoskittens.games.host import NEED_TARGET, WREN_OFF, game_options, listed_games
from logoskittens.games.models import GameManifest
from logoskittens.persistence import SessionRow, Store
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete

from test_game_echo import LINES, SOURCE, _deck


def _service(tmp_path, wren=True) -> SessionService:
    service = SessionService(Store(tmp_path / "picker.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.store.save_logoscat_material(
        "logoscat-77", logoscat_user_id=1, workspace_session_id=77, language="en", title="Echo", text=SOURCE
    )
    if wren:
        service.wren_fn = lambda user, *, system="", purpose="", game_id="": _deck(LINES[:4])
    return service


def _manifest_with(**change) -> GameManifest:
    manifest = EchoPlugin().load_manifest()
    return manifest.model_copy(update=change)


def test_every_listed_game_carries_summary_tags_next_and_availability(tmp_path):
    service = _service(tmp_path)
    rows = {item["id"]: item for item in service.catalog("user-local", "nb")["games"]}
    assert {"echo_chamber", "fill_blank", "interviewer", "listen", "word_order", "cue_card"} <= set(rows)
    echo = rows["echo_chamber"]
    assert echo["title"] == "EkkoGame"
    assert echo["summary"] == "Hør en linje fra teksten og si den tilbake."
    assert echo["available"] is True and echo["reason"] == ""
    assert echo["next"] == "word_order"
    assert echo["last"] is None
    assert rows["interviewer"]["tags"] == ["Judge"]
    assert rows["echo_chamber"]["tags"] == []
    # English summaries are their own text.
    english = {item["id"]: item for item in service.catalog("user-local", "en")["games"]}
    assert english["echo_chamber"]["summary"] != echo["summary"]


def test_wren_off_lists_the_game_disabled_with_its_reason(tmp_path):
    service = _service(tmp_path, wren=False)
    rows = service.catalog("user-local", "en")["games"]
    assert rows, "a game whose prompts exist stays listed"
    remote = [item for item in rows if item["id"] != "word_order"]
    assert remote and all(item["available"] is False and item["reason"] == WREN_OFF for item in remote)
    # A local deck (H9) needs no Wren.
    local = [item for item in rows if item["id"] == "word_order"]
    assert local and local[0]["available"] is True and local[0]["reason"] == ""
    with pytest.raises(ValueError, match="Wren is not available"):
        service.select("user-local", "en", "logoscat-77", "peter", game_id="echo_chamber")


def test_a_game_that_needs_a_target_is_disabled_without_one_and_refused_at_select(tmp_path, monkeypatch):
    service = _service(tmp_path)
    needs = _manifest_with(requires=["wren", "targets"])
    monkeypatch.setattr(EchoPlugin, "load_manifest", lambda self: needs)
    without = {item["id"]: item for item in service.catalog("user-local", "en")["games"]}["echo_chamber"]
    assert without["available"] is False and without["reason"] == NEED_TARGET
    assert "Translate" in without["tags"]
    chosen = {item["id"]: item for item in service.catalog("user-local", "en", targets=["nb"])["games"]}
    assert chosen["echo_chamber"]["available"] is True
    # The source is never a target, so choosing only the source is still no target.
    same = {item["id"]: item for item in service.catalog("user-local", "en", targets=["en"])["games"]}
    assert same["echo_chamber"]["available"] is False
    with service.store.open() as db:
        before = len(db.exec(select(SessionRow)).all())
    with pytest.raises(ValueError, match=NEED_TARGET):
        service.select("user-local", "en", "logoscat-77", "peter", game_id="echo_chamber")
    with service.store.open() as db:
        assert len(db.exec(select(SessionRow)).all()) == before
    service.select("user-local", "en", "logoscat-77", "peter", game_id="echo_chamber", target_languages=["nb"])


def test_options_are_listed_with_labels_and_select_keeps_only_declared_values(tmp_path, monkeypatch):
    option = {
        "name": "cue_mode",
        "values": ["meaning", "translation"],
        "default": "meaning",
        "labels": {"en": {"meaning": "Meaning", "translation": "Translation"}},
    }
    manifest = GameManifest.model_validate({**_manifest_with().model_dump(), "options": [option]})
    monkeypatch.setattr(EchoPlugin, "load_manifest", lambda self: manifest)
    rows = {item["id"]: item for item in listed_games("en")}
    assert rows["echo_chamber"]["options"] == [
        {
            "name": "cue_mode",
            "values": ["meaning", "translation"],
            "default": "meaning",
            "labels": {"meaning": "Meaning", "translation": "Translation"},
        }
    ]
    assert game_options(manifest, {"cue_mode": "translation", "extra": "x"}) == {"cue_mode": "translation"}
    assert game_options(manifest, {"cue_mode": "nonsense"}) == {"cue_mode": "meaning"}
    assert game_options(manifest, None) == {"cue_mode": "meaning"}
    with pytest.raises(ValueError):
        GameManifest.model_validate(
            {**_manifest_with().model_dump(), "options": [{**option, "default": "spoken"}]}
        )


def test_last_is_the_newest_closed_round_on_this_material(tmp_path):
    service = _service(tmp_path)
    first = service.select("user-local", "en", "logoscat-77", "peter", game_id="echo_chamber")
    for line in LINES[:3]:
        service.perform_text(first, line, lambda _payload: None)
    service.perform_text(first, "feil", lambda _payload: None)
    service.perform_text(first, "feil igjen", lambda _payload: None)
    rows = {item["id"]: item for item in service.catalog("user-local", "en", "logoscat-77")["games"]}
    assert rows["echo_chamber"]["last"] == {"hit": 3, "total": 4}
    assert rows["fill_blank"]["last"] is None
    # A newer round still open does not hide the last closed one.
    service.select("user-local", "en", "logoscat-77", "peter", game_id="echo_chamber")
    rows = {item["id"]: item for item in service.catalog("user-local", "en", "logoscat-77")["games"]}
    assert rows["echo_chamber"]["last"] == {"hit": 3, "total": 4}
    # Another material has its own history.
    other = {item["id"]: item for item in service.catalog("user-local", "en", "friendly_chat")["games"]}
    assert other["echo_chamber"]["last"] is None
    described = service.describe(first)
    assert {item["id"]: item for item in described["games"]}["echo_chamber"]["last"] == {"hit": 3, "total": 4}
    assert json.loads(service.store.get_session_row(first).deck_json)["targets"][3]["status"] == "missed"


def test_read_text_is_open_while_playing_only_where_the_answers_are_the_texts_words():
    from logoskittens.games.host import listed_games

    rows = {item["id"]: item["read_text"] for item in listed_games("nb")}
    # Hearing or rebuilding the text is the exercise: the card offers it once the round is over.
    for game_id in ("listen", "overhear", "word_order", "review"):
        assert rows[game_id] == "between", game_id
    for game_id in ("cue_card", "fill_blank", "taboo", "paraphrase", "play_dumb", "roleplay", "echo_chamber"):
        assert rows[game_id] == "play", game_id
