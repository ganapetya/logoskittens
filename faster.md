# Faster first response

Target: the teacher starts speaking within **1.0 s**, aiming at **0.7 s**. This is time-to-first-audio after the learner submits, not time until both actors have finished.

Measured on this machine (MacBook Pro, M4 Pro, 20 GPU cores, 48 GB) with `qwen3:8b` Q4_K_M, thinking off, context 2048, typed `Hei`:

| Slice | Warm | Notes |
| --- | --- | --- |
| Whole turn, wall clock | 2.0 s (3.2 s on the first call after a context reload) | What you feel as 2–4 s |
| Ollama `qwen3:8b` | 1.55 s | 145 prompt tokens, 66 completion tokens, about 42 tokens/s |
| Both Piper voices, then the socket send | about 0.45 s | The hub waits for both before it sends anything |

The GPU is already at 100%. An 8B Q4 model is about 5.2 GB. This chip’s memory bandwidth is 273 GB/s, so the decode ceiling is roughly 50 tokens/s. We measure about 42. There is no GPU switch left that turns 66 tokens into 0.7 s. 66 tokens at the ceiling is already **1.3 s before any audio**.

So anything that still waits for a full 8B JSON, and then for both voices, cannot hit 0.7 s. The attempts below are ordered by how much they should cut time-to-first-speech on a normal greeting. Later items are real, and they are smaller.

The spoken lines are already templates in `cognitive-hub/src/logoskittens/graph.py`. The model only fills a scorecard (`form_ok`, register, corrected form, a pronunciation note, tags, words, one coaching sentence). The wire message stays `ElementSolution`. Speed work changes when that message is sent and how the scorecard is produced.

## 1. Greeting lexicon, skip the model on a hit

**Expected:** 2 s down to well under 0.2 s for `Hei`, `Hallo`, `God dag`, and the broken forms the tests already use. This is the only change that reliably lands under 0.7 s on this hardware.

The live task is a closed drill, not open chat. A small table maps a normalized utterance to the same `TurnAssessment` the graph already consumes. A hit never calls Ollama. A miss falls through to the model, so unknown sentences still work.

Cost: the table is only as good as the forms we list. That is the right trade for this lesson. The 8B model already mislabels plain `Hei`.

## 2. Pre-rendered clips for those templates

**Expected:** removes the whole Piper wait on a hit (the remaining ~0.4 s). Together with 1, first audio can be a file read, around 50–150 ms.

Each live line is one of a few fixed sentences plus the corrected form (`graph.py`, `_teacher_line` / `_sibling_line`). Both actors already share `no_NO-talesyntese-medium`. Render those strings once with Piper, store the 22050 Hz PCM, and attach it in the hub without HTTP. Free-text pronunciation notes stay uncached and are omitted on the fast path, or appended only on a cache miss.

Do this in the same change as the lexicon. A fast decision that still waits on Piper will sit around 0.4–0.6 s and feel unfinished.

## 3. Browser plays a known line immediately

**Expected:** for typed text that is in the same lexicon, sound can start in the page with no hub round trip. Perceived time near 0. The hub still runs and, on a disagreement, replaces the line.

The page already has the text before the socket reply. Ship the same clip set to `virtual-stage` (or have the page hold PCM for the known greetings). The lexicon must be one table shared by the hub and the page, or the two will drift.

Cost: a wrong local guess can start and then be corrected. Keep the table tiny and identical on both sides so that almost never happens. This is the optimistic twin of 1, not a second pedagogy.

## 4. Send the teacher before the sibling exists

**Expected:** about 0.15–0.25 s today, because the two synths are serial and the socket opens only after both (`session.py`, `turn_from_text`). After 2, this is nearly free, and it still matters on a cache miss.

Change the turn so the first `ElementSolution` (teacher, with PCM) is sent as soon as it is ready. The sibling follows in a second message. The page already starts an animation when playback starts; it should play a partial turn instead of waiting for a pair.

## 5. Make a cache miss a few tokens, or a tiny classifier

**Expected:** takes unknown sentences from ~1.5 s of 8B time to about 0.05–0.4 s of decision time. With 2 and 4, those turns can land inside 1.0 s, and many inside 0.7 s.

Two ways, in the order to try them:

- Keep a local model, but stop asking for a 66-token JSON. A compact label is enough for the compiler, for example form, register, and the corrected string. Ten tokens on this 8B is about 0.25 s at the measured rate. Constrained decoding (llama.cpp GBNF, Outlines, or llguidance) is how you force that shape and stop at the end. The schema shrink is the gain. The grammar engine is only the tool.
- Replace the live model with something built for classification. A 0.5B–1.7B model, or a distilled classifier trained on 8B labels, or even a linear model over a small Norwegian greeting set. Run the 8B offline to label examples. Do not leave it on the request.

Try `qwen3:1.7b` and `qwen3:0.6b`, and one non-thinking model in the same size (Llama 3.2 3B or Gemma 3 1B), on this machine, with thinking off. A 4B is worth one measurement and will probably still miss 0.7 s once Piper is added. Quality bar: the scorecard parses, and the scripted cases in `tests/test_graph.py` still pick the right emotion.

## 6. Synthesize during the decision, not after it

