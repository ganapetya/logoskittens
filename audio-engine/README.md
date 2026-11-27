# audio-engine

Piper TTS in this image. Speech recognition is NbAiLab `nb-whisper-large` on the host, so it can use the host GPU. Docker on macOS cannot see the Apple GPU, so the recognizer stays outside the container on every OS.

Start the recognizer before `docker compose up`. macOS and Ubuntu: `./scripts/host_whisper.sh`. Windows: `.\scripts\host_whisper.ps1`. It listens on port 8082 and switches language on port 8083. The image downloads `no_NO-nvcc-medium`, `no_NO-talesyntese-medium`, `en_US-ryan-medium`, and `en_US-lessac-medium` during `docker compose build`. Weights are not committed.

| Weight | Where |
| --- | --- |
| `ggml-nb-whisper-large.bin` | Host, Hugging Face `NbAiLab/nb-whisper-large` `ggml-model.bin` |
| `ggml-silero-v6.2.0.bin` | Host, beside the whisper server |
| `no_NO-talesyntese-medium` | This image. This is the Norwegian lesson voice for both partners. |
| `no_NO-nvcc-medium` | This image, Hugging Face `rhasspy/piper-voices` `no/no_NO/nvcc/medium`. Ten speakers. The lesson does not select it. |

A voice id may name a speaker after `@`, for example `no_NO-nvcc-medium@KON`. `POST /synthesize` passes that speaker to Piper.

`POST /transcribe` accepts any ffmpeg-readable body, converts it, and forwards it to the host recognizer. The response is `{"text", "language"}`. The recognizer is locked to Norwegian (`-l no`). Silence gated by Silero yields an empty string.

`POST /synthesize` accepts `{"text", "language_code", "voice_model_id"}` and returns 22050 Hz mono 16-bit WAV.
