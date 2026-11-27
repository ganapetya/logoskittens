"""ReviewGame (H9 `history`). Earlier targets of this user in this language: missed first, then old hits."""

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from logoskittens.games.host import NEED_HISTORY, history_targets, listed_games
from logoskittens.persistence import SessionRow, Store
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete
from phase2 import SOURCE, Wren, deck_of, prompts_differ, turn

FJORD = "Vi gikk langs fjorden i regnet. Bølgene slo mot steinene."


def _service(tmp_path) -> SessionService:
    service = SessionService(Store(tmp_path / "review.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.store.save_logoscat_material(
        "logoscat-41", logoscat_user_id=1, workspace_session_id=41, language="nb", title="Norgesferie", text=SOURCE
    )
    service.store.save_logoscat_material(
        "logoscat-42", logoscat_user_id=1, workspace_session_id=42, language="nb", title="Fjordtur", text=FJORD
    )

    def complete(user, *, system, **kwargs):
        raise AssertionError("ReviewGame does not call the local partner")

    service.complete_fn = complete
    return service


def _past(service, session_id, game_id, material_id, rows, days_ago=0, user_id="user-local", language="nb"):
    deck = {
        "deck_version": 1,
        "game_id": game_id,
        "language": language,
        "material_id": material_id,
        "targets": [
            {"id": f"t{index}", "phrase": phrase, "status": status, "stem": "?", "retry_line": "?"}
            for index, (phrase, status) in enumerate(rows, start=1)
        ],
    }
    service.store.create_session(
        session_id,
        "talking_game",
        {},
        user_id=user_id,
        language_id=language,
        material_id=material_id,
        game_id=game_id,
        deck_json=json.dumps(deck),
    )
    if days_ago:
        with service.store.open() as db:
            row = db.get(SessionRow, session_id)
            row.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
            db.add(row)
            db.commit()


def _rows(service) -> int:
    with service.store.open() as db:
        return len(db.exec(select(SessionRow)).all())


def _cards(phrases):
    return {
        "targets": [
            {
                "phrase": phrase,
                "instruction": f"Betydning nummer {index}.",
                "stem": f"Husker du stikkord {index}?",
                "retry_line": f"Stikkord {index}, en gang til.",
                "hint": "første",
                "forms": [],
            }
            for index, phrase in enumerate(phrases, start=1)
        ]
    }


def test_review_is_listed_and_its_prompts_are_per_language():
    prompts_differ("review")
    assert {item["id"]: item for item in listed_games("nb")}["review"]["title"] == "RepetisjonGame"


def test_fewer_than_three_earlier_targets_fails_select_with_no_row(tmp_path):
    service = _service(tmp_path)
    service.wren_fn = Wren(_cards(["lange tunneler"]))
    _past(service, "sess-a", "fill_blank", "logoscat-41", [("lange tunneler", "missed"), ("helt utslitt", "hit")])
    before = _rows(service)
    with pytest.raises(ValueError, match=NEED_HISTORY):
        service.select("user-local", "nb", "logoscat-41", "lucas", game_id="review")
    assert _rows(service) == before
    assert service.wren_fn.calls == []


def test_missed_targets_come_first_then_hits_older_than_three_days(tmp_path):
    service = _service(tmp_path)
    # Oldest first. A recent hit does not come back. A newer verdict on the same chunk wins.
    _past(service, "sess-1", "fill_blank", "logoscat-41", [("helt utslitt", "hit"), ("over en fjord", "missed")], days_ago=9)
    _past(service, "sess-2", "echo_chamber", "logoscat-42", [("i regnet", "hit"), ("mot steinene", "pending")], days_ago=5)
    _past(service, "sess-3", "cue_card", "logoscat-41", [("lange tunneler", "missed"), ("den kalde luften", "hit")])
    _past(service, "sess-4", "taboo", "logoscat-41", [("over en fjord", "hit")])
    # Another user, another language, and ReviewGame's own rounds are not read.
    _past(service, "sess-5", "fill_blank", "logoscat-41", [("i juli", "missed")], user_id="someone")
    _past(service, "sess-6", "review", "logoscat-41", [("Norge", "missed")])
    entries = history_targets(service, "user-local", "nb")
    assert [(item["phrase"], item["status"]) for item in entries] == [
        ("lange tunneler", "missed"),
        ("i regnet", "hit"),
        ("helt utslitt", "hit"),
    ]
    assert entries[1]["origin"] == "Fjordtur" and entries[1]["passage"] == FJORD

    wren = Wren(_cards(["helt utslitt", "lange tunneler", "i regnet", "et nytt uttrykk"]))
    service.wren_fn = wren
    # The panel's material is a different text. It is not read.
    session_id = service.select("user-local", "nb", "logoscat-42", "lucas", game_id="review")
    prompt = wren.calls[0][1]
    assert "1. phrase: lange tunneler" in prompt and "status: missed" in prompt
    assert "[Fjordtur]" in prompt and "[Norgesferie]" in prompt
    targets = deck_of(service, session_id)["targets"]
    # The history order is kept, a chunk Wren made up is dropped, and each card names its source.
    assert [target["phrase"] for target in targets] == ["lange tunneler", "i regnet", "helt utslitt"]
    assert [target["origin"] for target in targets] == ["Norgesferie", "Fjordtur", "Norgesferie"]
    game = service.describe(session_id)["game"]
    assert game["origin"] == "Norgesferie"
    assert game["instruction"] == "Betydning nummer 2."
    game, _actors = turn(service, session_id, "lange tunneler")
    assert game["feedback"] == "match" and game["origin"] == "Fjordtur"
    assert [purpose for purpose, _user in wren.calls] == ["prepare"]
