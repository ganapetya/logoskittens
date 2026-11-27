"""TabooGame. A banned word buzzes with no attempt. A clean line goes on to the contains check (H6)."""

from logoskittens.games.host import listed_games

from phase2 import Wren, deck_of, prompts_differ, start, stored, turn

DECK = {
    "targets": [
        {
            "phrase": "helt utslitt",
            "forms": ["helt utslitte"],
            "banned": ["trøtt", "veldig", "helt"],
            "instruction": "Ikke si «trøtt» eller «veldig».",
            "stem": "Hvordan hadde dere det om kvelden?",
            "retry_line": "Tenk på hvor slitne dere var. Hvordan var dere?",
            "hint": "helt",
        },
        {
            "phrase": "lange tunneler",
            "banned": ["hull"],
            "instruction": "Ikke si «hull».",
            "stem": "Hva gikk veien gjennom?",
            "retry_line": "Veien gikk under fjellet. Gjennom hva?",
            "hint": "lange",
        },
        {
            "phrase": "den kalde luften",
            "banned": ["kulda"],
            "instruction": "Ikke si «kulda».",
            "stem": "Hva husker du fortsatt?",
            "retry_line": "Noe du kjente på huden. Hva?",
            "hint": "den",
        },
        {
            # No ban on the card: dropped.
            "phrase": "over en fjord",
            "banned": ["vann"],
            "instruction": "",
            "stem": "Hvor stoppet dere?",
            "retry_line": "Om morgenen. Hvor?",
        },
    ]
}


def test_taboo_is_listed_and_its_prompts_are_per_language():
    prompts_differ("taboo")
    rows = {item["id"]: item for item in listed_games("nb")}
    assert rows["taboo"]["title"] == "TabuGame" and rows["taboo"]["phase"] == 2


def test_a_banned_word_buzzes_with_no_attempt_and_a_clean_miss_hints(tmp_path):
    wren = Wren(DECK)
    service, session_id = start(tmp_path, "taboo", wren)
    deck = deck_of(service, session_id)
    assert [target["phrase"] for target in deck["targets"]] == ["helt utslitt", "lange tunneler", "den kalde luften"]
    # "helt" is a word of the chunk, so it is not banned. The right answer never buzzes.
    assert deck["targets"][0]["banned"] == ["trøtt", "veldig"]
    described = service.describe(session_id)["game"]
    assert described["instruction"] == "Ikke si «trøtt» eller «veldig»."

    game, actors = turn(service, session_id, "Vi var veldig trøtte.")
    assert game["buzzer"] is True and game["withheld"] is True
    assert game["misses"] == 0 and actors == []
    # The buzzed line is stored. She does not speak, and the user speaks again.
    assert stored(service, session_id, "human")[-1]["text"] == "Vi var veldig trøtte."
    assert stored(service, session_id, "buddy")[-1]["text"] == "Hvordan hadde dere det om kvelden?"

    game, actors = turn(service, session_id, "Vi var slitne.")
    assert game["feedback"] == "miss" and game["buzzer"] is False
    assert game["misses"] == 1
    assert game["hint"] == "helt"
    assert len(actors) == 1
    said = " ".join(item["text"] for item in stored(service, session_id, "buddy")[-2:])
    assert said == "Tenk på hvor slitne dere var. Hvordan var dere?"

    game, _actors = turn(service, session_id, "Vi var helt utslitte.")
    assert game["feedback"] == "match"
    assert stored(service, session_id, "buddy")[-1]["text"] == "Hva gikk veien gjennom?"
    assert wren.judged() == []
