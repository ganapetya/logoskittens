"""Free-speech subject card, sentence window, and one buddy line."""

import json

import pytest

from logoskittens.content import prompt_text, reset
from logoskittens.graph import run_buddy_turn, run_prepare
from logoskittens.llm import LLMError

from logoskittens.talk import SpokenSentence, buddy_reply, last_sentences, ongoing_for, split_sentences
from logoskittens.actors import load_actors

from fakes import SUBJECT, fake_complete


def test_eight_sentences_are_kept_and_the_older_ones_drop():
    sentences = [SpokenSentence(speaker="human", text=f"line {index}") for index in range(10)]
    window = last_sentences(sentences)
    assert len(window) == 8
    assert window[0].text == "line 2"
    assert window[-1].text == "line 9"


def test_a_fragment_is_one_sentence_and_a_stop_splits():
    assert split_sentences("yes") == ["yes"]
    assert split_sentences("The tunnel was long. The fjord was bright.") == [
        "The tunnel was long.",
        "The fjord was bright.",
    ]


def test_summarize_runs_once_and_a_passive_line_still_returns_a_buddy_line():
    card = run_prepare("Last summer we took a vacation.", "en", fake_complete)
    assert card.significant_words == ["tunnels", "fjords"]
    sentences = [SpokenSentence(speaker="human", text="yes")]
    ongoing = ongoing_for(card, sentences, "en")
    assert len(ongoing.recent) == 1
    solution = run_buddy_turn(ongoing, "yes", complete=fake_complete, actors=load_actors())
    assert solution.actor_id == "buddy-one"
    assert solution.speech.text
    assert solution.speech.language_code == "en"
    assert solution.speech.voice_model_id == "en_US-lessac-medium"
    assert solution.physical_gestures == []
    assert "buddy-two" not in solution.actor_id


def test_prose_is_not_a_subject_card():
    calls = {"n": 0}

    def broken(user: str, *, system: str, **kwargs):
        del user, system
        calls["n"] += 1
        if calls["n"] == 1:
            assert kwargs.get("num_predict") == 1024
        else:
            assert kwargs.get("think") == "off"
        from logoskittens.llm import ComparisonRecord

        return "I am not sure.", ComparisonRecord(
            backend="fake", model="fake", latency_ms=0, prompt_tokens=0, completion_tokens=0
        )

    with pytest.raises(LLMError, match="subject card was not JSON"):
        run_prepare("text", "en", broken)
    assert calls["n"] == 2


def test_a_truncated_buddy_object_still_parses():
    raw = '{"line": "The fjord was quiet.", "emotion": "curiosity"'

    def truncated(user: str, *, system: str, **kwargs):
        del user, system, kwargs
        from logoskittens.llm import ComparisonRecord

        return raw, ComparisonRecord(
            backend="fake", model="fake", latency_ms=0, prompt_tokens=0, completion_tokens=0
        )

    card = run_prepare("text", "en", fake_complete)
    solution = run_buddy_turn(
        ongoing_for(card, [SpokenSentence(speaker="human", text="yes")], "en"),
        "yes",
        complete=truncated,
        actors=load_actors(),
    )
    assert solution.speech.text == "The fjord was quiet."
    assert solution.emotion == "EMOTION_CURIOSITY"


def _record():
    from logoskittens.llm import ComparisonRecord

    return ComparisonRecord(backend="fake", model="fake", latency_ms=0, prompt_tokens=0, completion_tokens=0)


def test_a_think_block_and_a_text_key_still_count_as_a_line():
    ongoing = ongoing_for(
        run_prepare("text", "en", fake_complete),
        [SpokenSentence(speaker="human", text="yes")],
        "en",
    )

    def complete(user: str, *, system: str, **kwargs):
        del user, system, kwargs
        return (
            '<think>The human is quiet\n{"text": "The fjord stayed bright.", "emotion": "curiosity"}',
            _record(),
        )

    reply = buddy_reply(ongoing, "yes", complete)
    assert reply.line == "The fjord stayed bright."
    assert reply.emotion == "curiosity"


