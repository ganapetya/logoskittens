"""HTTP client for the audio engine."""

import io
import sys
import wave

import httpx

from logoskittens.wire import PCM_CHANNELS, PCM_SAMPLE_RATE, PCM_SAMPLE_WIDTH


class AudioError(RuntimeError):
    pass


class AudioClient:
    def __init__(self, base_url: str, timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def transcribe(
        self,
        audio: bytes,
        content_type: str = "application/octet-stream",
        language: str = "no",
        prompt: str = "",
    ) -> str:
        params = {"prompt": prompt} if prompt else None
        try:
            response = httpx.post(
                f"{self.base_url}/transcribe",
                content=audio,
                params=params,
                headers={"Content-Type": content_type, "X-Stt-Language": language or "no"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise AudioError(f"transcribe failed: {exc}") from exc
        if response.status_code == 400:
            # The audio engine could not decode the recording. The decoder's text is for the log, not the page.
            print(
                f"transcribe unreadable bytes={len(audio)} type={content_type} detail={response.text[-300:]!r}",
                file=sys.stderr,
                flush=True,
            )
            raise AudioError("The recording could not be read. Hold Speak and try again.")
        if response.status_code >= 400:
            raise AudioError(f"transcribe HTTP {response.status_code}: {response.text[:300]}")
        return str(response.json().get("text", "")).strip()

    def convert16k(self, audio: bytes, content_type: str = "application/octet-stream") -> bytes:
        """A recording Google cannot read as is (Safari's mp4) as 16 kHz mono 16-bit WAV."""
        try:
            response = httpx.post(
                f"{self.base_url}/convert16k",
                content=audio,
                headers={"Content-Type": content_type},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise AudioError(f"convert failed: {exc}") from exc
        if response.status_code >= 400:
            print(f"convert unreadable bytes={len(audio)} type={content_type}", file=sys.stderr, flush=True)
            raise AudioError("The recording could not be read. Hold Speak and try again.")
        return response.content

    def synthesize(self, text: str, language_code: str, voice_id: str) -> bytes:
        try:
            response = httpx.post(
                f"{self.base_url}/synthesize",
                json={
                    "text": text,
                    "language_code": language_code,
                    "voice_model_id": voice_id,
                },
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise AudioError(f"synthesize failed: {exc}") from exc
        if response.status_code >= 400:
            raise AudioError(f"synthesize HTTP {response.status_code}: {response.text[:300]}")
        return wav_to_pcm(response.content)


def wav_to_pcm(wav_bytes: bytes) -> bytes:
    """Resample a WAV to signed 16-bit mono PCM at PCM_SAMPLE_RATE using the stdlib when rates match.

    The audio engine already returns 22050 Hz mono s16le WAV. This strips the header.
    """
    with wave.open(io.BytesIO(wav_bytes), "rb") as handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if channels != PCM_CHANNELS or width != PCM_SAMPLE_WIDTH or rate != PCM_SAMPLE_RATE:
        raise AudioError(
            f"expected {PCM_SAMPLE_RATE} Hz mono s16le WAV, got {rate} Hz, "
            f"{channels} ch, {width * 8}-bit"
        )
    return frames
