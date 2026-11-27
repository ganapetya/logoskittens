"""AskBackGame. She says an answer. The user asks the question. Every turn is judged (H13). A failed judge is a miss."""

from logoskittens.games.host import listed_games

from phase2 import SOURCE, Wren, deck_of, prompts_differ, start, stored, turn

DECK = {
    "targets": [
        {"phrase": "i juli", "stem": "I juli.", "retry_line": "Prøv et spørsmål som begynner med «når»."},
        {"phrase": "i skyggen", "stem": "I skyggen.", "retry_line": "Prøv et spørsmål som begynner med «hvor»."},
        {
            "phrase": "den kalde luften",
            "stem": "Den kalde luften.",
            "retry_line": "Prøv et spørsmål som begynner med «hva».",
        },
        {"phrase": "helt utslitt", "stem": "Helt utslitt.", "retry_line": "Prøv et spørsmål med «hvordan»."},
    ]
}


def test_ask_back_is_listed_and_its_prompts_are_per_language():
    prompts_differ("ask_back", roles=("wren", "judge"))
    rows = {item["id"]: item for item in listed_games("nb")}
    assert rows["ask_back"]["title"] == "SpørTilbakeGame"
    assert rows["ask_back"]["tags"] == ["Judge"]


def test_every_turn_is_judged_and_a_failed_judge_is_a_miss(tmp_path):
    wren = Wren(DECK, verdicts=[True, False, False], why="Hvor så vannet nesten svart ut?")
    service, session_id = start(tmp_path, "ask_back", wren)
    # The stem holds the answer on purpose. The passage is on the card.
    assert deck_of(service, session_id)["targets"][0]["stem"] == "I juli."
    assert service.describe(session_id)["game"]["source"] == SOURCE
    # Even a line that holds the answer is judged: the contains check cannot score a question.
    game, _actors = turn(service, session_id, "Når reiste dere til Norge?")
    assert game["feedback"] == "match"
    assert len(wren.judged()) == 1
    game, _actors = turn(service, session_id, "Hvor vannet så svart ut i skyggen?")
    assert game["feedback"] == "miss" and len(wren.judged()) == 2
    # The first miss gives no model question (show_why final).
    assert game["miss_note"]["explanation"] == "Not quite. Try again."
    assert "last_try: no" in wren.judged()[1]
    assert " ".join(item["text"] for item in stored(service, session_id, "buddy")[-1:]) == (
        "Prøv et spørsmål som begynner med «hvor»."
    )
    # The final miss shows the judge's model question, then the passage sentence.
    game, _actors = turn(service, session_id, "Skyggen?")
    assert game["feedback"] == "miss" and "last_try: yes" in wren.judged()[2]
    assert game["miss_note"]["explanation"].startswith("Hvor så vannet nesten svart ut? The passage says: Vannet")
    # The judge is down: a miss, never a free hit.
    game, _actors = turn(service, session_id, "Hva husker du fortsatt?")
    assert game["feedback"] == "miss" and len(wren.judged()) == 4
    assert deck_of(service, session_id)["targets"][2]["status"] == "active"
