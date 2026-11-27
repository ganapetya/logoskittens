"""PlayDumbGame. She gets each fact wrong. A form hits with no Wren call. A reworded correction is judged."""

from logoskittens.games.host import listed_games

from phase2 import Wren, deck_of, prompts_differ, start, stored, turn

DECK = {
    "targets": [
        {
            "phrase": "lange tunneler",
            "forms": ["lang tunnel", "de lange tunnelene"],
            "stem": "Så veien gikk gjennom korte tunneler, ikke sant?",
            "retry_line": "Nei, jeg er sikker på at de var korte. Eller?",
        },
        {
            "phrase": "den kalde luften",
            "stem": "Du husker sikkert den varme luften der.",
            "retry_line": "Den var varm, ikke sant? Tenk på isbreen.",
        },
        {
            "phrase": "helt utslitt",
            "stem": "Om kvelden var dere helt opplagte.",
            "retry_line": "Opplagte, ja? Etter en så lang tur?",
        },
    ]
}


def test_play_dumb_is_listed_and_its_prompts_are_per_language():
    prompts_differ("play_dumb", roles=("wren", "judge"))
    rows = {item["id"]: item for item in listed_games("nb")}
    assert rows["play_dumb"]["title"] == "RettMegGame"


def test_a_form_hits_with_no_wren_call_and_a_reworded_correction_is_judged(tmp_path):
    wren = Wren(DECK, verdicts=[False, False, True], why="Riktig tanke. Bruk ordene fra teksten.")
    service, session_id = start(tmp_path, "play_dumb", wren)
    assert service.describe(session_id)["game"]["source"] == ""
    assert stored(service, session_id, "buddy")[0]["text"] == "Så veien gikk gjennom korte tunneler, ikke sant?"
    game, _actors = turn(service, session_id, "Nei, det var lange tunneler!")
    assert game["feedback"] == "match"
    assert wren.judged() == []
    # A correction in other words: the judge's why asks for the text's words, on every miss (show_why miss).
    game, _actors = turn(service, session_id, "Nei, den var kjølig.")
    assert game["feedback"] == "miss"
    assert game["miss_note"]["explanation"] == "Riktig tanke. Bruk ordene fra teksten."
    assert "den kalde luften" not in game["miss_note"]["explanation"]
    assert " ".join(item["text"] for item in stored(service, session_id, "buddy")[-2:]) == (
        "Den var varm, ikke sant? Tenk på isbreen."
    )
    # A bare no on the last try: missed, the phrase is revealed, the next wrong statement follows.
    game, _actors = turn(service, session_id, "Nei.")
    assert game["feedback"] == "miss"
    assert game["miss_note"]["expected"] == "den kalde luften"
    assert deck_of(service, session_id)["targets"][1]["status"] == "missed"
    assert stored(service, session_id, "buddy")[-1]["text"] == "Om kvelden var dere helt opplagte."
    game, _actors = turn(service, session_id, "Nei, vi var dødstrøtte, helt ferdige.")
    assert game["feedback"] == "match"
    assert game["finished"] is True
    assert " ".join(item["text"] for item in stored(service, session_id, "buddy")[-2:]) == (
        "Jeg må visst lese den igjen. Du rettet 2 av 3."
    )
