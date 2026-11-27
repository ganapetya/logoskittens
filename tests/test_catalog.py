"""The catalog offers the live languages and nothing from the retired lesson."""

import json

from logoskittens.persistence import Store


def test_seed_offers_english_and_norsk(tmp_path):
    store = Store(tmp_path / "catalog.db")
    languages = {row.id: row for row in store.list_languages()}
    assert set(languages) == {"en", "nb", "uk", "de", "he"}
    assert languages["en"].stt_language == "en"
    assert languages["en"].male_voice == "en_US-lessac-medium"
    assert languages["nb"].display_name == "Norsk"
    assert languages["nb"].stt_language == "no"
    assert languages["nb"].male_voice == "no_NO-talesyntese-medium"
    assert languages["nb"].female_voice == "no_NO-talesyntese-medium"
    assert languages["uk"].display_name == "Українська"
    assert languages["uk"].stt_language == "uk"
    assert languages["uk"].male_voice == "uk_UA-ukrainian_tts-medium@mykyta"
    assert languages["de"].display_name == "Deutsch"
    assert languages["de"].stt_language == "de"
    assert languages["de"].male_voice == "de_DE-thorsten-medium"
    assert store.get_user("user-local") is not None


def test_catalog_rereads_a_language_added_on_disk(tmp_path, monkeypatch):
    from fakes import FakeAudio, fake_complete

    from logoskittens.content import reset
    from logoskittens.session import SessionService

    root = tmp_path / "config"
    (root / "languages").mkdir(parents=True)
    doc = {
        "id": "zz",
        "display_name": "Fixture",
        "recognizer_model": "fixture",
        "stt_language": "zz",
        "llm_model": "qwen3:8b",
        "buddy_voice": "fixture-voice",
        "whisper": {"flag": "zz", "model": "fixture"},
    }
    (root / "languages" / "zz.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv("LOGOSKITTENS_CONFIG", str(root))
    reset()
    try:
        service = SessionService(Store(tmp_path / "late.db"), FakeAudio(), fake_complete)
        first = {item["id"] for item in service.catalog("user-local", "zz")["languages"]}
        assert first == {"zz"}
        later = dict(doc)
        later["id"] = "yy"
        later["display_name"] = "Later"
        (root / "languages" / "yy.json").write_text(json.dumps(later), encoding="utf-8")
        second = {item["id"] for item in service.catalog("user-local", "zz")["languages"]}
        assert second == {"zz", "yy"}
    finally:
        reset()
