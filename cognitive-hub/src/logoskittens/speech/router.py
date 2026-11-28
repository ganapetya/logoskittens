"""The hub's speech client: Google or local, per switch, with the audio-engine client's two method names.

`SessionService` holds one of these where it held `AudioClient`. Nothing else in the hub changes.

- Voice: a composite voice id (`g:<google>|<piper>`, see `voices.py`) speaks with Google
  while Google voice is on. A Google error or timeout speaks the same line with Piper.
- Recognition: while Google recognition is on, WAV, WebM, and Ogg go to Google as they are.
  Anything else (Safari's mp4) is converted to 16 kHz WAV by the audio engine first.
  A Google failure is an `AudioError` the page shows. Whisper is not tried, because the
  hub stopped loading its weights while Google recognition was on.
"""

from __future__ import annotations

import sys
import threading
import time

from logoskittens.audio import AudioClient, AudioError, wav_to_pcm
from logoskittens.games.speed import PcmCache
from logoskittens.speech import settings as speech_settings
from logoskittens.speech import voices
from logoskittens.speech.google import GoogleError, GoogleSpeech, audio_format, clean_text, phrases_from
from logoskittens.wire import PCM_SAMPLE_RATE

RECOGNITION_FAILED = "Recognition failed. Hold Speak and try again."
CACHE_ENTRIES = 256
CACHE_BYTES = 32 * 1024 * 1024

_local = threading.local()


def last_tts_via() -> str:
    """How the last line voiced on this thread was spoken: `google`, `piper`, or `fallback`."""
    return getattr(_local, "tts_via", "piper")


def recognizer_label(language_id: str, fallback: str) -> str:
    """The recognizer for the first-audio log line."""
    current = speech_settings.current()
    if not current.google_stt:
        return fallback
    locale, model = recognition_for(language_id, current)
    return f"google:{locale}/{model or 'default'}"


def recognition_for(language_id: str, current: speech_settings.SpeechSettings | None = None) -> tuple[str, str]:
    current = current or speech_settings.current()
    shipped = voices.entry(language_id)
    chosen = current.recognition.get(language_id) or {}
    locale = (chosen.get("locale") or "").strip() or str(shipped.get("stt_locale") or "")
    model = chosen["model"].strip() if "model" in chosen else str(shipped.get("stt_model") or "")
    return locale, model


def hub_language(stt_code: str) -> str:
    """The hub language id for a pack's `stt_language` (`no` is `nb`)."""
    from logoskittens.content import language as language_doc

    code = (stt_code or "").strip()
    known = voices.languages()
    if code in known:
        return code
    for language_id in known:
        try:
            if str(language_doc(language_id).get("stt_language") or "") == code:
                return language_id
        except KeyError:
            continue
    return code


class SpeechRouter:
    def __init__(self, local: AudioClient, google: GoogleSpeech | None = None):
        self.local = local
        self.google = google or GoogleSpeech()
        self.cache = PcmCache(max_entries=CACHE_ENTRIES, max_bytes=CACHE_BYTES)
        # A locale Google refused for recognition, replaced by the pack's alternative, for this process.
        self._stt_locale_swap: dict[str, str] = {}

    # -- voice ---------------------------------------------------------------------

    def synthesize(self, text: str, language_code: str, voice_id: str) -> bytes:
        return self._synthesize(text, language_code, voice_id, retry=False)

    def synthesize_background(self, text: str, language_code: str, voice_id: str) -> bytes:
        """Deck prefetch: one retry on a busy or failing Google before Piper speaks it."""
        return self._synthesize(text, language_code, voice_id, retry=True)

    def _synthesize(self, text: str, language_code: str, voice_id: str, *, retry: bool) -> bytes:
        google, piper = voices.split(voice_id)
        if google and speech_settings.current().google_tts:
            try:
                pcm = self.google_pcm(text, language_code, google, retry=retry)
                _local.tts_via = "google"
                return pcm
            except (GoogleError, AudioError) as exc:
                print(f"tts fallback voice={google} error={exc}", file=sys.stderr, flush=True)
                _local.tts_via = "fallback"
                return self.local.synthesize(text, language_code, piper)
        _local.tts_via = "piper"
        return self.local.synthesize(text, language_code, piper)

    def google_pcm(self, text: str, language_code: str, google_voice: str, *, retry: bool = False) -> bytes:
        spoken = clean_text(text)
        if not spoken:
            raise AudioError("text is empty")
        key = (google_voice, "", spoken)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        locale = voices.tts_locale(language_code) or google_voice[:5]
        current = speech_settings.current()
        try:
            wav = self.google.synthesize(current, spoken, locale=locale, voice_name=google_voice, sample_rate=PCM_SAMPLE_RATE)
        except GoogleError as exc:
            if not (retry and exc.retryable):
                raise
            time.sleep(0.5)
            wav = self.google.synthesize(current, spoken, locale=locale, voice_name=google_voice, sample_rate=PCM_SAMPLE_RATE)
        pcm = wav_to_pcm(wav) if wav[:4] == b"RIFF" else wav
        self.cache.put(key, pcm)
        return pcm

    # -- recognition ------------------------------------------------------------------

    def transcribe(
        self,
        audio: bytes,
        content_type: str = "application/octet-stream",
        language: str = "en",
        prompt: str = "",
    ) -> str:
        current = speech_settings.current()
        if not current.google_stt:
            return self.local.transcribe(audio, content_type, language=language, prompt=prompt)
        if not audio or len(audio) < 100:
            return ""
        language_id = hub_language(language)
        encoding, rate, channels = audio_format(audio, content_type)
        if not encoding:
            audio = self.local.convert16k(audio, content_type)
            encoding, rate, channels = audio_format(audio, "audio/wav")
            if not encoding:
                raise AudioError("The recording could not be read. Hold Speak and try again.")
        locale, model = recognition_for(language_id, current)
        locale = self._stt_locale_swap.get(locale, locale)
        phrases = phrases_from(prompt)
        try:
            return self.google.recognize(
                current, audio, encoding=encoding, sample_rate=rate, channels=channels,
                locale=locale, phrases=phrases, model=model,
            )
        except GoogleError as exc:
            alternative = str(voices.entry(language_id).get("stt_alt_locale") or "")
            if exc.status == 400 and alternative and alternative != locale:
                try:
                    text = self.google.recognize(
                        current, audio, encoding=encoding, sample_rate=rate, channels=channels,
                        locale=alternative, phrases=phrases, model=model,
                    )
                except GoogleError as again:
                    print(f"stt google failed locale={alternative} error={again}", file=sys.stderr, flush=True)
                    raise AudioError(RECOGNITION_FAILED) from again
                print(f"stt google locale {locale} refused, using {alternative}", file=sys.stderr, flush=True)
                self._stt_locale_swap[locale] = alternative
                return text
            print(f"stt google failed locale={locale} error={exc}", file=sys.stderr, flush=True)
            raise AudioError(RECOGNITION_FAILED) from exc
