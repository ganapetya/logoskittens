"""The German pack is files under config/ and runs a free talk like Ukrainian."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_german_pack_has_no_gaps():
    from logoskittens.content import language, language_gaps

    assert language_gaps("de") == []
    doc = language("de")
    assert doc["stt_language"] == "de"
    assert doc["whisper"]["flag"] == "de"
    assert doc["whisper"]["weight_file"] == "ggml-large-v3-turbo.bin"


def test_selecting_german_maps_peter_to_jonas_and_mary_to_lena(tmp_path):
    from fakes import FakeAudio, fake_complete

    from logoskittens.persistence import Store
    from logoskittens.session import SessionService

    service = SessionService(Store(tmp_path / "de.db"), FakeAudio(), fake_complete)
    man = service.describe(service.select("user-local", "de", "norway_vacation_tunnels_fjords", "peter"))
    assert man["personality_id"] == "jonas"
    assert man["buddy_name"] == "Jonas"
    assert man["language_id"] == "de"
    voices = {item["id"]: item["voice_id"] for item in man["personalities"]}
    assert voices == {"jonas": "de_DE-thorsten-medium", "lena": "de_DE-kerstin-low"}
    titles = {item["id"]: item["title"] for item in man["materials"]}
    assert titles["norway_vacation_tunnels_fjords"] == "Urlaub in Norwegen"
    assert titles["friendly_chat"] == "Freundliches Gespräch"
    assert titles["spider_brackfast"] == "Spinnenfrühstück"
    woman = service.describe(service.select("user-local", "de", "friendly_chat", "mary"))
    assert woman["personality_id"] == "lena"


def test_savelij_speaks_german_with_his_own_voice():
    from logoskittens.teachers import get_teacher

    teacher = get_teacher("de")
    assert teacher is not None
    assert teacher.voice_id == "de_DE-thorsten-medium"


def test_german_words_survive_normalising_and_greetings_are_direct():
    from logoskittens.talk import _direct, _drop_copied_prefix, _norm

    # casefold turns ß into ss on both sides, so Grüß Gott and Grüss Gott match.
    assert _norm("Grüß Gott, wie geht's?") == "grüss gott wie geht's"
    assert _norm("Die Straße über den Fjord.") == "die strasse über den fjord"
    assert _direct("Grüß Gott")
    assert _direct("Hallo")
    assert _direct("Guten Abend")
    assert _direct("Was isst du gern")
    assert not _direct("Ich mag die Berge und Kaffee")
    human = "Ich war letzten Sommer in Norwegen"
    assert _drop_copied_prefix("Ich war letzten Sommer in Norwegen, und es war schön.", human) == "und es war schön."


def test_logoscat_german_codes_become_de():
    from logoskittens.logoscat import language_code, live_language, target_codes

    for code in ("de", "DE", "deu", "ger", "de-DE", "de_AT", "de-CH"):
        assert live_language(code) == "de"
    assert language_code("deu") == "de"
    assert target_codes(["deu", "en", "uk"], "de") == ["en", "uk"]


def test_the_launcher_and_the_supervisor_know_the_german_weight():
    turbo = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
    rows = _script("extra_weights").rows(ROOT / "config")
    assert ("de", "ggml-large-v3-turbo.bin", turbo) in rows
    languages = _script("whisper_supervisor").load_languages(ROOT / "config")
    assert languages["de"] == {"flag": "de", "model": "large-v3-turbo", "weight_file": "ggml-large-v3-turbo.bin"}


def test_rob_falls_back_to_a_german_sentence():
    from logoskittens.rob import _fallback_explanation

    text = _fallback_explanation("Ich habe gegeht", "Ich bin gegangen", "", "de")
    assert text == "Sag in «Ich habe gegeht» lieber «Ich bin gegangen»."


def test_every_english_game_has_german_prompts_and_card_text():
    games = ROOT / "config" / "prompts" / "games"
    english = {path.name[: -len("_en.md")] for path in games.glob("*_en.md")}
    german = {path.name[: -len("_de.md")] for path in games.glob("*_de.md")}
    assert english and english == german
    for path in sorted((ROOT / "config" / "games").glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for key in ("titles", "summary", "closing"):
            block = manifest.get(key) or {}
            assert ("en" in block) == ("de" in block), (path.name, key)
        title = manifest["titles"]["de"]
        assert title.endswith("Game") and " " not in title
        for option in manifest.get("options") or []:
            labels = option.get("labels") or {}
            assert ("en" in labels) == ("de" in labels), path.name


def test_the_german_catalog_lists_the_same_games_as_english(tmp_path):
    from fakes import FakeAudio, fake_complete

    from logoskittens.persistence import Store
    from logoskittens.session import SessionService

    service = SessionService(Store(tmp_path / "games.db"), FakeAudio(), fake_complete)

    def listed(language: str) -> list[str]:
        return [item["id"] for item in service.catalog("user-local", language, "norway_vacation_tunnels_fjords", [])["games"]]

    assert listed("de") == listed("en")
    titles = {item["id"]: item["title"] for item in service.catalog("user-local", "de", "friendly_chat", [])["games"]}
    assert titles["taboo"] == "TabuGame"
