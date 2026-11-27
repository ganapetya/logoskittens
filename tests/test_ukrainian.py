"""The Ukrainian pack is files under config/ and runs a free talk like Norsk."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_ukrainian_pack_has_no_gaps():
    from logoskittens.content import language, language_gaps

    assert language_gaps("uk") == []
    doc = language("uk")
    assert doc["stt_language"] == "uk"
    assert doc["whisper"]["flag"] == "uk"
    assert doc["whisper"]["weight_file"] == "ggml-large-v3-turbo.bin"


def test_selecting_ukrainian_maps_peter_to_taras_and_mary_to_tanyusha(tmp_path):
    from fakes import FakeAudio, fake_complete

    from logoskittens.persistence import Store
    from logoskittens.session import SessionService

    service = SessionService(Store(tmp_path / "uk.db"), FakeAudio(), fake_complete)
    man = service.describe(service.select("user-local", "uk", "norway_vacation_tunnels_fjords", "peter"))
    assert man["personality_id"] == "taras"
    assert man["buddy_name"] == "Тарас"
    assert man["language_id"] == "uk"
    voices = {item["id"]: item["voice_id"] for item in man["personalities"]}
    assert voices == {
        "taras": "uk_UA-ukrainian_tts-medium@mykyta",
        "tanyusha": "uk_UA-ukrainian_tts-medium@tetiana",
    }
    titles = {item["id"]: item["title"] for item in man["materials"]}
    assert titles["norway_vacation_tunnels_fjords"] == "Відпустка в Норвегії"
    assert titles["friendly_chat"] == "Дружня розмова"
    assert titles["spider_brackfast"] == "Павучий сніданок"
    woman = service.describe(service.select("user-local", "uk", "friendly_chat", "mary"))
    assert woman["personality_id"] == "tanyusha"


def test_savelij_speaks_ukrainian_with_his_own_voice():
    from logoskittens.teachers import get_teacher

    teacher = get_teacher("uk")
    assert teacher is not None
    assert teacher.voice_id == "uk_UA-ukrainian_tts-medium@mykyta"


def test_cyrillic_words_survive_normalising_and_greetings_are_direct():
    from logoskittens.talk import _direct, _drop_copied_prefix, _norm

    assert _norm("Привіт, як справи?") == "привіт як справи"
    assert _norm("М'ята й п’ять") == "м'ята й п'ять"
    assert _norm("Vi dro på tur, også i fjor.") == "vi dro på tur også i fjor"
    assert _norm("I don't know.") == "i don't know"
    assert _direct("Привіт")
    assert _direct("Добрий вечір")
    assert _direct("Що ти любиш їсти")
    assert not _direct("Я люблю гори й каву")
    human = "Я їздив у Карпати минулого літа"
    assert _drop_copied_prefix("Я їздив у Карпати минулого літа, і там було гарно.", human) == "і там було гарно."


def test_logoscat_ukrainian_codes_become_uk():
    from logoskittens.logoscat import language_code, live_language, target_codes

    for code in ("uk", "UK", "ukr", "uk-UA", "uk_UA"):
        assert live_language(code) == "uk"
    assert language_code("ukr") == "uk"
    assert target_codes(["ukr", "en", "de"], "uk") == ["en", "de"]


def test_the_launcher_downloads_the_ukrainian_weight_and_the_supervisor_knows_it():
    rows = _script("extra_weights").rows(ROOT / "config")
    turbo = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
    assert ("uk", "ggml-large-v3-turbo.bin", turbo) in rows
    assert rows == [
        (
            "de",
            "ggml-large-v3-turbo.bin",
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
        ),
        (
            "he",
            "ggml-ivrit-large-v3-turbo.bin",
            "https://huggingface.co/ivrit-ai/whisper-large-v3-turbo-ggml/resolve/2130c78e4a9cb4914cc4df91a1c3031407789705/ggml-model.bin",
        ),
        (
            "uk",
            "ggml-large-v3-turbo.bin",
            "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin",
        )
    ]
    languages = _script("whisper_supervisor").load_languages(ROOT / "config")
    assert languages["uk"] == {"flag": "uk", "model": "large-v3-turbo", "weight_file": "ggml-large-v3-turbo.bin"}


def _uk_ongoing(human: str):
    from logoskittens.talk import LessonSubjectInput, SpokenSentence, ongoing_for

    subject = LessonSubjectInput(
        used_words=["тунелі", "фіорди", "пороми", "схили"],
        significant_words=["тунелі", "фіорди"],
        theme="Відпустка в Норвегії: тунелі й фіорди.",
        small_talk_subjects=["Ти колись їздив крізь довгий тунель?", "Які фіорди ти бачив?"],
    )
    return ongoing_for(subject, [SpokenSentence(speaker="human", text=human)], "uk")


def test_a_soft_miss_in_ukrainian_keeps_the_first_reply_without_a_second_call(capsys):
    from fakes import fake_complete

    from logoskittens.talk import buddy_reply

    human = "Що ти любиш пити зранку?"
    ongoing = _uk_ongoing(human)
    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del user, system, kwargs
        calls["n"] += 1
        line = "Я люблю каву. Фіорди там темні, а тунелі довгі й холодні."
        return json.dumps({"line": line, "emotion": "neutral"}, ensure_ascii=False), fake_complete("", system="")[1]

    reply = buddy_reply(ongoing, human, complete)
    assert calls["n"] == 1
    assert "buddy added a theme story" in capsys.readouterr().err
    assert reply.line == "Я люблю каву."


def test_a_third_person_line_in_ukrainian_is_still_asked_again():
    from fakes import fake_complete

    from logoskittens.talk import _reasks_soft_misses, buddy_reply

    assert _reasks_soft_misses("en") is True
    assert _reasks_soft_misses("uk") is False
    human = "Я теж люблю гори."
    ongoing = _uk_ongoing(human)
    from logoskittens.personalities import get_personality

    ongoing.personality = get_personality("uk", "taras")
    calls = {"n": 0}

    def complete(user: str, *, system: str, **kwargs):
        del user, system, kwargs
        calls["n"] += 1
        line = "Тарас любить гори." if calls["n"] == 1 else "Гори мені до душі, особливо Карпати."
        return json.dumps({"line": line, "emotion": "neutral"}, ensure_ascii=False), fake_complete("", system="")[1]

    reply = buddy_reply(ongoing, human, complete)
    assert calls["n"] == 2
    assert reply.line == "Гори мені до душі, особливо Карпати."


def test_the_recent_block_keeps_the_newest_lines_within_its_budget():
    from logoskittens.talk import SpokenSentence, recent_within_budget

    lines = [SpokenSentence(speaker="human", text=f"{index}" + "ж" * 299) for index in range(8)]
    kept = recent_within_budget(lines, budget=900)
    assert [item.text[0] for item in kept] == ["5", "6", "7"]
    huge = [SpokenSentence(speaker="human", text="я" * 5000)]
    assert recent_within_budget(huge, budget=900) == huge


def test_every_english_game_has_ukrainian_prompts_and_card_text():
    import json

    games = ROOT / "config" / "prompts" / "games"
    english = {path.name[: -len("_en.md")] for path in games.glob("*_en.md")}
    ukrainian = {path.name[: -len("_uk.md")] for path in games.glob("*_uk.md")}
    assert english and english == ukrainian
    for path in sorted((ROOT / "config" / "games").glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for key in ("titles", "summary", "closing"):
            block = manifest.get(key) or {}
            assert ("en" in block) == ("uk" in block), (path.name, key)
        title = manifest["titles"]["uk"]
        assert title.endswith("Game") and " " not in title
        for option in manifest.get("options") or []:
            labels = option.get("labels") or {}
            assert ("en" in labels) == ("uk" in labels), path.name


def test_the_ukrainian_catalog_lists_the_same_games_as_english(tmp_path):
    from fakes import FakeAudio, fake_complete

    from logoskittens.persistence import Store
    from logoskittens.session import SessionService

    service = SessionService(Store(tmp_path / "games.db"), FakeAudio(), fake_complete)

    def listed(language: str) -> list[str]:
        return [item["id"] for item in service.catalog("user-local", language, "norway_vacation_tunnels_fjords", [])["games"]]

    assert listed("uk") == listed("en")
    titles = {item["id"]: item["title"] for item in service.catalog("user-local", "uk", "friendly_chat", [])["games"]}
    assert titles["taboo"] == "ТабуGame"
