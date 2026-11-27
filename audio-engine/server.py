"""Piper TTS, plus a proxy to the host whisper server."""

import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid
import wave
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

WHISPER_URL = os.environ.get("WHISPER_URL", "http://host.docker.internal:8082").rstrip("/")
PIPER_DIR = Path(os.environ.get("PIPER_MODEL_DIR", "/models/piper"))
DEFAULT_VOICE = os.environ.get("PIPER_VOICE_ID", "no_NO-talesyntese-medium")
SAMPLE_RATE = 22050

app = FastAPI(title="LogosKittens audio engine")


class SynthesizeRequest(BaseModel):
    text: str
    language_code: str = "nb"
    voice_model_id: str = DEFAULT_VOICE


@app.get("/health")
def health():
    voice = _voice_path(DEFAULT_VOICE)
    whisper_ok = _whisper_ready()
    body = {
        "status": "ok" if whisper_ok and voice.is_file() else "degraded",
        "whisper": whisper_ok,
        "whisper_model": "nb-whisper-large",
        "recognizer": "host",
        "voice": voice.is_file(),
        "voice_id": DEFAULT_VOICE,
    }
    if body["status"] != "ok":
        return JSONResponse(body, status_code=503)
    return body


@app.post("/transcribe")
async def transcribe(request: Request):
    raw = await request.body()
    if not raw:
        return {"text": "", "language": "no"}
    wav = _to_16k(raw)
    if isinstance(wav, Response):
        return wav
    language = request.headers.get("x-stt-language", "no") or "no"
    prompt = request.query_params.get("prompt", "") or ""
    if prompt:
        print(f"stt prompt {prompt}", flush=True)
    try:
        text = _infer(wav, language, prompt)
    except urllib.error.URLError as exc:
        return Response(f"recognizer unavailable: {exc.reason}", status_code=502)
    return {"text": text, "language": language}


@app.post("/synthesize")
def synthesize(body: SynthesizeRequest):
    voice_id = body.voice_model_id or DEFAULT_VOICE
    model_id, speaker = _split_voice(voice_id)
    voice = _voice_path(model_id)
    if not voice.is_file():
        return Response(f"unknown voice {model_id}", status_code=400)
    text = body.text.strip()
    if not text:
        return Response("text is empty", status_code=400)
    loaded = _load_voice(voice)
    speaker_id = _speaker_id(loaded.config.speaker_id_map, speaker)
    if speaker and speaker_id is None:
        return Response(f"unknown speaker {speaker}", status_code=400)
    from piper.config import SynthesisConfig

    syn_config = SynthesisConfig(speaker_id=speaker_id) if speaker_id is not None else None
    with tempfile.NamedTemporaryFile(suffix=".wav") as handle:
        with wave.open(handle.name, "wb") as wav_file:
            if hasattr(loaded, "synthesize_wav"):
                loaded.synthesize_wav(text, wav_file, syn_config=syn_config)
            else:
                loaded.synthesize(text, wav_file)
        data = Path(handle.name).read_bytes()
    normalized = _to_22050(data)
    return Response(normalized, media_type="audio/wav")


_VOICE_CACHE: dict[str, object] = {}


def _split_voice(voice_id: str) -> tuple[str, str | None]:
    """`model@SPEAKER` selects one speaker inside a multi-speaker Piper file."""
    model, sep, speaker = voice_id.partition("@")
    if not sep or not speaker:
        return voice_id, None
    return model, speaker


def _speaker_id(mapping, speaker: str | None) -> int | None:
    if not speaker:
        return None
    if speaker not in mapping:
        return None
    return int(mapping[speaker])


def _voice_path(voice_id: str) -> Path:
    model_id, _speaker = _split_voice(voice_id)
    return PIPER_DIR / f"{model_id}.onnx"


def _load_voice(path: Path):
    key = str(path)
    cached = _VOICE_CACHE.get(key)
    if cached is not None:
        return cached
    from piper import PiperVoice

    loaded = PiperVoice.load(key)
    _VOICE_CACHE[key] = loaded
    return loaded


def _whisper_ready() -> bool:
    try:
        with urllib.request.urlopen(WHISPER_URL + "/", timeout=2) as response:
            return response.status < 500
    except (urllib.error.URLError, TimeoutError):
        return False


def _to_16k(raw: bytes) -> bytes | Response:
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        source = folder / "input.bin"
        wav = folder / "speech.wav"
        source.write_bytes(raw)
        convert = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(wav),
            ],
            capture_output=True,
        )
        if convert.returncode != 0:
            detail = convert.stderr.decode(errors="replace")
            print(f"transcribe unreadable bytes={len(raw)} head={raw[:16].hex()} ffmpeg={detail[-600:]!r}", flush=True)
            return Response(detail[-400:], status_code=400)
        return wav.read_bytes()


def _inference_body(wav: bytes, language: str, boundary: str, prompt: str = "") -> bytes:
    parts = [
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="speech.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
        + wav
        + b"\r\n",
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="response_format"\r\n\r\n'
            "json\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="temperature"\r\n\r\n'
            "0\r\n"
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="language"\r\n\r\n'
            f"{language}\r\n"
        ).encode(),
    ]
    if prompt.strip():
        parts.append(
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="prompt"\r\n\r\n'
                f"{prompt.strip()}\r\n"
            ).encode()
        )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)


def _infer(wav: bytes, language: str = "no", prompt: str = "") -> str:
    boundary = uuid.uuid4().hex
    body = _inference_body(wav, language, boundary, prompt)
    request = urllib.request.Request(
        WHISPER_URL + "/inference",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[-400:]
        raise urllib.error.URLError(detail or f"HTTP {exc.code}") from exc
    text = str(payload.get("text", "")).strip()
    return " ".join(text.split())


def _to_22050(wav_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        source = folder / "in.wav"
        target = folder / "out.wav"
        source.write_bytes(wav_bytes)
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(source),
                "-ar",
                str(SAMPLE_RATE),
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(target),
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode()[-400:])
        return target.read_bytes()
