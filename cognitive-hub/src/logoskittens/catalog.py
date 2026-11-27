"""Seed languages into SQLite. Topics and dossiers are not part of free speech."""

from logoskittens import content
from logoskittens.persistence import LanguageRow


def seed_store(store) -> None:
    content.reload()
    if store.get_user("user-local") is None:
        store.save_user("user-local", "Local", "")
    for language_id, doc in content.languages().items():
        row = store.get_language(language_id)
        voice = str(doc["buddy_voice"])
        payload = LanguageRow(
            id=language_id,
            display_name=doc["display_name"],
            recognizer_model=doc["recognizer_model"],
            stt_language=doc["stt_language"],
            male_voice=voice,
            female_voice=voice,
            llm_model=doc["llm_model"],
            phrases_json="",
        )
        if row is None:
            store.save_language(payload)
            continue
        changed = (
            row.display_name != payload.display_name
            or row.recognizer_model != payload.recognizer_model
            or row.stt_language != payload.stt_language
            or row.male_voice != voice
            or row.female_voice != voice
            or row.llm_model != payload.llm_model
        )
        if changed:
            row.display_name = payload.display_name
            row.recognizer_model = payload.recognizer_model
            row.stt_language = payload.stt_language
            row.male_voice = voice
            row.female_voice = voice
            row.llm_model = payload.llm_model
            row.phrases_json = ""
            store.save_language(row)


def language_brief(store) -> list[dict]:
    return [
        {"id": row.id, "display_name": row.display_name}
        for row in store.list_languages()
        if row.id in content.languages()
    ]


