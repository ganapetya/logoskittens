"""Google Cloud Text-to-Speech and Speech-to-Text v1 over REST, through one pooled httpx client.

Ported from shakti-practice `speak/platform/speech.py`, without its LogosCat
billing and without the gRPC SDK. The client is reused, so a turn does not pay
for a TLS handshake. Calls are synchronous. The hub calls them from worker threads.

Credentials:
- an API key, sent as `X-Goog-Api-Key`;
- a service-account JSON, exchanged for an OAuth access token that is cached
  and renewed in the background before it expires, so the exchange is never on a turn.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import sys
import threading
import time
import wave

import httpx

from logoskittens.speech.settings import SpeechSettings

TTS_URL = "https://texttospeech.googleapis.com/v1"
STT_URL = "https://speech.googleapis.com/v1"
SCOPE = "https://www.googleapis.com/auth/cloud-platform"
TOKEN_URI = "https://oauth2.googleapis.com/token"
# A token with less than this left is renewed in the background while it is still used.
RENEW_BEFORE_S = 600

_PHRASE_MAX = 100
_PHRASES_MAX = 500


class GoogleError(RuntimeError):
    def __init__(self, message: str, status: int = 0):
        super().__init__(message)
        self.status = status

    @property
    def retryable(self) -> bool:
        return self.status == 429 or self.status >= 500 or self.status == 0


def clean_text(text: str) -> str:
    """Hebrew points read letter by letter, so they go. A line with no end mark gets a full stop."""
    spoken = re.sub(r"[֑-ׇ]", "", " ".join((text or "").split()))
    if spoken and not spoken.endswith((".", "!", "?", "…", ":", ";", ",", '"', "»", "”", ")")):
        spoken += "."
    return spoken


def phrases_from(prompt: str) -> list[str]:
    """The game bias prompt as adaptation phrases. A comma list is words; anything else is one sentence."""
    text = " ".join((prompt or "").split())
    if not text:
        return []
    parts = [part.strip() for part in text.split(", ")] if ", " in text else [text]
    phrases: list[str] = []
    for part in parts:
        while len(part) > _PHRASE_MAX:
            cut = part.rfind(" ", 0, _PHRASE_MAX)
            cut = cut if cut > 0 else _PHRASE_MAX
            phrases.append(part[:cut].strip())
            part = part[cut:].strip()
        if part:
            phrases.append(part)
    return phrases[:_PHRASES_MAX]


def audio_format(content: bytes, content_type: str) -> tuple[str, int | None, int]:
    """(encoding, sample rate, channels) Google v1 reads as is. An empty encoding needs converting first."""
    mime = (content_type or "").split(";")[0].strip().lower()
    if content[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(content), "rb") as handle:
                if handle.getsampwidth() == 2:
                    return "LINEAR16", handle.getframerate(), handle.getnchannels()
        except (wave.Error, EOFError):
            pass
        return "", None, 1
    if content[:4] == b"\x1a\x45\xdf\xa3" or mime == "audio/webm":
        return "WEBM_OPUS", 48000, 1
    if content[:4] == b"OggS" or mime == "audio/ogg":
        return "OGG_OPUS", 48000, 1
    return "", None, 1


class GoogleSpeech:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        self._transport = transport
        self._client: httpx.Client | None = None
        self._lock = threading.Lock()
        # credential digest -> (token, expires_at)
        self._tokens: dict[str, tuple[str, float]] = {}
        self._renewing: set[str] = set()

    # -- transport -----------------------------------------------------------------

    def client(self) -> httpx.Client:
        with self._lock:
            if self._client is None:
                from logoskittens.speech.voices import config

                doc = config()
                connect = float(doc.get("connect_timeout_s") or 2)
                self._client = httpx.Client(
                    timeout=httpx.Timeout(float(doc.get("stt_timeout_s") or 8), connect=connect),
                    limits=httpx.Limits(max_connections=16, max_keepalive_connections=8, keepalive_expiry=300),
                    transport=self._transport,
                )
            return self._client

    def _timeout(self, kind: str) -> httpx.Timeout:
        from logoskittens.speech.voices import config

        doc = config()
        read = float(doc.get(f"{kind}_timeout_s") or (6 if kind == "tts" else 8))
        return httpx.Timeout(read, connect=float(doc.get("connect_timeout_s") or 2))

    def _headers(self, settings: SpeechSettings) -> dict[str, str]:
        if not settings.has_credential:
            raise GoogleError("No Google credential is set.", 401)
        if settings.credential_kind == "api_key":
            return {"X-Goog-Api-Key": settings.credential.strip()}
        return {"Authorization": f"Bearer {self._token(settings.credential)}"}

    def _call(self, method: str, url: str, settings: SpeechSettings, kind: str, **kwargs) -> dict:
        try:
            response = self.client().request(
                method, url, headers=self._headers(settings), timeout=self._timeout(kind), **kwargs
            )
        except httpx.TimeoutException as exc:
            raise GoogleError(f"Google {kind} timed out", 0) from exc
        except httpx.HTTPError as exc:
            raise GoogleError(f"Google {kind} failed: {exc}", 0) from exc
        if response.status_code >= 400:
            raise GoogleError(_error_text(response), response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise GoogleError(f"Google {kind} sent no JSON", response.status_code) from exc

    # -- service-account tokens -----------------------------------------------------

    def _token(self, credential: str) -> str:
        digest = hashlib.sha256(credential.encode("utf-8")).hexdigest()
        cached = self._tokens.get(digest)
        now = time.time()
        if cached and cached[1] - now > 60:
            if cached[1] - now < RENEW_BEFORE_S:
                self._renew_later(digest, credential)
            return cached[0]
        return self._exchange(digest, credential)

    def _renew_later(self, digest: str, credential: str) -> None:
        with self._lock:
            if digest in self._renewing:
                return
            self._renewing.add(digest)

        def work() -> None:
            try:
                self._exchange(digest, credential)
            except GoogleError as exc:
                print(f"google token renew failed: {exc}", file=sys.stderr, flush=True)
            finally:
                with self._lock:
                    self._renewing.discard(digest)

        threading.Thread(target=work, name="google-token", daemon=True).start()

    def _exchange(self, digest: str, credential: str) -> str:
        info = parse_service_account(credential)
        try:
            from google.auth import crypt, jwt
        except ImportError as exc:  # pragma: no cover - the dependency ships with the hub
            raise GoogleError("google-auth is not installed", 500) from exc
        now = int(time.time())
        token_uri = str(info.get("token_uri") or TOKEN_URI)
        signer = crypt.RSASigner.from_service_account_info(info)
        assertion = jwt.encode(
            signer,
            {"iss": info["client_email"], "scope": SCOPE, "aud": token_uri, "iat": now, "exp": now + 3600},
        )
        try:
            response = self.client().post(
                token_uri,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion.decode() if isinstance(assertion, bytes) else assertion,
                },
                timeout=self._timeout("tts"),
            )
        except httpx.HTTPError as exc:
            raise GoogleError(f"Google sign-in failed: {exc}", 0) from exc
        if response.status_code >= 400:
            raise GoogleError(f"Google sign-in refused: {_error_text(response)}", 401)
        body = response.json()
        token = str(body.get("access_token") or "")
        if not token:
            raise GoogleError("Google sign-in sent no token", 401)
        self._tokens[digest] = (token, time.time() + float(body.get("expires_in") or 3600))
        return token

    # -- the three calls --------------------------------------------------------------

    def synthesize(self, settings: SpeechSettings, text: str, *, locale: str, voice_name: str, sample_rate: int) -> bytes:
        """LINEAR16 at `sample_rate`. Google wraps it in a WAV header."""
        voice = {"languageCode": locale or voice_name[:5], "name": voice_name}
        body = self._call(
            "POST",
            f"{TTS_URL}/text:synthesize",
            settings,
            "tts",
            json={
                "input": {"text": text},
                "voice": voice,
                "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": sample_rate},
            },
        )
        content = body.get("audioContent") or ""
        if not content:
            raise GoogleError("Google voice sent no audio", 502)
        return base64.b64decode(content)

    def recognize(
        self,
        settings: SpeechSettings,
        content: bytes,
        *,
        encoding: str,
        sample_rate: int | None,
        channels: int,
        locale: str,
        phrases: list[str],
        model: str = "",
    ) -> str:
        config: dict = {"encoding": encoding, "languageCode": locale, "enableAutomaticPunctuation": True}
        if sample_rate:
            config["sampleRateHertz"] = sample_rate
        if channels and channels > 1:
            config["audioChannelCount"] = channels
        if model:
            config["model"] = model
        if phrases:
            config["speechContexts"] = [{"phrases": phrases}]
        body = self._call(
            "POST",
            f"{STT_URL}/speech:recognize",
            settings,
            "stt",
            json={"config": config, "audio": {"content": base64.b64encode(content).decode("ascii")}},
        )
        pieces = []
        for result in body.get("results") or []:
            alternatives = result.get("alternatives") or []
            if alternatives:
                pieces.append(str(alternatives[0].get("transcript") or "").strip())
        return " ".join(piece for piece in pieces if piece).strip()

    def voices(self, settings: SpeechSettings, locale: str) -> list[dict]:
        body = self._call("GET", f"{TTS_URL}/voices", settings, "tts", params={"languageCode": locale})
        found = []
        for item in body.get("voices") or []:
            name = str(item.get("name") or "")
            if not name.startswith(locale):
                continue
            gender = {"MALE": "man", "FEMALE": "woman"}.get(str(item.get("ssmlGender") or ""), "")
            found.append({"name": name, "gender": gender})
        return found

    def warm(self, settings: SpeechSettings) -> None:
        """Open the connection (and fetch a token) before a turn needs them. Errors only go to the log."""
        if not settings.has_credential:
            return
        try:
            self.voices(settings, "en-US")
        except GoogleError as exc:
            print(f"google warm failed: {exc}", file=sys.stderr, flush=True)


def parse_service_account(credential: str) -> dict:
    try:
        info = json.loads(credential)
    except ValueError as exc:
        raise GoogleError("The service-account JSON could not be read.", 400) from exc
    if not isinstance(info, dict) or not info.get("client_email") or not info.get("private_key"):
        raise GoogleError("The service-account JSON needs client_email and private_key.", 400)
    return info


def _error_text(response: httpx.Response) -> str:
    try:
        body = response.json()
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict) and error.get("message"):
            return f"HTTP {response.status_code}: {error['message']}"[:400]
        if isinstance(error, str):
            return f"HTTP {response.status_code}: {body.get('error_description') or error}"[:400]
    except ValueError:
        pass
    return f"HTTP {response.status_code}: {response.text[:300]}"
