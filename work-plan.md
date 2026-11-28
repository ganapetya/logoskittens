# LogosKittens work plan

Build the free-speech loop in `free_conv.md`, one stage at a time.

- Start a stage only after every stage it depends on has met its exit criteria.
- Update the checkboxes in the same change as the work. Check a stage complete only when every exit criterion is true.
- Design detail stays in `free_conv.md`. Architecture §2, §6, and §8 stay as written. This file owns order, tasks, and exit criteria.
- The proto contracts, the audio engine, SQLite, the `httpx` client, and Compose are already in the tree. Do not rebuild them.
- Items 7, 8, and 10–12 stay closed. Item 9 is open. Its steps are `masha-02-work-plan.md`. Do not mark item 9 done until step 6 of that file.

## Stage 1 — Point the docs at free speech

Depends on: `free_conv.md`.

Goal: the next session follows `free_conv.md` and does not rebuild the greeting lesson.

- [x] `free_conv.md` is the design of record at the repo root.
- [x] `AGENTS.md` read order starts with `free_conv.md` and records the prompt names, the buddy voice, the sim root, and English as the first language parameter.
- [x] Architecture §3, §5, and §12 describe `buddy-one`, an inactive `buddy-two`, and free speech. §2, §6, and §8 are unchanged.
- [x] `flow.md`, `impl-conversation-oct-16.md`, and `conversational_architecture.md` carry a retired banner.

Exit criteria:

- [x] A reader who starts at `AGENTS.md` reaches `free_conv.md` before any retired conversation doc.

## Stage 2 — Free-speech data

Depends on: Stage 1.

Goal: raw material, a lesson subject, an ongoing conversation, and the two English prompts exist as data the graph can load.

- [x] `RawMaterial`, `LessonSubjectInput`, and `OngoingConversation` are in the hub.
- [x] Language is a parameter. Prompt files end in `_en`.
- [x] `buddy-one` is active. `buddy-two` is stored and inactive.
- [x] File source reads `config/raw_materials/en/norway_vacation_tunnels_fjords.txt`.
- [x] The live loop reads those files. A downloaded LogosCat session is item 12.

Exit criteria:

- [x] A test loads the vacation text and a second language id through the same parameter.
- [x] File materials still load when LogosCat is down. The download checks are item 12.

## Stage 3 — One graph

Depends on: Stage 2.

Goal: summarize once, then buddy turns, with no end and no correction.

- [x] Greeting, topic, dossier, teacher, and sibling paths and their tests are gone.
- [x] The catalog offers `en` and the vacation raw material.
- [x] Prepare graph runs the summarize node once. Turn graph is `speak` then `compile` for `buddy-one` only.

Exit criteria:

- [x] A fake-LLM test covers summarize, the 8-sentence window, and a passive human line that still returns one `ElementSolution`.

## Stage 4 — Persist the talk

Depends on: Stage 3.

Goal: the ongoing conversation survives in SQLite and on the existing socket.

- [x] The session stores the raw material id, the lesson subject, and the full sentence log. The last-8 window is derived.
- [x] WebSocket `start`, `resume`, and `select` stay. One `ElementSolution` per buddy turn.
- [x] A page reload resumes the session. Changing language or raw material starts a new session and runs summarize again. Superseded: a reload now starts nothing until Start (`free_conv.md`, Starting a session).

Exit criteria:

- [x] An API test completes two turns on one material and reads the sentences back from the session.

## Stage 5 — Virtual stage

Depends on: Stage 4.

Goal: one buddy, a raw-material choice, the theme, and the existing hold-to-talk button.

- [x] The page shows one buddy. There is no topic list, no correction mode, and no gender picker.
- [x] Verified in the browser at desktop width and at a narrow viewport: choose the vacation material, see the theme, type a line, see one buddy reply, continue a second turn, reload and see the same log. The check used a local hub with a stand-in model and stand-in audio. Piper playback and the microphone are still the live path when Compose and the recognizer are up.

Exit criteria:

- [x] That browser check passed.

## Stage 6 — Trainer

Depends on: Stage 3. Can land beside Stage 5.

Goal: the improver optimizes the two `_en` prompts, and old simulations are gone.