def test_a_plain_sentence_is_kept_and_a_cut_off_object_is_asked_again():
    ongoing = ongoing_for(
        run_prepare("text", "en", fake_complete),
        [SpokenSentence(speaker="human", text="yes")],
        "en",
    )
    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del system
        calls["n"] += 1
        if calls["n"] == 1:
            assert "Return one JSON" not in user
            return '{"line": "The tunnel", "emotion":', _record()
        assert kwargs.get("think") == "off"
        assert kwargs.get("num_predict") == 768
        return "The light opened onto the fjord.", _record()

    reply = buddy_reply(ongoing, "yes", complete)
    assert calls["n"] == 2
    assert reply.line == "The light opened onto the fjord."
    assert reply.emotion == "neutral"


def test_a_repeated_line_is_replaced_and_a_used_opening_is_hidden():
    from logoskittens.talk import LessonSubjectInput

    subject = LessonSubjectInput(
        used_words=["ferries", "fjords", "tunnels"],
        significant_words=["ferries", "fjords"],
        theme="A drive through tunnels and fjords.",
        small_talk_subjects=[
            "Did you ever drive through those mountain tunnels in Norway?",
            "Did you see any ferries crossing the fjords?",
        ],
    )
    ongoing = ongoing_for(
        subject,
        [
            SpokenSentence(speaker="human", text="It's always beautiful."),
            SpokenSentence(speaker="buddy", text="Did you see any ferries crossing the fjords?"),
        ],
        "en",
    )
    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del system
        calls["n"] += 1
        if calls["n"] == 1:
            offered = user.split("small_talk_subjects:")[1].split("do_not_repeat:")[0]
            banned = user.split("do_not_repeat:")[1].split("recent:")[0]
            assert "ferries crossing the fjords" not in offered
            assert "ferries crossing the fjords" in banned
            return '{"line": "Did you see any ferries crossing the fjords?", "emotion": "curiosity"}', _record()
        assert kwargs.get("think") == "off"
        assert "Do not say this again" in user
        return '{"line": "The water went dark where the mountain blocked the sun.", "emotion": "curiosity"}', _record()

    reply = buddy_reply(ongoing, "Yeah, I saw Ferris crossing the Fjords.", complete)
    assert calls["n"] == 2
    assert reply.line == "The water went dark where the mountain blocked the sun."


def test_two_repeats_fall_back_to_an_unused_opening():
    from logoskittens.talk import LessonSubjectInput

    subject = LessonSubjectInput(
        used_words=["ferries", "fjords"],
        significant_words=["ferries"],
        theme="A drive through tunnels and fjords.",
        small_talk_subjects=[
            "Did you ever drive through those mountain tunnels in Norway?",
            "Did you see any ferries crossing the fjords?",
        ],
    )
    ongoing = ongoing_for(
        subject,
        [SpokenSentence(speaker="buddy", text="Did you see any ferries crossing the fjords?")],
        "en",
    )

    def complete(user: str, *, system: str, **kwargs):
        del user, system, kwargs
        return '{"line": "Did you see any ferries crossing the fjords?", "emotion": "curiosity"}', _record()

    reply = buddy_reply(ongoing, "yes", complete)
    assert reply.line == "Did you ever drive through those mountain tunnels in Norway?"
    assert reply.emotion == "curiosity"


def test_a_nocaptions_token_is_silence_and_a_repeat_uses_an_opening():
    from logoskittens.talk import LessonSubjectInput, clean_transcript

    assert clean_transcript("<|nocaptions|>") == ""
    assert clean_transcript("Hei <|nocaptions|> der") == "Hei der"
    assert clean_transcript("[BLANK_AUDIO]") == ""
    assert clean_transcript("hello [BLANK_AUDIO]") == "hello"
    assert clean_transcript("The, road, went, through, long, tunnels") == (
        "The road went through long tunnels"
    )
    subject = LessonSubjectInput(
        used_words=["ferries", "fjords"],
        significant_words=["ferries"],
        theme="A drive through tunnels and fjords.",
        small_talk_subjects=[
            "Did you ever drive through those mountain tunnels in Norway?",
            "Did you see any ferries crossing the fjords?",
        ],
    )
    ongoing = ongoing_for(
        subject,
        [SpokenSentence(speaker="buddy", text="Did you see any ferries crossing the fjords?")],
        "en",
    )

    def complete(user: str, *, system: str, **kwargs):
        del user, system, kwargs
        return '{"line": "Did you see any ferries crossing the fjords?", "emotion": "curiosity"}', _record()

    reply = buddy_reply(ongoing, "The road was long.", complete)
    assert reply.line == "Did you ever drive through those mountain tunnels in Norway?"


