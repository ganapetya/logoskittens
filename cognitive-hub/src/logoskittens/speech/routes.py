"""`/speech/*`: the Settings page's routes. The credential goes in and never comes back out."""

from __future__ import annotations

import asyncio
import base64
import sys
import threading
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from logoskittens.audio import AudioError
from logoskittens.speech import settings as speech_settings
from logoskittens.speech import voices
from logoskittens.speech.google import GoogleError, parse_service_account
from logoskittens.speech.router import SpeechRouter, recognition_for

LANGUAGE_NAMES = {"en": "English", "nb": "Norsk", "uk": "Українська", "de": "Deutsch", "he": "עברית"}
SAMPLE_LINES = {
    "en": "Hello, I am glad to talk with you today.",
    "nb": "Hei, så fint å snakke med deg i dag.",
    "uk": "Привіт, я радий поговорити з тобою сьогодні.",
    "de": "Hallo, schön, heute mit dir zu sprechen.",
    "he": "שלום, נעים לדבר איתך היום.",
}


class SettingsBody(BaseModel):
    tts_provider: str | None = None
    stt_provider: str | None = None
    # A new credential. Empty or missing keeps the stored one.
    credential_kind: str | None = None
    credential: str | None = None
    voices: dict[str, dict[str, str]] | None = None
    recognition: dict[str, dict[str, str]] | None = None


class SampleBody(BaseModel):
    language_id: str
    voice: str = ""
    role: str = "man"
    text: str = ""


def public(current: speech_settings.SpeechSettings) -> dict:
    """What the page sees. Never the credential."""
    languages = []
    for language_id, shipped in voices.languages().items():
        locale, model = recognition_for(language_id, current)
        languages.append(
            {
                "id": language_id,
                "name": LANGUAGE_NAMES.get(language_id, language_id),
                "tts_locale": shipped.get("tts_locale") or "",
                "voices": {role: voices.chosen(language_id, role, current) for role in speech_settings.ROLES},
                "defaults": voices.defaults(language_id),
                "ranked": {"man": voices.ranked(language_id, "man"), "woman": voices.ranked(language_id, "woman")},
                "stt_locale": locale,
                "stt_model": model,
            }
        )
    return {
        "tts_provider": current.tts_provider,
        "stt_provider": current.stt_provider,
        "credential_set": current.has_credential,
        "credential_kind": current.credential_kind,
        "credential_hint": current.credential_hint(),
        "languages": languages,
    }