- [x] Rubric, three frozen scripts, and proposals limited to the two prompt files. `approve` and `reject` behave as `free_conv.md` says.
- [x] Fake-LLM tests cover a waiting proposal, a refused path, approve copying a prompt only when a score rises, and reject with no model call.
- [x] Trials live in `simulations/` in this repo. `.gitignore` keeps the directory and its decision records. It ignores traces, round config copies, call logs, sqlite, audio, and binaries inside those subdirectories.
- [x] Old worktrees `logoskittens-shy-a2-fragment`, `logoskittens-nb-line-norsk`, and `logoskittens-reorder-echo` are removed. `data/sim` inside this repo is gone.

Exit criteria:

- [x] `pytest` is green, including the proposal-path refusal.
- [x] `python -m logoskittens.sim improve run`, `approve`, and `reject` are the commands. `improve status` resolves `simulations/` inside this repo and does not call a model.
- [x] The user can run those commands. Prompts stay the starters until the user accepts a proposal.

## Later, in this order

Talking games are specified in `games.md`. That work is not one of the items below. It does not close item 9 and does not reorder items 7, 8, or 10–14.

7. The user runs the trainer and accepts or rejects proposals until the two prompts are good. Not started.
8. The user holds real conversations with the web buddy. Not started.
9. Embodiment `physical_robot` for `buddy-one`. Open. Masha is the body. The hub graph is not rewritten. Steps and exit checks are in `masha-02-work-plan.md`. Do not mark this item done until step 6 of that file. `buddy-two` stays inactive.
10. Activate `buddy-two` on the web stage. The rare-injection rule in `free_conv.md` is the only new policy. Not started.
11. The same `buddy-two` on a second physical robot. Demo. Not started.
12. LogosCat client: a personal app-token connection (no password), workspace sessions, and one session's source sentences as raw material. File materials still load when LogosCat is down.
- [x] `MODE=dev` uses `http://localhost:8080` on the host and `http://host.docker.internal:8080` in the hub container. `MODE=prod` uses `https://logoscat.com`.
- [x] The page logs in, logs out, and lists workspace sessions through the hub. The token stays in the browser.
- [x] Choosing a session stores the source sentences and starts a new subject. The session name is a raw-material row.
- [x] pytest covers the proxy, the source-line filter, an empty session, a language we do not speak, and the file materials.
13. Polish. Norwegian Bokmål is language id `nb` (opened early). Prompts, the vacation text, Lucas, Ingrid, and the recognizer are live. Items 7, 8, and 10–11 stay unstarted. Item 9 is open. Item 12 is the LogosCat app-token connection. Item 14 is Teacher mode. No English sentence is copied into Norwegian.
14. Teacher mode. Relaxed is the loop that speaks one correction at once. Pedantic judges every human sentence after two human responses, stores the explanation and its voice, and plays that voice only from Hear.
- [x] The Talk panel lists Relaxed and Pedantic. The choice is stored on the session. A new talk keeps it. Relaxed is the default.
- [x] Pedantic does not speak on its own. A corrected sentence gets a Correction button. The popup shows the explanation. Hear plays the stored PCM in the browser.
- [x] pytest covers the relaxed clock, the two-response clock, a note per corrected sentence, a sentence with no note, a bad reply, and a mode switch that does not rewind the cursor.

15. Google speech option. Google Cloud TTS and STT beside Piper and whisper, two independent switches on a Settings page (`#/settings`), for `en`, `nb`, `uk`, `de`, and `he`. The credential (API key or service-account JSON) and the voice choices are rows in the hub SQLite file. Nothing calls LogosCat.
- [x] The hub `SpeechRouter` (`cognitive-hub/src/logoskittens/speech/`) has the `AudioClient` interface. While Google voice is on, a buddy speaks with the Google voice of their gender and Savelij with the teacher voice. A Google voice failure speaks that line with Piper. A Google recognition failure asks to speak again.
- [x] The Settings page saves, tests, and removes the credential, never shows it again, plays a sample of each voice, and mirrors for a right-to-left source.
- [x] pytest covers the PCM format, WAV, WebM, and mp4 routing, the Piper fallback, the hidden credential, voices by gender, the teacher's voice, the Hebrew locale fallback, and Start without the whisper switch.
- [ ] With a real key: each language's three voices played by ear, and recognition of one recording per language. Confirm whether Google accepts `iw-IL` or `he-IL` for Hebrew recognition.
- [ ] Median of 10 turns per language, Google against local, in a table here: Google first audio within +300 ms of Piper, Google recognition median at most 1.5 s for a 3 s utterance, no turn past the 6 s voice and 8 s recognition ceilings.

Out of scope while item 9 is open: a second live buddy, and marking item 9 done before its last step.
