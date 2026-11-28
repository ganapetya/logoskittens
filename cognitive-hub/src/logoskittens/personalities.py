"""Buddy profiles. The subject card stays the theme. This file is who is talking.

Read on each turn. An empty id is the buddy marked default.
An old session id ``jorge`` is Peter, then matched into the chosen language.
An id from another language matches by gender, then by that default buddy.
``nature`` is optional and is not that match key. An empty nature stays off the prompt.
``alias`` is optional. An empty alias stays off the prompt. It does not replace the name.
"""

import json

from pydantic import BaseModel, Field

from logoskittens.content import config_root

DEFAULT_PERSONALITY_ID = "peter"
_ALIASES = {"jorge": "peter"}


class BuddyPersonality(BaseModel):
    id: str
    name: str = Field(min_length=1)
    gender: str = Field(min_length=1)
    nature: str = ""
    alias: str = ""
    mood: str = Field(min_length=1)
    home: str = ""
    stance: str = Field(min_length=1)
    likes: list[str] = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    default: bool = False


def list_personalities(language_id: str) -> list[BuddyPersonality]:
    folder = config_root() / "buddies" / language_id
    if not folder.is_dir():
        return []
    found = [BuddyPersonality.model_validate(json.loads(path.read_text(encoding="utf-8"))) for path in folder.glob("*.json")]
    found.sort(key=lambda item: (not item.default, item.name))
    return [_spoken(language_id, item) for item in found]


def _spoken(language_id: str, person: BuddyPersonality) -> BuddyPersonality:
    """While Google voice is on, the voice id names the Google voice of this gender, with the Piper one behind it."""
    from logoskittens.speech.voices import overlay, role_for

    voice = overlay(language_id, role_for(person.gender), person.voice_id)
    return person if voice == person.voice_id else person.model_copy(update={"voice_id": voice})


def get_personality(language_id: str, personality_id: str) -> BuddyPersonality:
    people = list_personalities(language_id)
    if not people:
        raise ValueError(f"No buddy profiles for {language_id}")
    chosen = _ALIASES.get((personality_id or "").strip(), (personality_id or "").strip())
    if not chosen:
        return _default_buddy(people)
    for item in people:
        if item.id == chosen:
            return item
    gender = _gender_of(chosen)
    if gender:
        for item in people:
            if item.gender == gender:
                return item
    return _default_buddy(people)


def _default_buddy(people: list[BuddyPersonality]) -> BuddyPersonality:
    for item in people:
        if item.default:
            return item
    return people[0]


def _gender_of(personality_id: str) -> str:
    """Gender of this id in any language pack. ``man`` and ``woman`` are the match keys."""
    root = config_root() / "buddies"
    if not root.is_dir():
        return ""
    for path in sorted(root.glob("*/*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(doc, dict):
            continue
        if str(doc.get("id") or "").strip() != personality_id:
            continue
        return str(doc.get("gender") or "").strip()
    return ""