def test_a_content_line_is_not_answered_with_a_card_question():
    from logoskittens.talk import LessonSubjectInput

    subject = LessonSubjectInput(
        used_words=["fjords", "water", "shade"],
        significant_words=["fjords", "water"],
        theme="A drive through tunnels and fjords.",
        small_talk_subjects=["What did the water look like in the shade?"],
    )
    ongoing = ongoing_for(subject, [SpokenSentence(speaker="human", text="I like Japan food more.")], "en")
    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del system
        calls["n"] += 1
        if calls["n"] == 1:
            assert "What did the water look like in the shade?" not in user
            assert 'The human brought this up: "I like Japan food more."' in user
            return (
                '{"line": "What did the water look like in the shade of the steep slopes?", "emotion": "curiosity"}',
                _record(),
            )
        assert kwargs.get("think") == "off"
        assert "I like Japan food more." in user
        return (
            '{"line": "Japan food is a different pleasure. The fjord water still looked black in the shade.", "emotion": "curiosity"}',
            _record(),
        )

    reply = buddy_reply(ongoing, "I like Japan food more.", complete)
    assert calls["n"] == 2
    assert reply.line.startswith("Japan food")


def test_peter_is_the_default_and_mary_names_herself():
    from logoskittens.personalities import get_personality
    from logoskittens.talk import buddy_user

    peter = get_personality("en", "")
    assert peter.id == "peter"
    assert get_personality("en", "jorge").id == "peter"
    assert peter.name == "Peter"
    assert peter.gender == "man"
    assert peter.mood == "energetic"
    assert peter.stance == "capitalist"
    assert peter.likes == ["steak", "a fight"]
    assert peter.voice_id == "en_US-ryan-medium"
    mary = get_personality("en", "mary")
    assert mary.gender == "woman"
    assert mary.nature == ""
    assert mary.alias == "Masha"
    assert peter.alias == ""
    assert peter.nature == ""
    assert mary.mood == "gentle"
    assert mary.home == "Venetian"
    assert mary.stance == "humanitarian"
    assert mary.likes == ["romance", "music", "flowers"]
    assert mary.voice_id == "en_US-lessac-medium"
    card = run_prepare("text", "en", fake_complete)
    mary_user = buddy_user(ongoing_for(card, [], "en", mary), "What is your name?")
    assert "name: Mary" in mary_user
    assert "home: Venetian" in mary_user
    assert "nature:" not in mary_user
    assert "spider" not in mary_user
    assert "alias: Masha" in mary_user
    # A profile may still set a nature; it reaches the prompt as one line.
    robot = mary.model_copy(update={"nature": "robot cat"})
    robot_user = buddy_user(ongoing_for(card, [], "en", robot), "What are you?")
    assert "nature: robot cat" in robot_user
    assert "Nature is what you are" in robot_user
    assert "romance" in mary_user
    peter_user = buddy_user(ongoing_for(card, [], "en", peter), "Do you like fish?")
    assert "name: Peter" in peter_user
    assert "steak" in peter_user
    assert "a fight" in peter_user
    assert "home:" not in peter_user
    assert "nature:" not in peter_user
    assert "alias:" not in peter_user
    assert "one short sentence" in peter_user
    assert "language_specifics:" in peter_user
    assert "person: 1st" in peter_user
    assert "gender: man" in peter_user
    assert "language_specifics:" in mary_user
    assert "person: 1st" in mary_user
    assert "gender: woman" in mary_user
    mary_line = run_buddy_turn(
        ongoing_for(card, [SpokenSentence(speaker="human", text="What is your name?")], "en", mary),
        "What is your name?",
        complete=fake_complete,
        actors=load_actors(),
    )
    peter_line = run_buddy_turn(
        ongoing_for(card, [SpokenSentence(speaker="human", text="What is your name?")], "en", peter),
        "What is your name?",
        complete=fake_complete,
        actors=load_actors(),
    )
    assert mary_line.speech.voice_model_id == "en_US-lessac-medium"
    assert peter_line.speech.voice_model_id == "en_US-ryan-medium"


