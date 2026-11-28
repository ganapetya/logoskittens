"""The Google speech settings: two switches, one credential, and the voice choices.

They live in the hub SQLite file (`SpeechSettingsRow`) and are cached here, so a
turn never reads the database to learn which provider to use. The Settings page
replaces them through `/speech/settings`. Nothing here calls LogosCat.
"""

from __future__ import annotations

import json
import threading
from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["local", "google"]
CredentialKind = Literal["", "api_key", "service_account"]
ROLES = ("man", "woman", "teacher")


class SpeechSettings(BaseModel):
    tts_provider: Provider = "local"
    stt_provider: Provider = "local"
    credential_kind: CredentialKind = ""
    credential: str = ""
    # {language_id: {man, woman, teacher}}: a voice chosen on the page. A missing one is the shipped default.
    voices: dict[str, dict[str, str]] = Field(default_factory=dict)
    # {language_id: {locale, model}}: the recognition locale and model chosen on the page.
    recognition: dict[str, dict[str, str]] = Field(default_factory=dict)

    @property
    def has_credential(self) -> bool:
        return bool(self.credential_kind and self.credential.strip())

    @property
    def google_tts(self) -> bool:
        return self.tts_provider == "google" and self.has_credential

    @property
    def google_stt(self) -> bool:
        return self.stt_provider == "google" and self.has_credential

    def credential_hint(self) -> str:
        """What the page may show: the last four characters of a key, or a service account's email."""
        if not self.has_credential:
            return ""
        if self.credential_kind == "service_account":
            try:
                return str(json.loads(self.credential).get("client_email") or "")
            except (ValueError, AttributeError):
                return ""
        key = self.credential.strip()
        return f"…{key[-4:]}" if len(key) > 4 else "…"


_lock = threading.Lock()
_current = SpeechSettings()


def current() -> SpeechSettings:
    return _current


def replace(settings: SpeechSettings) -> None:
    global _current
    with _lock:
        _current = settings


def reset() -> None:
    """Back to local speech. Tests start here."""
    replace(SpeechSettings())


def load(store) -> SpeechSettings:
    """Read the row into the cache. No row is local speech."""
    row = store.get_speech_settings()
    if row is None:
        settings = SpeechSettings()
    else:
        settings = SpeechSettings(
            tts_provider=row.tts_provider if row.tts_provider in {"local", "google"} else "local",
            stt_provider=row.stt_provider if row.stt_provider in {"local", "google"} else "local",
            credential_kind=row.credential_kind if row.credential_kind in {"api_key", "service_account"} else "",
            credential=row.credential or "",
            voices=_json_map(row.voices_json),
            recognition=_json_map(row.recognition_json),
        )
    replace(settings)
    return settings


def save(store, settings: SpeechSettings) -> None:
    store.save_speech_settings(
        tts_provider=settings.tts_provider,
        stt_provider=settings.stt_provider,
        credential_kind=settings.credential_kind,
        credential=settings.credential,
        voices_json=json.dumps(settings.voices, ensure_ascii=False),
        recognition_json=json.dumps(settings.recognition, ensure_ascii=False),
    )
    replace(settings)


def _json_map(text: str) -> dict[str, dict[str, str]]:
    try:
        doc = json.loads(text or "{}")
    except ValueError:
        return {}
    if not isinstance(doc, dict):
        return {}
    found: dict[str, dict[str, str]] = {}
    for key, value in doc.items():
        if isinstance(value, dict):
            found[str(key)] = {str(k): str(v) for k, v in value.items() if isinstance(v, str)}
    return found
