"""ParaphraseChallengerGame. A line with a form hits with no Wren call. A reworded right answer is judged."""

from logoskittens.games.host import listed_games

from phase2 import Wren, prompts_differ, start, stored, turn

DECK = {
    "targets": [
        {
            "phrase": "lange tunneler",
            "forms": ["lang tunnel", "de lange tunnelene"],
            "instruction": "Si deg enig, med ordene teksten bruker.",
            "stem": "Vi kjørte mye under fjellene.",
            "retry_line": "Under fjellene, ja. Hva kjørte vi gjennom?",
            "hint": "lange",
        },
        {
            "phrase": "den kalde luften",
            "forms": ["kald luft"],
            "instruction": "Si deg enig, med ordene teksten bruker.",
            "stem": "Det var ganske kjølig der.",
            "retry_line": "Kjølig, ja. Hva husker du?",
            "hint": "den",
        },
        {
            "phrase": "helt utslitt",
            "instruction": "Si deg enig, med ordene teksten bruker.",
            "stem": "Vi var trøtte om kvelden.",
            "retry_line": "Trøtte, ja. Hvor trøtte?",
            "hint": "helt",
        },
    ]
}


def test_paraphrase_is_listed_and_its_prompts_are_per_language():
    prompts_differ("paraphrase", roles=("wren", "judge"))
    rows = {item["id"]: item for item in listed_games("nb")}
    assert rows["paraphrase"]["title"] == "OmskrivGame"
    assert rows["paraphrase"]["tags"] == ["Judge"]


def test_a_form_hits_with_no_wren_call_and_a_reworded_answer_is_judged(tmp_path):
    wren = Wren(DECK, verdicts=[False, True])
    service, session_id = start(tmp_path, "paraphrase", wren)
    assert stored(service, session_id, "buddy")[0]["text"] == "Vi kjørte mye under fjellene."
    game, _actors = turn(service, session_id, "Ja, gjennom de lange tunnelene.")
    assert game["feedback"] == "match"
    assert wren.judged() == []
    # Her plain words back are judged, and are a miss. The hint shows, and the note keeps the chunk hidden.
    game, _actors = turn(service, session_id, "Ja, det var kjølig.")
    assert game["feedback"] == "miss"
    assert len(wren.judged()) == 1
    assert "expected: den kalde luften" in wren.judged()[0]
    assert "forms: kald luft" in wren.judged()[0]
    assert "last_try: no" in wren.judged()[0]
    assert game["hint"] == "den"
    assert game["miss_note"]["explanation"] == "Not quite. Try again."
    # A reworded answer the contains check misses is judged a hit.
    game, _actors = turn(service, session_id, "Ja, lufta var så kald.")
    assert game["feedback"] == "match"
    assert "last_try: yes" in wren.judged()[1]
    assert stored(service, session_id, "buddy")[-1]["text"] == "Vi var trøtte om kvelden."