def test_a_name_question_drops_the_theme_story():
    from logoskittens.personalities import get_personality
    from logoskittens.talk import LessonSubjectInput, buddy_user

    subject = LessonSubjectInput(
        used_words=["fjords", "tunnels", "water"],
        significant_words=["fjords", "water"],
        theme="A drive through tunnels and fjords.",
        small_talk_subjects=["What did the water look like in the shade?"],
    )
    mary = get_personality("en", "mary")
    ongoing = ongoing_for(subject, [], "en", mary)
    asked = buddy_user(ongoing, "Hello, what's your name?")
    assert "Answer that in one short sentence" in asked
    assert "Then add one detail from the theme" not in asked
    about_theme = buddy_user(ongoing, "What did the water look like?")
    assert "Answer that question" in about_theme
    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del system
        calls["n"] += 1
        if calls["n"] == 1:
            assert "Do not mention the theme" not in user
            return (
                '{"line": "My name is Mary. The fjords there were so beautiful.", "emotion": "neutral"}',
                _record(),
            )
        assert kwargs.get("think") == "off"
        assert "Do not mention the theme" in user
        return (
            '{"line": "My name is Mary. The fjords were still.", "emotion": "neutral"}',
            _record(),
        )

    reply = buddy_reply(ongoing, "Hello, what's your name?", complete)
    assert calls["n"] == 2
    assert reply.line == "My name is Mary."


def test_a_third_person_self_is_put_back_into_the_first_person():
    from logoskittens.personalities import get_personality
    from logoskittens.talk import LessonSubjectInput

    subject = LessonSubjectInput(
        used_words=["fjords", "money"],
        significant_words=["fjords"],
        theme="A drive through fjords.",
        small_talk_subjects=["What did the water look like?"],
    )
    peter = get_personality("en", "peter")
    ongoing = ongoing_for(subject, [], "en", peter)
    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del system
        calls["n"] += 1
        if calls["n"] == 1:
            assert "language_specifics:" in user
            assert "person: 1st" in user
            return (
                '{"line": "Money is a tool, Peter likes to use it to buy steak.", "emotion": "neutral"}',
                _record(),
            )
        assert "first person" in user
        return (
            '{"line": "Money is a tool, Peter likes to use it to buy steak.", "emotion": "neutral"}',
            _record(),
        )

    reply = buddy_reply(ongoing, "What do you think about money, Peter?", complete)
    assert calls["n"] == 2
    assert reply.line == "Money is a tool, I like to use it to buy steak."
    assert "Peter" not in reply.line


