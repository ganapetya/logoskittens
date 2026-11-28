"""Google speech as an option: switches, the credential that never leaves the hub, voices by gender, fallback.

No test reaches Google. `httpx.MockTransport` plays the two APIs.
"""

import base64
import io
import json
import wave

import httpx
import pytest
from fastapi.testclient import TestClient

from fakes import FakeAudio, fake_complete

from logoskittens.api import create_app
from logoskittens.audio import AudioError
from logoskittens.persistence import Store
from logoskittens.session import SessionService
from logoskittens.speech import settings as speech_settings
from logoskittens.speech import voices
from logoskittens.speech.google import GoogleSpeech, audio_format, clean_text, phrases_from
from logoskittens.speech.router import RECOGNITION_FAILED, SpeechRouter

KEY = "AIzaSyTESTKEY-0123456789abcd"


def _wav(rate: int, frames: bytes = b"\x01\x00" * 400, channels: int = 1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames)
    return buffer.getvalue()


class FakeLocal(FakeAudio):
    def __init__(self):
        self.spoken: list[str] = []
        self.heard = 0
        self.converted = 0

    def synthesize(self, text, language_code, voice_id):
        self.spoken.append(voice_id)
        return b"\x09\x00" * 10

    def transcribe(self, audio, content_type="application/octet-stream", language="en", prompt=""):
        self.heard += 1
        return "whisper heard"

    def convert16k(self, audio, content_type="application/octet-stream"):
        self.converted += 1
        return _wav(16000)


class Google:
    """Records each request and answers like Google, or fails the way a test asks."""

    def __init__(self, fail_tts: Exception | int | None = None, stt_status: int = 200, refuse_locale: str = ""):
        self.requests: list[httpx.Request] = []
        self.fail_tts = fail_tts
        self.stt_status = stt_status
        self.refuse_locale = refuse_locale

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path.endswith("text:synthesize"):
            if isinstance(self.fail_tts, Exception):
                raise self.fail_tts
            if isinstance(self.fail_tts, int):
                return httpx.Response(self.fail_tts, json={"error": {"message": "busy"}})
            body = json.loads(request.content)
            rate = body["audioConfig"]["sampleRateHertz"]
            return httpx.Response(200, json={"audioContent": base64.b64encode(_wav(rate)).decode()})
        if path.endswith("speech:recognize"):
            config = json.loads(request.content)["config"]
            if config["languageCode"] == self.refuse_locale:
                return httpx.Response(400, json={"error": {"message": "Invalid recognition 'config': bad language code."}})
            if self.stt_status != 200:
                return httpx.Response(self.stt_status, json={"error": {"message": "nope"}})
            return httpx.Response(200, json={"results": [{"alternatives": [{"transcript": " Google heard "}]}]})
        if path.endswith("/voices"):
            locale = request.url.params["languageCode"]
            return httpx.Response(
                200,
                json={
                    "voices": [
                        {"name": f"{locale}-Chirp3-HD-Charon", "ssmlGender": "MALE"},
                        {"name": f"{locale}-Wavenet-B", "ssmlGender": "MALE"},
                        {"name": f"{locale}-Wavenet-A", "ssmlGender": "FEMALE"},
                        {"name": "xx-XX-Wavenet-A", "ssmlGender": "FEMALE"},
                    ]
                },
            )
        return httpx.Response(404)

    def bodies(self, suffix: str) -> list[dict]:
        return [json.loads(item.content) for item in self.requests if item.url.path.endswith(suffix)]


def _google_on(tts: bool = True, stt: bool = True, **extra) -> None:
    speech_settings.replace(
        speech_settings.SpeechSettings(
            tts_provider="google" if tts else "local",
            stt_provider="google" if stt else "local",
            credential_kind="api_key",
            credential=KEY,
            **extra,
        )
    )


def _router(google: Google) -> tuple[SpeechRouter, FakeLocal]:
    local = FakeLocal()
    return SpeechRouter(local, GoogleSpeech(httpx.MockTransport(google))), local


# -- voices by gender -----------------------------------------------------------------


def test_local_speech_keeps_the_piper_voice_ids():
    from logoskittens.personalities import get_personality
    from logoskittens.teachers import get_teacher

    assert get_personality("he", "maya").voice_id == "he_IL-saspeech-medium"
    assert get_teacher("he").voice_id == "he_IL-saspeech-medium"


