#!/bin/sh
# Exercise the audio engine: one Norwegian line out, then that audio back in.
set -eu
base="${AUDIO_ENGINE_URL:-http://127.0.0.1:8081}"
out="${1:-/tmp/lk-check.wav}"
curl -sf -X POST "$base/synthesize" \
  -H 'content-type: application/json' \
  -d '{"text":"Hei, god dag. Jeg heter Kari.","voice_model_id":"no_NO-talesyntese-medium"}' \
  -o "$out"
python3 -c 'import sys, wave
w = wave.open(sys.argv[1])
assert w.getnchannels() == 1 and w.getsampwidth() == 2 and w.getframerate() == 22050 and w.getnframes() > 1000, (
    w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes())
print("wav", w.getframerate(), w.getnframes())' "$out"
curl -sf -X POST "$base/transcribe" --data-binary @"$out" -H 'content-type: audio/wav'
echo
