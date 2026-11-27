"""Passage words for the recognizer bias."""

from logoskittens.stt_bias import bias_prompt, bias_words, expected_hearing


def test_words_keep_ferries_and_drop_repeats():
    text = (
        "We watched the ferries cross. The ferries were quiet. "
        "Between the tunnels the fjords opened."
    )
    words = bias_words(text)
    assert words[0] == "watched"
    assert "ferries" in words
    assert "fjords" in words
    assert words.count("ferries") == 1
    assert "we" not in [word.casefold() for word in words]
    assert bias_prompt("ferries", text).startswith("ferries, ")


def test_bias_is_the_answer_sentence_not_the_question():
    passage = (
        "We stopped above a fjord and watched the ferries cross. "
        "The road went through long tunnels."
    )
    question = "What did we watch cross after we stopped above a fjord?"
    prompt = expected_hearing("ferries", passage)
    assert prompt == "We stopped above a fjord and watched the ferries cross."
    assert "tunnels" not in prompt.casefold()
    assert question not in prompt
