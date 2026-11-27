"""Stage G across the four phase 2 deck games: no turn calls the local partner, and the progression links them."""

import pytest

from logoskittens.games.host import listed_games

import test_game_ask_back
import test_game_paraphrase
import test_game_play_dumb
import test_game_taboo
from phase2 import Wren, start, turn

CASES = [
    ("taboo", test_game_taboo.DECK, ["Vi var veldig trøtte.", "hei", "Vi var helt utslitt.", "hull", "lange tunneler"]),
    ("paraphrase", test_game_paraphrase.DECK, ["hei", "nei", "lange tunneler", "kald luft", "helt utslitt"]),
    ("play_dumb", test_game_play_dumb.DECK, ["nei", "nei", "den kalde luften", "helt utslitt"]),
    ("ask_back", test_game_ask_back.DECK, ["Når?", "Hvor?", "Hva?", "Hvordan?", "Hvorfor?"]),
]


@pytest.mark.parametrize("game_id, deck, lines", CASES)
def test_no_turn_calls_the_local_partner(tmp_path, game_id, deck, lines):
    # start() binds a `complete` that raises. Every judge call is answered, then fails.
    service, session_id = start(tmp_path, game_id, Wren(deck, verdicts=[False, True] * 3))
    for line in lines:
        turn(service, session_id, line)


def test_phase_two_deck_games_are_listed_for_both_languages_and_linked():
    for language in ("en", "nb"):
        rows = {item["id"]: item for item in listed_games(language)}
        assert {"taboo", "paraphrase", "play_dumb", "ask_back"} <= set(rows)
        assert all(rows[game]["phase"] == 2 for game in ("taboo", "paraphrase", "play_dumb", "ask_back"))
    rows = {item["id"]: item for item in listed_games("nb")}
    assert rows["interviewer"]["next"] == "taboo"
    assert rows["taboo"]["next"] == "paraphrase"
    assert rows["paraphrase"]["next"] == "play_dumb"
    assert rows["play_dumb"]["next"] == "ask_back"