def test_google_voice_gives_maya_a_womans_voice_and_savelij_another_man():
    from logoskittens.personalities import get_personality
    from logoskittens.teachers import get_teacher

    _google_on(stt=False)
    assert get_personality("he", "maya").voice_id == "g:he-IL-Wavenet-A|he_IL-saspeech-medium"
    assert get_personality("he", "noam").voice_id == "g:he-IL-Wavenet-B|he_IL-saspeech-medium"
    assert get_teacher("he").voice_id == "g:he-IL-Wavenet-D|he_IL-saspeech-medium"
    assert get_personality("en", "mary").voice_id == "g:en-US-Wavenet-C|en_US-lessac-medium"


def test_the_teacher_is_another_speaker_and_skips_studio():
    # nb-NO-Standard-G is the man's own speaker, so Savelij moves to a Chirp3-HD man.
    assert voices.defaults("nb") == {
        "man": "nb-NO-Wavenet-G",
        "woman": "nb-NO-Wavenet-F",
        "teacher": "nb-NO-Chirp3-HD-Charon",
    }
    # de-DE-Studio-B is skipped. Ukrainian has only Chirp3-HD men.
    assert voices.defaults("de")["teacher"] == "de-DE-Chirp3-HD-Charon"
    assert voices.defaults("uk") == {
        "man": "uk-UA-Chirp3-HD-Charon",
        "woman": "uk-UA-Wavenet-B",
        "teacher": "uk-UA-Chirp3-HD-Fenrir",
    }


def test_the_teacher_uses_the_mans_voice_when_there_is_no_other_speaker(monkeypatch):
    monkeypatch.setattr(voices, "entry", lambda _lang: {"man": ["xx-XX-Wavenet-A", "xx-XX-Standard-A"], "woman": []})
    found = voices.defaults("xx")
    assert found["teacher"] == "xx-XX-Wavenet-A"
    assert found["woman"] == "xx-XX-Wavenet-A"


def test_a_voice_chosen_on_the_page_wins_and_moves_the_teacher():
    _google_on(voices={"en": {"man": "en-US-Wavenet-B"}})
    assert voices.chosen("en", "man") == "en-US-Wavenet-B"
    assert voices.chosen("en", "teacher") == "en-US-Wavenet-A"
    assert voices.chosen("en", "woman") == "en-US-Wavenet-C"


# -- voice ------------------------------------------------------------------------------


def test_google_voice_returns_22050_pcm_without_the_header_and_caches_it():
    google = Google()
    router, local = _router(google)
    _google_on(stt=False)
    pcm = router.synthesize("שָׁלוֹם", "he", "g:he-IL-Wavenet-A|he_IL-saspeech-medium")
    assert pcm == b"\x01\x00" * 400
    body = google.bodies("text:synthesize")[0]
    assert body["audioConfig"] == {"audioEncoding": "LINEAR16", "sampleRateHertz": 22050}
    assert body["voice"] == {"languageCode": "he-IL", "name": "he-IL-Wavenet-A"}
    assert body["input"]["text"] == "שלום."
    assert google.requests[0].headers["X-Goog-Api-Key"] == KEY
    router.synthesize("שָׁלוֹם", "he", "g:he-IL-Wavenet-A|he_IL-saspeech-medium")
    assert len(google.bodies("text:synthesize")) == 1
    assert local.spoken == []


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("slow"), 500, 403])
def test_a_google_voice_failure_speaks_the_line_with_piper(failure, capfd):
    router, local = _router(Google(fail_tts=failure))
    _google_on(stt=False)
    assert router.synthesize("Hello there.", "en", "g:en-US-Wavenet-A|en_US-ryan-medium") == b"\x09\x00" * 10
    assert local.spoken == ["en_US-ryan-medium"]
    from logoskittens.speech.router import last_tts_via

    assert last_tts_via() == "fallback"
    assert "tts fallback voice=en-US-Wavenet-A" in capfd.readouterr().err


def test_a_composite_id_speaks_piper_once_google_voice_is_off():
    google = Google()
    router, local = _router(google)
    assert router.synthesize("Hi.", "en", "g:en-US-Wavenet-A|en_US-ryan-medium") == b"\x09\x00" * 10
    assert local.spoken == ["en_US-ryan-medium"]
    assert google.requests == []