def test_a_side_track_stays_out_when_it_would_replace_the_human():
    from logoskittens.personalities import get_personality
    from logoskittens.talk import LessonSubjectInput, buddy_user, steer_landed

    subject = LessonSubjectInput(
        used_words=["fjords", "tunnels", "goats", "road"],
        significant_words=["fjords", "goats"],
        theme="A drive along the fjords, with goats by the road.",
        small_talk_subjects=["Did the goats watch the car?"],
    )
    mary = get_personality("en", "mary")
    steer = "Wonder if roadside goats watched the car more closely than the fjords did."
    recent = [SpokenSentence(speaker="buddy", text="I know you enjoy the stillness of a crowded place.")]
    ongoing = ongoing_for(subject, recent, "en", mary, bob_steer=steer)
    heard = buddy_user(ongoing, "I like to read fantasy books.")
    assert "roadside goats" in heard
    assert "private hint" in heard
    assert "roadside" in heard
    assert "Do not continue the previous detail" not in heard
    asked = buddy_user(ongoing, "What else?")
    assert "Answer that in one short sentence" in asked
    assert "side-track" not in asked
    assert steer_landed("I like a story with a long road and a quiet inn.", steer, ongoing) is False
    assert steer_landed("The light there is like the light on the Venetian canals.", "Compare the light on the fjords to the light on Venetian canals.", ongoing) is True
    from logoskittens.talk import steer_shows
    assert steer_shows("Fantasy books suit a quiet evening.", steer, "I like to read fantasy books.") is False
    assert steer_shows(
        "I like to read fantasy books, and the goats might have stories.",
        steer,
        "I like to read fantasy books.",
    ) is True

    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del system
        calls["n"] += 1
        if calls["n"] == 1:
            return (
                '{"line": "Fantasy books are a good road for me. Wonder if roadside goats watched the car more closely than the fjords did.", "emotion": "neutral"}',
                _record(),
            )
        raise AssertionError("the hint was already in the reply")

    reply = buddy_reply(ongoing, "I like to read fantasy books.", complete)
    assert calls["n"] == 1
    assert "fantasy books" in reply.line.casefold()
    assert "roadside" in reply.line.casefold()

    calls["n"] = 0

    def only_goats(user: str, *, system: str, **kwargs):
        del system
        calls["n"] += 1
        if calls["n"] == 1:
            return (
                '{"line": "I imagine the goats would have a better view of the road than the fjords do.", "emotion": "neutral"}',
                _record(),
            )
        assert kwargs.get("think") == "off"
        assert "roadside" in user
        assert "Do not copy their sentence" in user
        return (
            '{"line": "Fantasy books suit a long quiet evening.", "emotion": "neutral"}',
            _record(),
        )

    reply = buddy_reply(ongoing, "I like to read fantasy books.", only_goats)
    assert calls["n"] == 2
    assert "Fantasy books" in reply.line
    assert "goats" not in reply.line.casefold()


def test_a_question_hint_is_asked_after_the_answer():
    from logoskittens.personalities import get_personality
    from logoskittens.talk import LessonSubjectInput, buddy_user

    subject = LessonSubjectInput(
        used_words=["fjords", "lakes", "water"],
        significant_words=["lakes"],
        theme="A drive along lakes and fjords.",
        small_talk_subjects=["Did you swim?"],
    )
    peter = get_personality("en", "peter")
    steer = "Are you swimming? Love any water sports?"
    ongoing = ongoing_for(subject, [], "en", peter, bob_steer=steer)
    vague = buddy_user(ongoing, "I feel well.")
    assert "Are you swimming?" in vague
    assert "Answer that first" in vague
    asked = buddy_user(ongoing, "What else?")
    assert "Are you swimming?" in asked
    assert "Answer that in one short sentence" not in asked
    books = buddy_user(ongoing, "I like to read fantasy books.")
    assert "Then ask this private hint" in books
    assert "sports" in books

    def woven(user: str, *, system: str, **kwargs):
        del user, system, kwargs
        return (
            '{"line": "Fantasy books make a quiet evening. Are you swimming?", "emotion": "neutral"}',
            _record(),
        )

    reply = buddy_reply(ongoing, "I like to read fantasy books.", woven)
    assert "fantasy books" in reply.line.casefold()
    assert "swimming" in reply.line.casefold()

    def follow_up(user: str, *, system: str, **kwargs):
        del user, system, kwargs
        return (
            '{"line": "I feel well too. Are you swimming?", "emotion": "curiosity"}',
            _record(),
        )

    reply = buddy_reply(ongoing, "I feel well.", follow_up)
    assert "feel well" in reply.line.casefold()
    assert "swimming" in reply.line.casefold()


