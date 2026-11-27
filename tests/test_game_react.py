"""ReactGame (H8). The stem carries an emotion and a mimic token. A token not in the catalog is dropped; the line plays."""

import base64

import pytest

from logoskittens.games.host import listed_games
from logoskittens.wire import decode

from phase2 import SOURCE, Wren, deck_of, prompts_differ, start, turn

DECK = {
    "targets": [
        {
            "phrase": "helt utslitt",
            "forms": ["helt utslitte"],
            "instruction": "Hun klager over den lange dagen.",
            "stem": "For en dag! Jeg orker nesten ikke mer.",
            "retry_line": "Jeg orker ikke mer. Hvordan har du det?",
            "emotion": "encouragement",
            "mimic": "frustration",
        },
        {
            "phrase": "den kalde luften",
            "instruction": "Hun spør hva du husker best.",
            "stem": "Hva husker du best fra turen?",
            "retry_line": "Tenk på isbreen. Hva husker du?",
            "emotion": "curiosity",
            "mimic": "dance",
        },
        {
            "phrase": "lange tunneler",
            "instruction": "Hun lurer på veien.",
            "stem": "Var veien fin, da?",
            "retry_line": "Hva kjørte dere gjennom?",
            "emotion": "furious",
            "mimic": "curiosity",
        },
    ]
}


class Desk:
    def __init__(self):
        self.sent: list[tuple[str, list[str]]] = []

    def deliver(self, pcm, tokens=None, language="", role="buddy"):
        del pcm, language
        self.sent.append((role, list(tokens or [])))


def test_react_is_listed_and_its_prompts_are_per_language():
    prompts_differ("react", roles=("wren", "judge"))
    assert {item["id"]: item for item in listed_games("nb")}["react"]["title"] == "ReagerGame"


def test_the_token_rides_on_the_stem_and_an_unknown_token_is_dropped(tmp_path):
    service, session_id = start(tmp_path, "react", Wren(DECK))
    desk = Desk()
    service.deliver_pcm = desk.deliver
    service.botnet = lambda: True
    targets = deck_of(service, session_id)["targets"]
    # An emotion the avatar does not know is cleared. The token is kept until delivery checks it.
    assert [target["emotion"] for target in targets] == ["encouragement", "curiosity", ""]
    described = service.describe(session_id)["game"]
    assert described["instruction"] == "Hun klager over den lange dagen."
    # The text is on the card from the start (show_source), so the reactions can be found in it.
    assert described["source"] == SOURCE
    emitted: list[dict] = []
    service.voice_opening(session_id, emitted.append)
    assert desk.sent == [("buddy", ["frustration"])]
    opening = decode(base64.b64decode([item for item in emitted if item["type"] == "actor"][0]["solutions"][0]))
    assert opening.speech.text == "For en dag! Jeg orker nesten ikke mer."
    # The stem's emotion reaches the avatar.
    assert opening.emotion == "EMOTION_ENCOURAGEMENT"
    desk.sent.clear()
    game, actors = turn(service, session_id, "Ja, jeg er helt utslitt.")
    assert game["feedback"] == "match"
    # "dance" is not in config/mimic_tokens.json. The next stem still plays, with no token.
    assert desk.sent == [("buddy", [])]
    second = decode(base64.b64decode(actors[0]["solutions"][0]))
    assert second.speech.text == "Hva husker du best fra turen?"
    assert second.emotion == "EMOTION_CURIOSITY"


def test_a_text_with_too_few_reactions_does_not_start(tmp_path):
    with pytest.raises(ValueError, match="fewer than 3 reactions"):
        start(tmp_path, "react", Wren({"targets": DECK["targets"][:2]}))
