"""Which Google voice speaks for whom, and the composite voice id.

`config/google_speech.json` ranks each language's voices per gender, best first
(WaveNet, Standard, Studio, Chirp3-HD). A buddy speaks with the first voice of
their gender unless the Settings page chose another. Savelij takes the first
man's voice of another speaker than the man's (`speaker()`: `nb-NO-Wavenet-G`
and `nb-NO-Standard-G` are one speaker), Studio skipped; when there is none he
uses the man's voice.

While Google voice is on, a profile's voice id becomes `g:<google voice>|<piper voice>`.
The router speaks the Google half and falls back to the Piper half. Every call
site that already passes a profile's voice id inherits this with no edit.
"""

from __future__ import annotations

import json
import re

from logoskittens.content import config_root
from logoskittens.speech import settings as speech_settings

PREFIX = "g:"
_FAMILY = re.compile(r"^(?P<locale>[a-z]{2,3}-[A-Z]{2})-(?P<family>[A-Za-z0-9]+(?:-HD)?)-(?P<voice>[A-Za-z0-9]+)$")
GOOGLE_VOICE = re.compile(r"^[a-z]{2,3}-[A-Z]{2}-\S+$")


def config() -> dict:
    path = config_root() / "google_speech.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"languages": {}}
    return doc if isinstance(doc, dict) else {"languages": {}}


def languages() -> dict[str, dict]:
    found = config().get("languages") or {}
    return found if isinstance(found, dict) else {}


def entry(language_id: str) -> dict:
    found = languages().get(language_id)
    return found if isinstance(found, dict) else {}


def tts_locale(language_id: str) -> str:
    return str(entry(language_id).get("tts_locale") or "")


def family(name: str) -> str:
    match = _FAMILY.match(name or "")
    return match.group("family") if match else ""


def speaker(name: str) -> str:
    """One Google speaker across families: `nb-NO-Wavenet-G` and `nb-NO-Standard-G` are the same one."""
    match = _FAMILY.match(name or "")
    if match is None:
        return name or ""
    return f"{match.group('locale')}:{match.group('voice')}"


def ranked(language_id: str, gender: str) -> list[str]:
    key = "woman" if gender == "woman" else "man"
    found = entry(language_id).get(key) or []
    return [str(item) for item in found if isinstance(item, str)]


def default_teacher(language_id: str, man: str) -> str:
    """The first man's voice of another speaker than `man`, Studio skipped. None left: the man's voice."""
    taken = speaker(man)
    for candidate in ranked(language_id, "man"):
        if family(candidate) == "Studio":
            continue
        if speaker(candidate) != taken:
            return candidate
    return man


def defaults(language_id: str) -> dict[str, str]:
    man = next(iter(ranked(language_id, "man")), "")
    woman = next(iter(ranked(language_id, "woman")), "") or man
    man = man or woman
    return {"man": man, "woman": woman, "teacher": default_teacher(language_id, man)}


def chosen(language_id: str, role: str, current: speech_settings.SpeechSettings | None = None) -> str:
    """The voice for `man`, `woman`, or `teacher` in this language: the page's choice, else the default."""
    current = current or speech_settings.current()
    picked = (current.voices.get(language_id) or {}).get(role, "").strip()
    if picked and GOOGLE_VOICE.match(picked):
        return picked
    found = defaults(language_id)
    if role == "teacher":
        return default_teacher(language_id, chosen(language_id, "man", current))
    return found.get(role, "")


def role_for(gender: str) -> str:
    return "woman" if (gender or "").strip().lower() in {"woman", "female", "f"} else "man"


def composite(google: str, piper: str) -> str:
    return f"{PREFIX}{google}|{piper}"


def split(voice_id: str) -> tuple[str, str]:
    """(google voice, piper voice). A plain Piper id has no Google half."""
    text = voice_id or ""
    if not text.startswith(PREFIX):
        return "", text
    google, _sep, piper = text[len(PREFIX):].partition("|")
    return google, piper


def piper_of(voice_id: str) -> str:
    return split(voice_id)[1]


def overlay(language_id: str, role: str, piper_voice: str) -> str:
    """The voice id a profile speaks with now: composite while Google voice is on, else its Piper voice."""
    piper = piper_of(piper_voice)
    current = speech_settings.current()
    if not current.google_tts:
        return piper
    google = chosen(language_id, role, current)
    if not google:
        return piper
    return composite(google, piper)