def test_a_copied_human_sentence_is_not_spoken():
    from logoskittens.talk import BuddyReply, LessonSubjectInput, _echoes_human, _without_echo

    human = "I came back to home and enjoyed my kids."
    copied = (
        "I came back to home and enjoyed my kids, and I hope that girl felt a little less alone after you stopped."
    )
    assert _echoes_human(human, copied) is True
    own = "The kids at home sound like the best part of coming back."
    assert _echoes_human(human, own) is False
    stripped = _without_echo(BuddyReply(line=copied, emotion="neutral"), human)
    assert "came back" not in stripped.line.casefold()
    assert "less alone" in stripped.line.casefold()

    subject = LessonSubjectInput(
        used_words=["home", "kids"],
        significant_words=["kids"],
        theme="A quiet evening after a long day.",
        small_talk_subjects=["How was the evening?"],
    )
    ongoing = ongoing_for(subject, [], "en", None)
    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del system
        calls["n"] += 1
        if calls["n"] == 1:
            return ('{"line": "' + copied + '", "emotion": "neutral"}', _record())
        assert "Do not repeat their sentence" in user or "Do not copy their sentence" in user
        return (
            '{"line": "Coming home to the kids sounds full. I hope she felt less alone.", "emotion": "neutral"}',
            _record(),
        )

    reply = buddy_reply(ongoing, human, complete)
    assert calls["n"] == 2
    assert "came back to home and enjoyed" not in reply.line.casefold()
    assert "kids" in reply.line.casefold()


def test_a_theme_echo_does_not_count_as_using_the_hint():
    from logoskittens.personalities import get_personality
    from logoskittens.talk import LessonSubjectInput, buddy_user, steer_taken

    subject = LessonSubjectInput(
        used_words=["fjords", "water", "sun", "tunnels"],
        significant_words=["fjords", "water"],
        theme="A drive along the fjords, with the sun on the water.",
        small_talk_subjects=["What did the water look like?"],
    )
    peter = get_personality("en", "peter")
    recent = [SpokenSentence(speaker="buddy", text="I'm fighting for the better view, man.")]
    steer = "I keep staring at that mirror water too. I'd grab a boat and push hard down the fjord."
    ongoing = ongoing_for(subject, recent, "en", peter, bob_steer=steer)
    human = "Okay, great start."
    heard = buddy_user(ongoing, human)
    assert "boat" in heard
    assert "private hint" in heard
    echo = "I'm glad you're on board, man. The water's got that mirror shine, like it's holding its own against the sun."
    taken = "I'm glad you're on board, man. I'd grab a boat and push down the fjord."
    assert steer_taken(echo, steer, ongoing, human) is False
    assert steer_taken(taken, steer, ongoing, human) is True

    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del system
        calls["n"] += 1
        if calls["n"] == 1:
            return ('{"line": "' + echo + '", "emotion": "neutral"}', _record())
        assert kwargs.get("think") == "off"
        assert "boat" in user
        return ('{"line": "' + taken + '", "emotion": "encouragement"}', _record())

    reply = buddy_reply(ongoing, human, complete)
    assert calls["n"] == 2
    assert "boat" in reply.line.casefold()

    question = "Would you invest in a private boat to lock in that fjord view?"
    travel = ongoing_for(subject, recent, "en", peter, bob_steer=question)
    asked = buddy_user(travel, "I like to travel.")
    assert "Ask" in asked or "ask this private hint" in asked
    mirror = "I like to travel, and the fjords here are like a mirror to the sun, man."
    assert steer_taken(mirror, question, travel, "I like to travel.") is False
    assert steer_taken(
        "I like to travel. Would you invest in a private boat?",
        question,
        travel,
        "I like to travel.",
    ) is True


def test_an_unknown_personality_uses_the_default():
    from logoskittens.personalities import get_personality

    assert get_personality("en", "nobody").id == "peter"


