"""The Hebrew pack is files under config/ and runs a free talk like German. The page mirrors for it."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IVRIT = "https://huggingface.co/ivrit-ai/whisper-large-v3-turbo-ggml/resolve/2130c78e4a9cb4914cc4df91a1c3031407789705/ggml-model.bin"


def _script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_hebrew_pack_has_no_gaps():
    from logoskittens.content import language, language_gaps

    assert language_gaps("he") == []
    doc = language("he")
    assert doc["stt_language"] == "he"
    assert doc["whisper"]["flag"] == "he"
    assert doc["whisper"]["weight_file"] == "ggml-ivrit-large-v3-turbo.bin"


def test_selecting_hebrew_maps_peter_to_noam_and_mary_to_maya(tmp_path):
    from fakes import FakeAudio, fake_complete

    from logoskittens.persistence import Store
    from logoskittens.session import SessionService

    service = SessionService(Store(tmp_path / "he.db"), FakeAudio(), fake_complete)
    man = service.describe(service.select("user-local", "he", "norway_vacation_tunnels_fjords", "peter"))
    assert man["personality_id"] == "noam"
    assert man["buddy_name"] == "נועם"
    assert man["language_id"] == "he"
    voices = {item["id"]: item["voice_id"] for item in man["personalities"]}
    assert voices == {"noam": "he_IL-saspeech-medium", "maya": "he_IL-saspeech-medium"}
    titles = {item["id"]: item["title"] for item in man["materials"]}
    assert titles["norway_vacation_tunnels_fjords"] == "חופשה בנורווגיה"
    assert titles["friendly_chat"] == "שיחה ידידותית"
    assert titles["cozy_breakfast"] == "ארוחת בוקר נעימה"
    woman = service.describe(service.select("user-local", "he", "friendly_chat", "mary"))
    assert woman["personality_id"] == "maya"


def test_savelij_speaks_hebrew_with_the_hebrew_voice():
    from logoskittens.teachers import get_teacher

    teacher = get_teacher("he")
    assert teacher is not None
    assert teacher.voice_id == "he_IL-saspeech-medium"


def test_hebrew_words_survive_normalising_and_greetings_are_direct():
    from logoskittens.talk import _direct, _drop_copied_prefix, _norm

    assert _norm("שלום, מה נשמע?") == "שלום מה נשמע"
    assert _direct("שלום")
    assert _direct("בוקר טוב")
    assert _direct("מה אתה אוהב לאכול")
    assert not _direct("אני אוהב הרים וקפה")
    human = "בקיץ שעבר נסעתי לנורווגיה עם חברים"
    assert _drop_copied_prefix("בקיץ שעבר נסעתי לנורווגיה עם חברים, והיה נהדר.", human) == "והיה נהדר."


def test_logoscat_hebrew_codes_become_he():
    from logoskittens.logoscat import language_code, live_language, target_codes

    for code in ("he", "HE", "heb", "iw", "he-IL", "he_IL"):
        assert live_language(code) == "he"
    assert language_code("heb") == "he"
    assert target_codes(["heb", "en", "de"], "he") == ["en", "de"]


def test_the_launcher_downloads_the_ivrit_weight_and_the_supervisor_knows_it():
    rows = _script("extra_weights").rows(ROOT / "config")
    assert ("he", "ggml-ivrit-large-v3-turbo.bin", IVRIT) in rows
    languages = _script("whisper_supervisor").load_languages(ROOT / "config")
    assert languages["he"] == {"flag": "he", "model": "ivrit-large-v3-turbo", "weight_file": "ggml-ivrit-large-v3-turbo.bin"}


def test_rob_falls_back_to_a_hebrew_sentence():
    from logoskittens.rob import _fallback_explanation

    assert _fallback_explanation("אני הולך אתמול", "הלכתי אתמול", "", "he") == "במקום «אני הולך אתמול» אומרים «הלכתי אתמול»."


def test_every_english_game_has_hebrew_prompts_and_card_text():
    games = ROOT / "config" / "prompts" / "games"
    english = {path.name[: -len("_en.md")] for path in games.glob("*_en.md")}
    hebrew = {path.name[: -len("_he.md")] for path in games.glob("*_he.md")}
    assert english and english == hebrew
    for path in sorted((ROOT / "config" / "games").glob("*.json")):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for key in ("titles", "summary", "closing"):
            block = manifest.get(key) or {}
            assert ("en" in block) == ("he" in block), (path.name, key)
        title = manifest["titles"]["he"]
        assert title.endswith("Game") and " " not in title
        for option in manifest.get("options") or []:
            labels = option.get("labels") or {}
            assert ("en" in labels) == ("he" in labels), path.name


def test_the_hebrew_catalog_lists_the_same_games_as_english(tmp_path):
    from fakes import FakeAudio, fake_complete

    from logoskittens.persistence import Store
    from logoskittens.session import SessionService

    service = SessionService(Store(tmp_path / "games.db"), FakeAudio(), fake_complete)

    def listed(language: str) -> list[str]:
        return [item["id"] for item in service.catalog("user-local", language, "norway_vacation_tunnels_fjords", [])["games"]]

    assert listed("he") == listed("en")
    titles = {item["id"]: item["title"] for item in service.catalog("user-local", "he", "friendly_chat", [])["games"]}
    assert titles["taboo"] == "טאבוGame"


def test_the_page_mirrors_for_a_right_to_left_source():
    source = (ROOT / "virtual-stage" / "src" / "languages.tsx").read_text(encoding="utf-8")
    assert 'const RTL = new Set(["he", "iw", "ar", "fa", "ur", "yi"]);' in source
    app = (ROOT / "virtual-stage" / "src" / "App.tsx").read_text(encoding="utf-8")
    assert 'root.dir = isRtl(language) ? "rtl" : "ltr";' in app
    # Physical left/right classes do not mirror. The page uses start and end.
    for path in (ROOT / "virtual-stage" / "src").rglob("*.tsx"):
        text = path.read_text(encoding="utf-8")
        for physical in (" text-left", " ml-", " mr-", "md:border-r ", '"ml-', '"mr-'):
            assert physical not in text, (path.name, physical)