def mount(app: FastAPI, router_of, store_of, on_recognition_local=None) -> None:
    """`router_of()` is the hub's `SpeechRouter`, `store_of()` its `Store`."""

    def _router() -> SpeechRouter:
        router = router_of()
        if not isinstance(router, SpeechRouter):
            raise HTTPException(status_code=503, detail="Google speech is not available on this hub.")
        return router

    def _warm() -> None:
        router = router_of()
        if isinstance(router, SpeechRouter):
            threading.Thread(target=router.google.warm, args=(speech_settings.current(),), daemon=True).start()

    @app.get("/speech/settings")
    def read_settings():
        return public(speech_settings.current())

    @app.put("/speech/settings")
    def write_settings(body: SettingsBody):
        before = speech_settings.current()
        update = before.model_copy(deep=True)
        if body.credential is not None and body.credential.strip():
            kind = (body.credential_kind or "").strip()
            if kind not in {"api_key", "service_account"}:
                raise HTTPException(status_code=400, detail="Choose an API key or a service account.")
            secret = body.credential.strip()
            if kind == "service_account":
                try:
                    parse_service_account(secret)
                except GoogleError as exc:
                    raise HTTPException(status_code=400, detail=str(exc))
            elif len(secret) < 20 or any(ch.isspace() for ch in secret):
                raise HTTPException(status_code=400, detail="That does not look like a Google API key.")
            update.credential_kind = kind
            update.credential = secret
        for field in ("tts_provider", "stt_provider"):
            value = getattr(body, field)
            if value is None:
                continue
            if value not in {"local", "google"}:
                raise HTTPException(status_code=400, detail=f"{field} is local or google.")
            setattr(update, field, value)
        if body.voices is not None:
            for language_id, picks in body.voices.items():
                if language_id not in voices.languages():
                    raise HTTPException(status_code=400, detail=f"Unknown language {language_id}.")
                # Merged per role. An empty name goes back to the default, which follows the man for the teacher.
                kept = dict(update.voices.get(language_id) or {})
                for role, name in picks.items():
                    if role not in speech_settings.ROLES:
                        raise HTTPException(status_code=400, detail=f"Unknown role {role}.")
                    name = (name or "").strip()
                    if name and not voices.GOOGLE_VOICE.match(name):
                        raise HTTPException(status_code=400, detail=f"Not a Google voice name: {name}")
                    if name:
                        kept[role] = name
                    else:
                        kept.pop(role, None)
                update.voices[language_id] = kept
        if body.recognition is not None:
            for language_id, chosen in body.recognition.items():
                if language_id not in voices.languages():
                    raise HTTPException(status_code=400, detail=f"Unknown language {language_id}.")
                update.recognition[language_id] = {
                    key: str(chosen[key]).strip() for key in ("locale", "model") if key in chosen
                }
        if (update.tts_provider == "google" or update.stt_provider == "google") and not update.has_credential:
            raise HTTPException(status_code=400, detail="Save a Google credential before turning Google on.")
        speech_settings.save(store_of(), update)
        _warm()
        if before.google_stt and not update.google_stt and on_recognition_local is not None:
            on_recognition_local()
        return public(update)

    @app.delete("/speech/credential")
    def forget_credential():
        before = speech_settings.current()
        update = before.model_copy(
            update={"credential_kind": "", "credential": "", "tts_provider": "local", "stt_provider": "local"}
        )
        speech_settings.save(store_of(), update)
        if before.google_stt and on_recognition_local is not None:
            on_recognition_local()
        return public(update)

    @app.post("/speech/test")
    async def test_credential():
        router = _router()
        current = speech_settings.current()
        if not current.has_credential:
            raise HTTPException(status_code=400, detail="No Google credential is saved.")

        def run() -> dict:
            began = time.perf_counter()
            try:
                router.google.voices(current, "en-US")
                listed = (time.perf_counter() - began) * 1000
                began = time.perf_counter()
                router.google.synthesize(
                    current, "Hello.", locale="en-US", voice_name=voices.chosen("en", "man", current), sample_rate=22050
                )
                spoken = (time.perf_counter() - began) * 1000
            except GoogleError as exc:
                return {"ok": False, "error": str(exc)}
            return {"ok": True, "voices_ms": round(listed), "tts_ms": round(spoken)}

        return await asyncio.to_thread(run)

    @app.get("/speech/voices")
    async def list_voices(language_id: str):
        router = _router()
        current = speech_settings.current()
        locale = voices.tts_locale(language_id)
        if not locale:
            raise HTTPException(status_code=404, detail="not found")
        shipped = {"man": voices.ranked(language_id, "man"), "woman": voices.ranked(language_id, "woman")}
        if not current.has_credential:
            return {"language_id": language_id, "live": False, "voices": _shipped_list(shipped)}
        try:
            found = await asyncio.to_thread(router.google.voices, current, locale)
        except GoogleError as exc:
            print(f"google voices failed: {exc}", file=sys.stderr, flush=True)
            return {"language_id": language_id, "live": False, "error": str(exc), "voices": _shipped_list(shipped)}
        return {"language_id": language_id, "live": True, "voices": _ranked_live(found)}

    @app.post("/speech/sample")
    async def sample(body: SampleBody):
        router = _router()
        if body.language_id not in voices.languages():
            raise HTTPException(status_code=404, detail="not found")
        if not speech_settings.current().has_credential:
            raise HTTPException(status_code=400, detail="No Google credential is saved.")
        name = (body.voice or "").strip() or voices.chosen(body.language_id, body.role)
        if not voices.GOOGLE_VOICE.match(name):
            raise HTTPException(status_code=400, detail="Not a Google voice name.")
        text = (body.text or "").strip()[:200] or SAMPLE_LINES.get(body.language_id, "Hello.")
        began = time.perf_counter()
        try:
            pcm = await asyncio.to_thread(router.google_pcm, text, body.language_id, name)
        except (GoogleError, AudioError) as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        return {"pcm": base64.b64encode(pcm).decode("ascii"), "ms": round((time.perf_counter() - began) * 1000)}


def _family_rank(name: str) -> int:
    order = ("Wavenet", "Standard", "Neural2", "Studio", "Chirp3-HD", "Chirp-HD")
    found = voices.family(name)
    return order.index(found) if found in order else len(order)


def _ranked_live(found: list[dict]) -> list[dict]:
    rows = [item | {"family": voices.family(item["name"])} for item in found if item.get("gender")]
    rows.sort(key=lambda item: (_family_rank(item["name"]), item["name"]))
    return rows


def _shipped_list(shipped: dict[str, list[str]]) -> list[dict]:
    return [
        {"name": name, "gender": gender, "family": voices.family(name)}
        for gender, names in shipped.items()
        for name in names
    ]