def test_norsk_maps_buddies_and_speaks_as_jeg():
    from logoskittens.content import prompt_text
    from logoskittens.personalities import get_personality
    from logoskittens.talk import LessonSubjectInput, _as_first_person, _third_person_self, buddy_user, ongoing_for

    lucas = get_personality("nb", "peter")
    assert lucas.id == "lucas"
    assert lucas.voice_id == "no_NO-talesyntese-medium"
    ingrid = get_personality("nb", "mary")
    assert ingrid.id == "ingrid"
    assert ingrid.voice_id == "no_NO-talesyntese-medium"
    assert get_personality("nb", "").id == "lucas"
    assert get_personality("nb", "jorge").id == "lucas"
    card = LessonSubjectInput(
        used_words=["tunneler", "fjorder"],
        significant_words=["fjorder"],
        theme="Ferie i Norge.",
        small_talk_subjects=["Hvordan var tunnelene?"],
    )
    heard = buddy_user(ongoing_for(card, [], "nb", lucas), "Hei")
    assert "jeg" in heard
    assert "Use I, me, and my" not in heard
    assert "Du er en mann" in heard
    assert "Ikke si han" in heard
    assert "one short sentence" in heard
    asked = buddy_user(ongoing_for(card, [], "nb", lucas), "Hva heter du")
    assert "one short sentence" in asked
    agreed = buddy_user(ongoing_for(card, [], "nb", lucas), "ja")
    assert "Hvordan var tunnelene?" in agreed
    english = buddy_user(ongoing_for(card, [], "en", get_personality("en", "peter")), "Hi")
    assert "Use I, me, and my" in english
    assert "gender: man" in english
    assert "bokmål" in prompt_text("ongoing_instruction_prompt", "nb").casefold()
    ongoing = ongoing_for(card, [], "nb", lucas)
    assert _third_person_self("Jeg heter Lucas.", ongoing) is False
    assert _third_person_self("Mitt navn er Lucas.", ongoing) is False
    assert _third_person_self("Lucas liker sjøen.", ongoing) is True
    assert _as_first_person("Lucas liker sjøen.", ongoing) == ""


def test_selecting_norsk_stores_lucas_or_ingrid(tmp_path):
    from fakes import FakeAudio, fake_complete

    from logoskittens.persistence import Store
    from logoskittens.session import SessionService

    service = SessionService(Store(tmp_path / "nb.db"), FakeAudio(), fake_complete)
    man = service.select("user-local", "nb", "norway_vacation_tunnels_fjords", "peter")
    described = service.describe(man)
    assert described["personality_id"] == "lucas"
    assert described["buddy_name"] == "Lucas"
    assert described["language_id"] == "nb"
    voices = {item["id"]: item["voice_id"] for item in described["personalities"]}
    assert voices == {
        "lucas": "no_NO-talesyntese-medium",
        "ingrid": "no_NO-talesyntese-medium",
    }
    titles = {item["id"]: item["title"] for item in described["materials"]}
    assert titles["norway_vacation_tunnels_fjords"] == "Ferie i Norge"
    assert titles["friendly_chat"] == "Vennlig prat"
    assert titles["cozy_breakfast"] == "Koselig frokost"
    woman = service.select("user-local", "nb", "norway_vacation_tunnels_fjords", "mary")
    assert service.describe(woman)["personality_id"] == "ingrid"
    listed = service.catalog("user-local", "nb")
    assert {item["id"] for item in listed["languages"]} == {"en", "nb", "uk", "de", "he"}
    assert [item["id"] for item in listed["personalities"]] == ["lucas", "ingrid"]


def test_a_second_language_id_selects_its_own_prompt(tmp_path, monkeypatch):
    root = tmp_path / "config"
    (root / "languages").mkdir(parents=True)
    (root / "prompts").mkdir()
    (root / "languages" / "zz.json").write_text(
        json.dumps(
            {
                "id": "zz",
                "display_name": "Fixture",
                "recognizer_model": "fixture",
                "stt_language": "zz",
                "llm_model": "qwen3:8b",
                "buddy_voice": "fixture-voice",
                "whisper": {"flag": "zz", "model": "fixture"},
            }
        ),
        encoding="utf-8",
    )
    (root / "prompts" / "ongoing_instruction_prompt_zz.md").write_text("Talk in the fixture language.\n")
    monkeypatch.setenv("LOGOSKITTENS_CONFIG", str(root))
    reset()
    try:
        assert prompt_text("ongoing_instruction_prompt", "zz") == "Talk in the fixture language."
        assert "nb" not in __import__("logoskittens.content", fromlist=["languages"]).languages()
    finally:
        reset()


def test_subject_fixture_matches_the_card_shape():
    assert set(SUBJECT) == {
        "used_words",
        "significant_words",
        "important_words",
        "theme",
        "small_talk_subjects",
    }


