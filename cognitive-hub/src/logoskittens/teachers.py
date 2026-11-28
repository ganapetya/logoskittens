"""The teacher is one role across languages. The files are not buddy choices.

Savelij is ``teacher-one`` for every live pack. The talk language picks his
voice and Rob's prompt. It does not pick a different person.
"""

import json

from pydantic import BaseModel, Field

from logoskittens.content import config_root


class TeacherProfile(BaseModel):
    id: str
    name: str = Field(min_length=1)
    gender: str = Field(min_length=1)
    mood: str = Field(min_length=1)
    stance: str = Field(min_length=1)
    likes: list[str] = Field(min_length=1)
    voice_id: str = Field(min_length=1)
    voices: dict[str, str] = Field(default_factory=dict)
    summary: str = Field(min_length=1)
    actor_id: str = "teacher-one"
    default: bool = False


def get_teacher(language_id: str) -> TeacherProfile | None:
    """Savelij for this talk, with that language's voice. None when no teacher file exists."""
    found = _profiles()
    if not found:
        return None
    chosen = next((item for item in found if item.default), found[0])
    voice = (chosen.voices.get(language_id) or chosen.voice_id).strip()
    if not voice:
        return None
    from logoskittens.speech.voices import overlay

    # While Google voice is on, Savelij speaks with the language's teacher voice, Piper behind it.
    voice = overlay(language_id, "teacher", voice)
    if voice == chosen.voice_id:
        return chosen
    return chosen.model_copy(update={"voice_id": voice})


def _profiles() -> list[TeacherProfile]:
    root = config_root() / "teachers"
    if not root.is_dir():
        return []
    paths = sorted(root.glob("*.json")) + sorted(root.glob("*/*.json"))
    found: list[TeacherProfile] = []
    seen: set[str] = set()
    for path in paths:
        person = TeacherProfile.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if person.id in seen:
            continue
        seen.add(person.id)
        found.append(person)
    return found
