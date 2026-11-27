"""Stage I: RoleplayGame and the open-talk host. H1 history, H4 closed rounds and the turn count, H5 Finish, H7 passage."""

import base64
import json

from logoskittens.games.host import listed_games, partner_user
from logoskittens.games.models import GameDeck
from logoskittens.persistence import Store
from logoskittens.session import SessionService
from logoskittens.talk import SpokenSentence
from logoskittens.wire import decode

from fakes import FakeAudio, fake_complete
from phase2 import SOURCE, Wren, deck_of, prompts_differ, stored

from test_game_echo import LINES, SOURCE as ECHO_SOURCE, _deck as echo_deck

SCENE = "Du står ved billettluka på fergekaia, og hun selger billettene."
DECK = {
    "scene": SCENE,
    "targets": [
        {"phrase": "lange tunneler", "forms": ["lang tunnel"], "prompt_to_partner": "Spør hvordan veien hit var."},
        {"phrase": "over en fjord", "prompt_to_partner": "Spør hvor de stoppet i går."},
        {"phrase": "helt utslitt", "forms": ["helt utslitte"], "prompt_to_partner": "Spør om de er trøtte."},
    ],
}


class Partner:
    """The local partner. Records each call and answers with a numbered line."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def __call__(self, user: str, *, system: str, **kwargs):
        del kwargs
        self.calls.append((user, system))
        return fake_complete("", system="")[0].replace("The light", f"Linje {len(self.calls)}. The light"), None


def _start(tmp_path, cap=None):
    service = SessionService(Store(tmp_path / "roleplay.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.store.save_logoscat_material(
        "logoscat-41", logoscat_user_id=1, workspace_session_id=41, language="nb", title="Norgesferie", text=SOURCE
    )
    wren = Wren(DECK)
    service.wren_fn = wren
    partner = Partner()
    service.complete_fn = partner
    session_id = service.select("user-local", "nb", "logoscat-41", "lucas", game_id="roleplay")
    if cap is not None:
        row = service.store.get_session_row(session_id)
        state = json.loads(row.game_state_json)
        state["turn_cap"] = cap
        service.store.save_game(session_id, row.deck_json, json.dumps(state), row.wren_note or "")
    return service, session_id, wren, partner


def _turn(service, session_id, text):
    emitted: list[dict] = []
    service.perform_text(session_id, text, emitted.append)
    games = [item for item in emitted if item["type"] == "game"]
    actors = [item for item in emitted if item["type"] == "actor"]
    return (games[0] if games else None), actors


def test_roleplay_is_listed_with_its_prompts():
    prompts_differ("roleplay", roles=("wren", "partner"))
    row = {item["id"]: item for item in listed_games("nb")}["roleplay"]
    assert row["title"] == "RollespillGame" and row["phase"] == 3
    assert "Partner" in row["tags"]


def test_the_partner_sees_the_history_the_passage_and_the_steer(tmp_path):
    service, session_id, wren, partner = _start(tmp_path)
    # The opening: the scene is the user message. The passage and the first steer are in the system prompt (H7).
    opening_user, opening_system = partner.calls[0]
    assert opening_user == SCENE
    assert "passage:\n" + SOURCE in opening_system
    assert "Spør hvordan veien hit var." in opening_system
    described = service.describe(session_id)["game"]
    assert described["instruction"] == SCENE and described["source"] == ""
    assert [row["text"] for row in described["quest"]] == ["lange tunneler", "over en fjord", "helt utslitt"]
    assert described["finish"] is True

    _turn(service, session_id, "Hei, to billetter, takk.")
    user, system = partner.calls[-1]
    assert user.startswith("recent:\n- buddy: Linje 1.")
    assert user.endswith("latest_human: Hei, to billetter, takk.")
    assert "- human: Hei, to billetter" not in user
    assert "passage:\n" + SOURCE in system and "Spør hvordan veien hit var." in system
    # A chunk anywhere in the line marks its row, before the partner is called. The steer moves on.
    game, actors = _turn(service, session_id, "Vi kom gjennom lange tunneler, og jeg er helt utslitt.")
    assert game["feedback"] == "match"
    assert [row["status"] for row in game["quest"]] == ["hit", "active", "hit"]
    assert "Spør hvor de stoppet i går." in partner.calls[-1][1]
    assert len(actors) == 1
    # A line with no chunk is just talk: no miss, no verdict on the line.
    game, _actors = _turn(service, session_id, "Når går ferja?")
    assert game["feedback"] == ""
    assert stored(service, session_id, "human")[-1]["verdict"] == ""
    assert [purpose for purpose, _user in wren.calls] == ["prepare"]


def test_partner_history_is_the_last_eight_lines():
    lines = [SpokenSentence(speaker="buddy" if index % 2 else "human", text=f"l{index}", response_index=index // 2) for index in range(12)]
    lines.append(SpokenSentence(speaker="human", text="nå", response_index=99))
    user = partner_user(lines, "nå")
    assert user.splitlines()[1:9] == [f"- {'buddy' if index % 2 else 'human'}: l{index}" for index in range(4, 12)]
    assert user.splitlines()[-1] == "latest_human: nå"


def test_the_turn_at_the_cap_speaks_once_then_the_round_stays_closed(tmp_path):
    service, session_id, _wren, partner = _start(tmp_path, cap=2)
    _turn(service, session_id, "Hei.")
    calls = len(partner.calls)
    game, actors = _turn(service, session_id, "Vi kjørte gjennom lange tunneler.")
    assert game["finished"] is True and len(actors) == 1 and len(partner.calls) == calls + 1
    assert game["score"] == {"kind": "hits", "hit": 1, "total": 3}
    deck = deck_of(service, session_id)
    assert deck["closed"] is True and deck["targets"][1]["status"] in {"pending", "active"}
    # The next turn is refused: nothing stored, nobody speaks, the score is shown.
    before = len(stored(service, session_id, "human"))
    game, actors = _turn(service, session_id, "Over en fjord!")
    assert game["finished"] is True and actors == [] and len(partner.calls) == calls + 1
    assert game["score"] == {"kind": "hits", "hit": 1, "total": 3}
    assert len(stored(service, session_id, "human")) == before
    # On resume the round is still closed, with its score.
    resumed = service.describe(session_id)["game"]
    assert resumed["finished"] is True and resumed["score"] == {"kind": "hits", "hit": 1, "total": 3}


def test_finish_emits_a_hits_score_and_closes_the_round(tmp_path):
    service, session_id, wren, partner = _start(tmp_path)
    _turn(service, session_id, "Jeg er helt utslitt.")
    emitted: list[dict] = []
    calls = len(partner.calls)
    service.finish_game(session_id, emitted.append)
    (game,) = [item for item in emitted if item["type"] == "game"]
    assert game["finished"] is True and game["score"] == {"kind": "hits", "hit": 1, "total": 3}
    assert deck_of(service, session_id)["closed"] is True
    # Finish calls no model.
    assert len(partner.calls) == calls and [purpose for purpose, _user in wren.calls] == ["prepare"]
    game, actors = _turn(service, session_id, "lange tunneler")
    assert game["finished"] is True and actors == []


def test_echo_ignores_the_transcript_and_finish_does_not_close_it(tmp_path):
    service = SessionService(Store(tmp_path / "echo-finish.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.store.save_logoscat_material(
        "logoscat-77", logoscat_user_id=1, workspace_session_id=77, language="nb", title="Echo", text=ECHO_SOURCE
    )
    service.wren_fn = lambda user, *, system="", purpose="", game_id="": echo_deck(LINES[:4])
    session_id = service.select("user-local", "nb", "logoscat-77", "lucas", game_id="echo_chamber")
    emitted: list[dict] = []
    service.finish_game(session_id, emitted.append)
    (game,) = [item for item in emitted if item["type"] == "game"]
    assert game["finished"] is False and game["score"] is None and game["finish"] is False
    row = service.store.get_session_row(session_id)
    assert GameDeck.model_validate_json(row.deck_json).closed is False
    emitted = []
    service.perform_text(session_id, LINES[0], emitted.append)
    assert [item for item in emitted if item["type"] == "game"][0]["feedback"] == "match"
    actor = [item for item in emitted if item["type"] == "actor"][0]
    assert decode(base64.b64decode(actor["solutions"][0])).speech.text == LINES[1]