**Expected:** turns `model + Piper` into `max(model, Piper)`. Today that hides ~0.2–0.4 s and still leaves the 1.5 s model. It becomes the way a 0.4 s classifier disappears behind audio.

While the fallback model runs, start Piper on the likely template (the lexicon’s best guess, or the neutral “acceptable greeting” line). If the model agrees, the clip is already done. If it disagrees, drop the clip and synthesize the real line. Pair this with 4 so the teacher is not held for the sibling.

## 7. Piper without a process per line

**Expected:** about 50–150 ms per line on a cache miss, so up to ~0.3 s when both still go through Piper.

`audio-engine/server.py` writes a temp WAV, runs `ffmpeg` to resample to 22050 Hz, and the hub calls that twice over HTTP. Piper’s own `synthesize` yields PCM chunks. Set the voice to 22050 Hz or resample in-process, and generate both lines at once. Streaming those chunks lets the browser start after the first 100 ms of audio instead of after the full line.

Worth editing Piper’s call path. Not worth a new voice engine unless talesyntese cannot emit 22050 Hz directly. Kokoro or another fast voice is a later swap, and it changes the teacher’s voice.

## 8. A faster runtime for whatever model is still live

**Expected:** about 1.2–1.8× on decode if we stay on an 8B. 1.55 s becomes roughly 0.9–1.2 s of model time. **Not enough by itself.** Do this only if a large model remains on the hot path after 1 and 5.

Attempts, each measured with the same prompt:

- MLX on this Mac (`mlx-lm`). It is often faster than Ollama here because it is built for unified memory.
- llama.cpp’s Metal server, with flash attention and a q8 KV cache.
- Speculative decoding: a 0.5B draft model plus the 8B as the checker, inside llama.cpp. Expect up to about 2× on a short JSON, which is the same band as MLX.
- `Q4_0` instead of `Q4_K_M`, and context 512 instead of 2048. The prompt is ~150 tokens. Expect around 10–20% together, not a new class of speed.
- `OLLAMA_KEEP_ALIVE=-1` so the 3–4 s case (model reload) stops happening. This removes the slow tail. It does not touch the 2 s floor.

Editing Ollama or llama.cpp is justified for a measured kernel gap. It is not how this drill gets to 0.7 s.

## 9. Speech in, without spending the whole second on Whisper

**Expected:** the typed path does not include this. Speak records while the button is held and sends on release. A pause does not end the take. After release the cost is ffmpeg plus the recognizer.

Attempts:

- The browser silence gate is gone. Do not put it back. Recording ends when Speak is released.
- Start the scorecard on a partial transcript. Moonshine, distil-whisper, or whisper `tiny` are the open-source pieces that can do that. `base` is the wrong size for a one-second budget.
- Rebuild whisper.cpp with Metal for the M4. The image sets `GGML_NATIVE=OFF` because the aarch64 Docker build failed on fp16. A host-side Metal binary, or a build that enables fp16 cleanly, is an edit to that build, not a new product.

The fast lexicon still applies after the transcript. Recognition and the scorecard should overlap. They are sequential today (`turn_from_audio` transcribes, then calls `turn_from_text`).

## 10. Small work off the critical path

**Expected:** tens of milliseconds each. Do these while touching the turn, not as their own project.

- Write the SQLite turn after the socket send, not before the learner hears anything.
- Shorten the system prompt. Prefill of 145 tokens is a small slice of 1.55 s, and it is pure waste once the output is a short label.
- If llama.cpp stays, cache the system-prompt prefix. It is identical on every turn.

## 11. A filler sound

**Expected:** none toward the real target. A cached breath or “mm” can play at once and make the wait feel shorter. Do not treat it as hitting 0.7 s. The teacher’s actual line is the clock.

## Attempt order

The gains compound only in this order. Tuning the 8B first cannot reach the target.

1. Time one typed turn inside the hub: scorecard done, teacher PCM ready, sibling PCM ready, bytes sent. Confirm the split above on the day you start.
2. Lexicon in front of `complete()`, fall through on a miss.
3. Pre-rendered clips for those lines, served with no Piper call.
4. Send the teacher message first. Teach the page to play a partial turn.
5. Re-measure an unknown sentence. If it is still over 1 s, shrink the label and try a 1.7B or a distilled classifier. Synthesize during that call. Drop ffmpeg from Piper.
6. Speak path: the recording already ends on button release. A smaller streaming recognizer can still overlap with step 2.
7. MLX, speculative decoding, and 8B kernel flags only if a large model is still on the hot path and still over budget.

## Not a path to 0.7 s

- More GPU flags on this same 8B Q4 while it still writes ~66 tokens.
- A lower quant of that same 8B as the main plan. Worse Norwegian, about the same wait.
- Removing LangGraph. The four nodes are not the 1.5 s.
- Protobuf versus JSON, or moving the hub out of Docker. Localhost overhead is milliseconds.
- Swapping talesyntese for a rougher engine just to shave a synth we can cache.

## Done when

- Typed known greeting, warm stack: teacher audio starts at or under 0.7 s, and her animation still starts and ends with that audio.
- Typed unknown sentence: first audio at or under 1.0 s, or the miss is visible in the comparison log.
- Speak: from end of speech to first audio at or under 1.0 s.
- The comparison log records the backend that actually ran, including a rules hit, so a fast path cannot hide as a silent skip.