def test_practice_words_must_occur_in_the_sentences_and_an_old_card_still_loads():
    from logoskittens.talk import LessonSubjectInput, _ground_subject

    raw = "We stopped above a fjord and watched the ferries cross. The cold air stayed with me."
    card = LessonSubjectInput(
        used_words=["fjord", "ferries", "cold air"],
        significant_words=["fjord"],
        theme="A stop above a fjord.",
        small_talk_subjects=["Did you watch the water?"],
        important_words=["fjord", "ferries", "cold air", "goats", "the"],
    )
    grounded = _ground_subject(card, raw)
    assert grounded.important_words == ["ferries", "cold air"]
    older = LessonSubjectInput.model_validate(
        {
            "used_words": ["fjords"],
            "significant_words": ["fjords"],
            "theme": "A drive.",
            "small_talk_subjects": ["Did you look?"],
        }
    )
    assert older.important_words == []


def test_a_reading_word_is_offered_on_some_lines_and_may_be_left_out():
    from logoskittens.talk import LessonSubjectInput, buddy_reply, buddy_user, ongoing_for

    subject = LessonSubjectInput(
        used_words=["ferries", "slopes", "fjords"],
        significant_words=["fjords"],
        theme="A drive above the water.",
        small_talk_subjects=["Did you look down?"],
        important_words=["ferries", "slopes"],
    )
    first = ongoing_for(
        subject,
        [SpokenSentence(speaker="human", text="I came back to the road.")],
        "en",
        latest_human="I came back to the road.",
    )
    assert first.reading_word == "ferries"
    offered = buddy_user(first, "I came back to the road.")
    assert 'word from the reading: "ferries"' in offered
    assert "Leave the word out" in offered

    question = ongoing_for(
        subject,
        [SpokenSentence(speaker="human", text="What is your name?")],
        "en",
        latest_human="What is your name?",
    )
    assert question.reading_word == ""
    assert "reading" not in buddy_user(question, "What is your name?")

    quiet = ongoing_for(
        subject,
        [SpokenSentence(speaker="human", text="yes")],
        "en",
        latest_human="yes",
    )
    assert quiet.reading_word == ""

    steered = ongoing_for(
        subject,
        [SpokenSentence(speaker="human", text="I came back to the road.")],
        "en",
        bob_steer="I would grab a boat.",
        latest_human="I came back to the road.",
    )
    assert steered.reading_word == ""

    skipped = ongoing_for(
        subject,
        [
            SpokenSentence(speaker="human", text="I came back to the road."),
            SpokenSentence(speaker="buddy", text="The road was quiet."),
            SpokenSentence(speaker="human", text="I liked the evening."),
        ],
        "en",
        latest_human="I liked the evening.",
    )
    assert skipped.reading_word == ""

    later = [
        SpokenSentence(speaker="human", text="I came back to the road."),
        SpokenSentence(speaker="buddy", text="The ferries crossed once."),
        SpokenSentence(speaker="human", text="I liked the evening."),
        SpokenSentence(speaker="buddy", text="The light was low."),
        SpokenSentence(speaker="human", text="Then I walked."),
        SpokenSentence(speaker="buddy", text="The path stayed narrow."),
        SpokenSentence(speaker="human", text="It grew late."),
        SpokenSentence(speaker="buddy", text="The coat was enough."),
        SpokenSentence(speaker="human", text="The day ended."),
        SpokenSentence(speaker="buddy", text="I kept walking."),
        SpokenSentence(speaker="human", text="Home was close."),
        SpokenSentence(speaker="buddy", text="The door was open."),
        SpokenSentence(speaker="human", text="I sat down."),
    ]
    resumed = ongoing_for(subject, later, "en", latest_human="I sat down.")
    assert resumed.reading_word == "slopes"

    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del system, kwargs
        calls["n"] += 1
        assert "ferries" in user
        return '{"line": "The road home was quiet.", "emotion": "neutral"}', _record()

    reply = buddy_reply(first, "I came back to the road.", complete)
    assert calls["n"] == 1
    assert reply.line == "The road home was quiet."


def test_an_old_talk_on_spider_brackfast_opens_the_cozy_breakfast():
    from logoskittens.materials import FileRawMaterialSource

    loaded = FileRawMaterialSource().load("en", "spider_brackfast")
    assert loaded.title == "Cozy Breakfast"
    assert "spider" not in loaded.text.lower() and "flies" not in loaded.text.lower()