def test_background_prefetch_retries_a_busy_google_once(monkeypatch):
    calls = {"n": 0}
    good = Google()

    def flaky(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": {"message": "slow down"}})
        return good(request)

    monkeypatch.setattr("logoskittens.speech.router.time.sleep", lambda _s: None)
    local = FakeLocal()
    router = SpeechRouter(local, GoogleSpeech(httpx.MockTransport(flaky)))
    _google_on(stt=False)
    assert router.synthesize_background("Hei.", "nb", "g:nb-NO-Wavenet-G|no_NO-talesyntese-medium") == b"\x01\x00" * 400
    assert calls["n"] == 2
    assert local.spoken == []


# -- recognition --------------------------------------------------------------------------


def test_audio_formats_go_to_google_as_they_are():
    assert audio_format(_wav(16000), "audio/wav") == ("LINEAR16", 16000, 1)
    assert audio_format(_wav(44100, b"\x00\x00" * 800, channels=2), "") == ("LINEAR16", 44100, 2)
    assert audio_format(b"\x1a\x45\xdf\xa3" + b"\x00" * 200, "audio/webm;codecs=opus") == ("WEBM_OPUS", 48000, 1)
    assert audio_format(b"OggS" + b"\x00" * 200, "audio/ogg") == ("OGG_OPUS", 48000, 1)
    assert audio_format(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 200, "audio/mp4")[0] == ""


def test_google_hears_a_webm_recording_with_the_norwegian_locale_and_model():
    google = Google()
    router, local = _router(google)
    _google_on(tts=False)
    text = router.transcribe(b"\x1a\x45\xdf\xa3" + b"\x00" * 300, "audio/webm", language="no", prompt="fjord, tunnel")
    assert text == "Google heard"
    config = google.bodies("speech:recognize")[0]["config"]
    assert config["languageCode"] == "no-NO"
    assert config["model"] == "latest_long"
    assert config["encoding"] == "WEBM_OPUS"
    assert config["speechContexts"] == [{"phrases": ["fjord", "tunnel"]}]
    assert local.heard == 0 and local.converted == 0


def test_an_mp4_recording_is_converted_by_the_audio_engine_first():
    google = Google()
    router, local = _router(google)
    _google_on(tts=False)
    router.transcribe(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 300, "audio/mp4", language="en")
    assert local.converted == 1
    config = google.bodies("speech:recognize")[0]["config"]
    assert (config["encoding"], config["sampleRateHertz"], config["languageCode"]) == ("LINEAR16", 16000, "en-US")


def test_a_google_recognition_failure_asks_to_speak_again_and_does_not_try_whisper():
    router, local = _router(Google(stt_status=500))
    _google_on(tts=False)
    with pytest.raises(AudioError, match=RECOGNITION_FAILED):
        router.transcribe(_wav(16000), "audio/wav", language="de")
    assert local.heard == 0


def test_a_refused_hebrew_locale_moves_to_the_alternative_once():
    google = Google(refuse_locale="iw-IL")
    router, _local = _router(google)
    _google_on(tts=False)
    assert router.transcribe(_wav(16000), "audio/wav", language="he") == "Google heard"
    assert router.transcribe(_wav(16000), "audio/wav", language="he") == "Google heard"
    locales = [body["config"]["languageCode"] for body in google.bodies("speech:recognize")]
    assert locales == ["iw-IL", "he-IL", "he-IL"]


def test_local_recognition_stays_whisper():
    google = Google()
    router, local = _router(google)
    assert router.transcribe(_wav(16000), "audio/wav", language="en") == "whisper heard"
    assert google.requests == []


def test_phrases_and_clean_text():
    assert phrases_from("") == []
    assert phrases_from("one sentence here") == ["one sentence here"]
    long = " ".join(["word"] * 40)
    assert all(len(item) <= 100 for item in phrases_from(long))
    assert clean_text("  Hei  der ") == "Hei der."
    assert clean_text("Er du klar?") == "Er du klar?"


# -- the Settings page routes ---------------------------------------------------------------


def _client(tmp_path, google: Google | None = None) -> tuple[TestClient, SessionService]:
    router = SpeechRouter(FakeLocal(), GoogleSpeech(httpx.MockTransport(google or Google())))
    service = SessionService(Store(tmp_path / "speech.db"), router, fake_complete)  # type: ignore[arg-type]
    return TestClient(create_app(service)), service


def test_the_credential_never_comes_back_and_survives_a_restart(tmp_path):
    client, service = _client(tmp_path)
    assert client.get("/speech/settings").json()["credential_set"] is False
    saved = client.put(
        "/speech/settings",
        json={"credential_kind": "api_key", "credential": KEY, "tts_provider": "google"},
    )
    assert saved.status_code == 200
    assert KEY not in saved.text
    shown = client.get("/speech/settings").json()
    assert KEY not in json.dumps(shown)
    assert shown["credential_hint"] == "…abcd"
    assert shown["tts_provider"] == "google"
    assert {item["id"] for item in shown["languages"]} == {"en", "nb", "uk", "de", "he"}
    speech_settings.reset()
    create_app(service)
    assert speech_settings.current().credential == KEY
    assert speech_settings.current().google_tts


def test_google_cannot_be_turned_on_without_a_credential(tmp_path):
    client, _service = _client(tmp_path)
    refused = client.put("/speech/settings", json={"stt_provider": "google"})
    assert refused.status_code == 400
    assert client.put("/speech/settings", json={"credential_kind": "api_key", "credential": "short"}).status_code == 400
    bad_json = client.put("/speech/settings", json={"credential_kind": "service_account", "credential": '{"a": 1}'})
    assert bad_json.status_code == 400


def test_removing_the_credential_turns_both_switches_off(tmp_path):
    client, _service = _client(tmp_path)
    client.put(
        "/speech/settings",
        json={"credential_kind": "api_key", "credential": KEY, "tts_provider": "google", "stt_provider": "google"},
    )
    shown = client.delete("/speech/credential").json()
    assert (shown["credential_set"], shown["tts_provider"], shown["stt_provider"]) == (False, "local", "local")


def test_voice_choices_are_checked_and_stored(tmp_path):
    client, _service = _client(tmp_path)
    client.put("/speech/settings", json={"credential_kind": "api_key", "credential": KEY})
    assert client.put("/speech/settings", json={"voices": {"he": {"woman": "not a voice"}}}).status_code == 400
    assert client.put("/speech/settings", json={"voices": {"zz": {"man": "en-US-Wavenet-A"}}}).status_code == 400
    shown = client.put("/speech/settings", json={"voices": {"he": {"woman": "he-IL-Wavenet-C"}}}).json()
    hebrew = next(item for item in shown["languages"] if item["id"] == "he")
    assert hebrew["voices"]["woman"] == "he-IL-Wavenet-C"
    assert hebrew["voices"]["man"] == "he-IL-Wavenet-B"
    # A second pick keeps the first; an empty name is the default again.
    shown = client.put("/speech/settings", json={"voices": {"he": {"man": "he-IL-Wavenet-D"}}}).json()
    hebrew = next(item for item in shown["languages"] if item["id"] == "he")
    assert (hebrew["voices"]["woman"], hebrew["voices"]["man"], hebrew["voices"]["teacher"]) == (
        "he-IL-Wavenet-C",
        "he-IL-Wavenet-D",
        "he-IL-Wavenet-B",
    )
    shown = client.put("/speech/settings", json={"voices": {"he": {"man": ""}}}).json()
    hebrew = next(item for item in shown["languages"] if item["id"] == "he")
    assert hebrew["voices"]["man"] == "he-IL-Wavenet-B"


def test_voices_test_and_sample_routes(tmp_path):
    client, _service = _client(tmp_path)
    shipped = client.get("/speech/voices", params={"language_id": "uk"}).json()
    assert shipped["live"] is False
    client.put("/speech/settings", json={"credential_kind": "api_key", "credential": KEY})
    live = client.get("/speech/voices", params={"language_id": "uk"}).json()
    assert live["live"] is True
    assert [item["name"] for item in live["voices"]] == ["uk-UA-Wavenet-A", "uk-UA-Wavenet-B", "uk-UA-Chirp3-HD-Charon"]
    assert client.post("/speech/test").json()["ok"] is True
    sample = client.post("/speech/sample", json={"language_id": "he", "role": "woman"}).json()
    assert base64.b64decode(sample["pcm"]) == b"\x01\x00" * 400


def test_start_does_not_switch_whisper_while_google_hears(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr("logoskittens.api.switch_recognizer", lambda language_id: calls.append(language_id) or {"ok": True})
    client, _service = _client(tmp_path)
    client.put(
        "/speech/settings", json={"credential_kind": "api_key", "credential": KEY, "stt_provider": "google"}
    )
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        hello = socket.receive_json()
    assert hello["recognizer"]["detail"] == "Google recognition"
    assert calls == []


def test_a_service_account_signs_in_once_and_reuses_its_token():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    account = json.dumps({"type": "service_account", "client_email": "lk@example.iam.gserviceaccount.com", "private_key": pem})
    google = Google()
    exchanges = []

    def handler(request):
        if request.url.host == "oauth2.googleapis.com":
            exchanges.append(request)
            return httpx.Response(200, json={"access_token": "ya29.test", "expires_in": 3600})
        return google(request)

    router = SpeechRouter(FakeLocal(), GoogleSpeech(httpx.MockTransport(handler)))
    speech_settings.replace(
        speech_settings.SpeechSettings(tts_provider="google", credential_kind="service_account", credential=account)
    )
    assert speech_settings.current().credential_hint() == "lk@example.iam.gserviceaccount.com"
    router.synthesize("One.", "en", "g:en-US-Wavenet-A|en_US-ryan-medium")
    router.synthesize("Two.", "en", "g:en-US-Wavenet-A|en_US-ryan-medium")
    assert len(exchanges) == 1
    assert b"grant_type=urn" in exchanges[0].content
    assert [item.headers["Authorization"] for item in google.requests] == ["Bearer ya29.test"] * 2
