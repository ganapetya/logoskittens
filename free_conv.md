# Execution

On approval, write this document unchanged to `free_conv.md` at the repo root. That file is the design of record for this replan. Then do the stages marked **Build now**, in order. Do not start stages marked **Later**.

The working tree already has uncommitted Norwegian fluency edits (`conversation.py`, `graph.py`, `llm.py`, `session.py`, `config/languages/nb.json`, tests, `AGENTS.md`, `work-plan.md`). This replan replaces that lesson. Do not merge those edits forward.

Reading of two phrases in the request, so they are not rebuilt wrong:

- "2-d buddy" and "3-d or N-d conversation partner" mean the second partner and the Nth partner. They do not mean a 2D graphic. The screen stays the virtual-stage adapter.
- Simulation trials go to `simulations/` inside this repository. The directory itself is tracked. Generated bulk inside a round (traces, copied config, call logs, sqlite, audio, binaries) is gitignored. Sibling folders of this checkout named `logoskittens-*` are the old trials and are removed.

# Free conversation

LogosKittens is local cognitive middleware. The hub emits semantic and affective directives. Pixels, CSS, servos, and ROS stay in adapters. The same `ElementSolution` (`cerm.execution.v1`) can drive the web buddy now and a hexapod spider later. The cognitive core does not learn that a body has legs.

The live product is one endless free-speech talk. A human and one buddy take turns. The subject of the talk comes from raw material, summarized once into a lesson subject. There is no drill, no correction of the human, and no end of conversation.

## What stays

- Five primitives: `Situation`, `Task`, `Actor`, `GroupSolution`, `ElementSolution`. Protobuf package `cerm.execution.v1` is unchanged, including `EMOTION_ENCOURAGEMENT` and `EMOTION_FRUSTRATION`.
- Hub boundary mirror in `primitives.py` stays field-compatible with that proto.
- Adapters only: `virtual-stage` maps an `ElementSolution` to SVG and audio. A later robotics bridge maps the same message to a hexapod. LangGraph does not mention either.
- Audio path: hold-to-talk (pointer down starts, pointer up or cancel stops, no silence gate). Web mode uses the browser microphone and plays PCM in the page. Botnet mode asks the ready robot to record and play. Host whisper.cpp and Piper in `audio-engine` stay on the host. PCM is signed 16-bit little-endian mono at 22050 Hz. WebSocket frames stay JSON (`session_id`, `transcript`, base64 `solutions`). The face is chosen when the human turn is accepted.
- One SQLite file via SQLModel, WAL mode, for the live conversation. The trainer uses a different file under the simulations tree.
- LLM client stays `httpx` inside `cognitive-hub`. Local default is Ollama `qwen3:8b` (`POST /api/chat`, `format: json`, `num_ctx` 2048, `LLM_THINK=off`). Remote is Grok `grok-4.7` at `https://api.x.ai/v1` when `LLM_BACKEND=grok` and `XAI_API_KEY` is set. Local is the default for the buddy and for the subject creator.
- Language is a parameter on the situation, the task, the prompts, the recognizer, the voice, and the raw material. The first live value is `en`.

## Participants

The human is a participant, not an actor the hub compiles. In a real talk the human is the person on the microphone. In training the human is a pseudo-human agent. The pseudo-human exists only in the trainer. The live graph never calls it.

The buddy is an actor. `buddy-one` is active. It is an LLM agent, local by default, remote when the hub backend is Grok. Its embodiment is `virtual_screen` on the web stage. The same actor id and the same `ElementSolution` are what a hexapod adapter will execute later. Switching body is an adapter and an embodiment medium (`physical_robot`), not a new brain.

`buddy-two` (and further buddies) stay in the actor model and are inactive. No graph node, no avatar, no microphone turn, and no injection. The later injection rule is already fixed so the slot is not a vague idea: after `buddy-one` has spoken, at most one extra `ElementSolution` for `buddy-two`, never on the first buddy turn, and no more often than once per many `buddy-one` turns. The rate stays unset until that stage is opened. A second physical robot is the same actor with `medium: physical_robot`.

Remove the teacher role and the sibling role. Remove actor files `actor_tutor_01` and `actor_sibling_01`. Remove correction personalities, agreement-by-gender, and the fluency / balanced / strict modes.

`buddy-one` has two English profiles in `config/buddies/en`. Peter is the default: man, energetic, capitalist, likes steak and a fight, voice `en_US-ryan-medium`. Mary is the other: woman, gentle, warm, and kind, Venetian, humanitarian, likes romance, music, and flowers, voice `en_US-lessac-medium`. She has no nature. Her alias is Masha. The name stays Mary. Gender stays `woman`, so the pronouns stay she and a Norsk click still matches Ingrid. Nature is not the match key. Peter, Lucas, and Ingrid leave it empty. The page lists both English profiles. Choosing one starts a new talk. Reset conversation starts a new talk and keeps the buddy already chosen. A question or a greeting is answered in one short sentence. A theme story is not added after that answer. Each turn also sends `language_specifics`: person `1st`, and the profile gender. Peter is a man and Mary is a woman. Both speak as I, me, and my. When nature is set, a question about what she is is answered from that line, and the theme is not replaced by it.

## Buddy out-brain

BOB is an internal role. It is not a second buddy and it does not speak. After every third buddy line, BOB reads the last lines and the buddy's character, and may store one short steer. The next local calls append that steer to the system prompt until the next third line. The starter files stay on disk. Settings live in `config/bob.json`, including `every_n`. The shipped backend is xAI (`grok-4.7`, `reasoning_effort` low) and uses `BOB_API_KEY` or, when that is empty, `XAI_API_KEY`. It does not read `LLM_BACKEND`. The steer is a nearby subject in that character. The same message may name one pose: agreement, disagreement, frustration, or curiosity. A question is curiosity. She plays that pose once, after the voice, on the reply that uses the steer. Later replies may keep the steer and do not repeat the pose. It does not force a listed like. The buddy answers what the human meant, then uses the last sentence of the steer. A word already in the theme does not count, and a reply that misses the new word is asked once more. A question steer is asked after the answer. In QA mode `altered by BOB` shows only when that new word was spoken, then `Suggested alteration:`. A steer still waiting shows `Next suggestion:`. QA also lists the subject card's important words under Send and Speak, labeled `Outside the theme`. QA is off unless `qa` or `BOB_QA` turns it on. The trainer may not edit `config/prompts/bob_en.md` or `config/bob.json`.

## Conversation types

Free speech is the only live conversation. Shut down greetings, life in Norway, and life in the user's country: topic files, dossiers, greeting graphs, anchor walks, preempt rules, canned moves, and the lesson-panel mode switch.

Do not add a new concrete type in this pass. A later type, if it is needed, is a policy on top of this free-speech loop, written only after the free-speech prompts are good.

## Language

Every prompt, raw-material set, voice, and recognizer weight is selected by the language id. English prompt files end in `_en`. Norwegian Bokmål is language id `nb`. Its prompt files end in `_nb` and do not reuse the English prompt text. The graph loads `prompt-of-subject-creation_{language}` and `ongoing_instruction_prompt_{language}`. Python does not branch on English wording. Pronoun text and `first_person_rewrite` live in the language file. A missing template keeps the English pronoun block.

The live packs are `en` and `nb`. Start reloads `config/languages`, starts a new empty talk in the language chosen in the Talk panel, and switches the recognizer. A language file added after the hub is up appears on the next catalog or select. The page lists the display names. Buddies for `nb` are Lucas (man, default) and Ingrid (woman). Both use Piper `no_NO-talesyntese-medium`. `no_NO-nvcc-medium` stays in the image and is not selected. An id from another language matches by gender, then by the buddy marked default.

Recognizer for `en` uses `-l en`. The weight is `RECOGNITION_MODEL` in `.env_recognition`. The default is `small.en`. Recognizer for `nb` uses `-l no` and NbAiLab `nb-whisper-large`. `POST /switch` re-reads the language files before it accepts the id.

## Raw material

Raw material is the set of sentences the talk is about. Two sources share one interface:

```text
RawMaterialSource.load(language, material_id) -> RawMaterial
RawMaterial: id, language, title, text, origin
origin: "file" | "logoscat"
```

File source reads `config/raw_materials/{language}/{id}.txt`. The hub works with this source alone.

LogosCat uses that same load after a workspace session has been downloaded. The page logs in through the hub. `MODE=dev` calls `http://localhost:8080` (the hub container uses `host.docker.internal`). `MODE=prod` calls `https://logoscat.com`. The browser keeps the token. Workspace sessions lists the account's sessions. Choosing one downloads `text_input` sentences only, stores them in the hub database as `logoscat-{id}`, and selects that row in the Talk panel. Start begins the talk. English stays `en`. `no`, `nb`, and `nob` become `nb`. One live language switches the talk to it. A mix keeps the lines that match the talk already open. Any other language, or a session with no source sentences, does not start a subject. The session name stays in the raw-material list, logged in or not, until it is deleted. File materials still load when nobody is logged in and when LogosCat is down. `attached` stays unwired. The live mode remains `detached`.

The first test material is `en` / `norway_vacation_tunnels_fjords`:

```text
Last summer we took a vacation along the west coast of Norway. The road went through long tunnels cut into the mountains, and the light at the far end always felt like a surprise. Between the tunnels the fjords opened up, steep and quiet, with water that looked almost black in the shade and bright where the sun hit it. We stopped above a fjord and watched the ferries cross. Someone on the trip said the tunnels make that beauty easier to reach: you drive through the dark and come out above the water. I still think about the cold air and how green the slopes were, right down to the fjord.
```

Further predefined files follow the same shape (a travel story, a greeting scene). The same id in both packs is `friendly_chat`: title `Friendly chat` in English and `Vennlig prat` in Norwegian Bokmål. Those sentences are a friendly talk with a little affection. The same shape is `cozy_breakfast`: title `Cozy Breakfast` in English and `Koselig frokost` in Norwegian Bokmål, a quiet Italian-style breakfast with a warm cornetto, berries, and espresso. The Norwegian text is its own text. The default material id stays `norway_vacation_tunnels_fjords`. Tests use that file.

## Summarize node

When a conversation starts, the summarize node runs once. Its engine is LLM-subject-creator: one `httpx` call, the hub's configured backend, local by default. Input is the raw material text and `prompt-of-subject-creation_{language}`. Output is the lesson subject input. A new raw material starts a new conversation and runs the node again. Turns do not run it again.

Lesson subject input:

| Field | Meaning |
| :--- | :--- |
| `used_words` | Content words and short phrases that occur in the raw material. No articles, auxiliaries, or bare pronouns. Deduplicated. Surface form from the text. |
| `significant_words` | Subset of `used_words`. The few concrete words a talk should keep touching. |
| `important_words` | About 6 to 12 words or short phrases from the raw sentences that the theme would otherwise drop. Not the same list as `significant_words`. The buddy may use one of them on some replies. A missing list on an older session is empty. |
| `theme` | One sentence, no fact that is absent from the raw material. |
| `small_talk_subjects` | Four to seven short openings the buddy can start. Each one is speakable and grounded in the theme. |

File `config/prompts/prompt-of-subject-creation_en.md`, starter text (the trainer may replace it later only through approve):

```text
You read raw material: sentences a person has already read. You prepare a subject card for an open conversation. You do not write a lesson, a quiz, or a story.

Use only facts that are in the raw material. Do not add places, events, or reasons that the text does not contain.

Return one JSON object with these keys:
- used_words: array of content words and short phrases that actually occur in the text. Drop articles, auxiliaries, and bare pronouns. Deduplicate. Keep the spelling used in the text.
- significant_words: array, a subset of used_words. Choose the few concrete words a conversation should return to (places, things, experiences). Leave out glue words.
- important_words: array of about 6 to 12 content words or short phrases that occur in the text and are worth hearing aloud, especially ones you did not put in significant_words. These are practice words the summary must not drop. Leave out glue words and anything already listed in significant_words. Keep the spelling used in the text.
- theme: one sentence naming what the material is about. No new facts.
- small_talk_subjects: array of 4 to 7 short openings. Each opening is one question or prompt a friend could say. Ground every opening in the theme and the significant words.

Write the card in English.
```

## Ongoing conversation

`OngoingConversation` is the whole live state. `ongoing_conversation_data` is the same object. It holds:

1. The lesson subject input.
2. The last 8 sentences spoken by the human or the buddy, oldest first, each with a speaker label `human` or `buddy`. A sentence is a span ending in `.`, `!`, or `?`. A turn can contribute more than one. The list is trimmed to 8 after every turn.
3. `ongoing_instruction_prompt`, loaded from `config/prompts/ongoing_instruction_prompt_{language}.md`.

The buddy call receives that object and nothing older. The judge of a simulation sees the full transcript. The buddy does not.

## Starting a session

Nothing starts a talk except Start. The Talk panel is a draft: language, Web or Botnet mode, QA, buddy, raw material, game, and, for free speech, teacher mode. A click in the panel changes only the draft. It sends nothing to the hub except read-only catalog reads for the chosen language and the player-list poll. Start is enabled when language, buddy, raw material, and game are chosen (Free speech counts as a game). Start applies the mode with `POST /host-mode` when it differs from the hub, then sends one `select` with every field, including `qa` and `teacher_mode`. That one `select` switches the recognizer and runs the summarize node or the game prepare once.

While a talk runs, the panel can change. The running talk keeps its settings, and the panel says so, until Start is pressed again, which starts a new session. Reset conversation starts a new session with the running talk's settings and ignores an unapplied draft.

The draft is kept in the browser (`logoskittens.setup`) and prefilled after a refresh. A refresh sends nothing. It does not resume the previous session, which stays in SQLite. The hub never creates a session by itself: `transcript`, `audio`, and `resume` without an existing session return `No conversation is running. Choose the settings and press Start.` QA is stored per session on the hub, not shared across tabs. The CLI's explicit `start` message stays.

A workspace session chosen from LogosCat is imported as a raw material and selected in the draft. It does not start a talk. Its row stays in the raw-material list of its language, logged in or not, until its delete button removes it from the database (`DELETE /logoscat/materials/{id}`). Importing the same workspace session again updates that row. The material of the running talk cannot be deleted while it runs.

SQLite stores the raw material id, the language, the lesson subject input, and the full sentence log. The last-8 window is derived from the log. A page reload does not resume it (see Starting a session). Start with another raw material or another language starts a new session and runs the summarize node again. The previous session stays in SQLite.

File `config/prompts/ongoing_instruction_prompt_en.md`, starter text:

```text
You are the buddy in an open conversation. The talk has no lesson and no ending.

When a personality block is present, you are that person. Answer questions about your name, gender, mood, tastes, and beliefs from that block. Do not deny a trait it sets.

When a language_specifics block is present, follow it. It sets the person and the gender of the words you use about yourself. Speak as I. Do not talk about yourself by name.

You receive a subject card (theme, used words, significant words, small-talk openings) and the last sentences spoken by you and the human.

Stay inside the theme when the human is talking about it. Use the significant words when they fit the moment. Draw on the used words. Do not list the card, do not quiz, and do not say that you are teaching.

When the message names one word from the reading, you may use it in the detail you are already adding, if it fits. Leave it out when it does not. Do not use it on every line, and do not let it replace what the human said.

If the human asked a question or said hello, answer that in one short sentence and stop. Do not add a story, a second sentence, or a detail from the theme. If they did not ask a question, answer the meaning of their latest sentence and add one concrete detail of your own from the theme. If that sentence leaves the theme, acknowledge what they said, then add one detail from the theme. Do not replace their sentence with a question from the card.

When the latest human sentence is only agreement, a fragment, or a passive line such as "yes", "ok", or "mhm", do not stall and do not repeat them. Choose one small-talk opening that has not been used yet and start it with a specific question.

Do not correct grammar, pronunciation, word choice, or facts. Do not repeat their sentence. Do not recap the whole talk. Do not say goodbye and do not close the conversation.

Speak the way a person answers, in English. One short sentence when they asked something. One or two short sentences otherwise.

Return one JSON object:
{"line": "<what you say aloud>", "emotion": "neutral" | "curiosity" | "amusement" | "encouragement"}
```

Emotion maps onto `EmotionType`. Gestures stay empty. The screen cue is a single talk animation. Those fields are for the adapter, including a future hexapod, and are not a second conversation policy.

## Turn loop

The live order is human, buddy, human, buddy, with no terminal state.

1. The page loads a language and a raw-material id. The hub runs the summarize node and sends the theme to the page.
2. The human holds the mic button, as today. Typed text still skips recognition.
3. The transcript is appended to the sentence log. Speech errors are stored as heard and are not repaired, scored, or taught.
4. The buddy node produces the spoken line. It reads `OngoingConversation` and returns `line` and `emotion`. BOB may run after every third buddy line. It does not sit on this call.
5. The hub compiles one `ElementSolution` for `buddy-one` and sends it. Piper speaks `line`. The virtual stage plays audio and the visual cue.
6. The buddy line is appended, the window is trimmed to 8, and the graph returns to wait for the human.
7. Rob may judge the human sentences he has not seen yet, once the gap in `group.md` is reached. A correction is a later `ElementSolution` for `teacher-one`. The buddy line already sent is not held for that call. The human line stays as heard.

`GroupSolution.protocol` is `free_speech`. `turn_order` contains `buddy-one` only. The human is ingress.

The buddy graph has no assess node, no grammar scorecard, no `form_ok`, and no retry-because-echo node. Echo and drift on the buddy line are prompt problems for the trainer. Savelij is not a node in that graph. He speaks only the sentence Rob returns. `group.md` is that design. A code change in the compiler waits for a person.

## Trainer

Keep the improver shape: one proposal, then wait. `.env_training` chooses the model for the simulated talk (`BACKEND_SIM_TALK`) and the model for the judge and the proposer (`BACKEND_JUDGE_PROPOSER`). Each is `local` or `grok`. The example file speaks with local `qwen3:8b` and judges with Grok `grok-4.7`. `approve` replays on the simulated-talk model and asks for the next proposal. `reject` records the refusal and does not write a proposal. Commands stay `python -m logoskittens.sim improve run|approve|reject`. Practice keeps using `.env`.

What changes:

- The thing under test is free speech: summarize node plus buddy turns.
- The proposal may change only `config/prompts/prompt-of-subject-creation_en.md` or `config/prompts/ongoing_instruction_prompt_en.md`, one of them per proposal. Window size, graph code, the pseudo-human, and the raw material are not proposal targets. A code edit is out of band and waits for a person.
- The simulated talk and the judge each use the role in `.env_training`. Call logging stays as it is now (stderr plus `calls.log`, no API key).
- The pseudo-human is a fixed agent used to author scripts. Scoring replays frozen human lines so two prompts face the same human. A separate `sim talk` command runs pseudo-human and buddy live and is not the accept gate.
- Trials are written under `simulations/<round-id>/` in this repository, never as sibling folders of the `logoskittens` checkout.

Frozen scripts, all on `norway_vacation_tunnels_fjords`:

- `passive_en`: `yes` / `okay` / `mhm` / `nice` / `sure` / `I guess`
- `curious_en`: `We drove through so many tunnels.` / `Why are the tunnels so long?` / `The fjords looked almost black.` / `Did you see a ferry?` / `I liked the green slopes.` / `Would you go back?`
- `wanderer_en`: `I mostly remember my kitchen at home, the kettle and the noisy fridge, and I forgot the trip.` / `yeah` / `the fridge again` / `okay the water then` / `sure` / `mhm`

Six human lines, then stop. The live product does not stop; the cap is only the measurement.

### Goodness

Scores are integers 1–5.

| Score | 5 means |
| :--- | :--- |
| `subject_fidelity` | The buddy stays on the theme and uses significant words as part of the talk. |
| `responsiveness` | Each buddy turn answers the latest human meaning and does not recite it. |
| `initiative` | After a passive human line the buddy opens a specific unused small-talk subject. A talk of only "yes" lines cannot score 4 or 5 if the buddy stalls. |
| `naturalness` | One or two spoken sentences, in the session language, with no quiz, no teaching frame, and no goodbye. |
| `subject_card` | `used_words` occur in the raw material, `significant_words` are a concrete subset, `important_words` occur in the raw material and are not the theme anchors, `theme` adds no facts, and every small-talk opening is grounded. |

Flags, and a true value fails the trial even if scores rise: `corrected_human`, `recited_human`, `ended_conversation`. `language_match` must stay true.

`compare` accepts only when at least one score rose, none fell, and no fail-flag is set. Critiques quote a spoken line or a lesson-subject field.

The old scores (`flow`, `education`, `progress`, CEFR, correction usefulness) belong to the retired lesson and are deleted with it.

## Simulation files

Trials stay in this repository, under `simulations/`. The directory is not ignored.

`.gitignore` ignores generated bulk inside a round, and leaves the decision records:

```gitignore
simulations/**/traces/
simulations/**/config/
simulations/**/baseline/
simulations/**/calls.log
simulations/**/*.pcm
```

`*.db`, `*.wav`, `*.bin`, and `*.onnx` are already ignored for the whole repo. A decision record is the proposal id, the prompt file name, the full proposed prompt text, the hypothesis, the score table, and the approve or reject outcome. Full transcripts, round checkouts, SQLite, and call logs stay untracked.

Accepted prompt text is copied back into `config/prompts/` by `approve`, which is the copy the next session runs.

Remove old simulations:

- directories `../logoskittens-shy-a2-fragment`, `../logoskittens-nb-line-norsk`, `../logoskittens-reorder-echo` (git worktrees; use `git worktree remove`, then delete any leftover)
- `data/sim/` inside logoskittens
- `config/sim/` scenarios, scripts, matrix, and agent prompts of the teacher/sibling lab

## What to remove because it hides this goal

- Topics and dossiers other than the new free-speech path. Free speech is rebuilt; the old free-conversation dossier is not kept.
- Teacher, sibling, anchors, preempts, intervention modes, greeting canned lines, `without_learner_echo`, `TurnAssessment` grammar fields on the live path, and the phrase-stack `prompt_template`.
- Lesson-panel controls for those topics and modes.
- Norwegian lesson content from the catalog.
- Old sim rubric, matrix, and traces.
- Active status of `flow.md`, `impl-conversation-oct-16.md`, and `conversational_architecture.md`. Leave the files, with a one-line banner that `free_conv.md` replaces them. Do not follow them.

Update in the same pass, so the next session does not rebuild the drill:

- `AGENTS.md` read order: `free_conv.md`, then `logoskittens_architecture.md`, then `work-plan.md`. Record the prompt file names, the buddy voice, the sim root, and English as the first language parameter.
- `logoskittens_architecture.md` §3, §5, and §12: buddy-one on screen or hexapod, human as participant, free speech in the selected language, second actor inactive, LogosCat as a future raw-material source. Keep §2, §6, and §8.
- `work-plan.md`: replace the open work with the stages below. Stages 10 and 11 as previously written (cloud curricula, ROS bridge) are restated as the later stages here, still not started.

## Stages

### Build now

1. Write `free_conv.md`. Point `AGENTS.md`, the architecture MVP sections, and `work-plan.md` at it. Banner the retired conversation docs.
2. Add the data types: `RawMaterial`, `LessonSubjectInput`, `OngoingConversation`, language parameter, `buddy-one` active, `buddy-two` stored and inactive. File source and the vacation text. Both `_en` prompts as written above. A LogosCat workspace session is downloaded later, in item 12, and then loaded on the same path.
3. Delete the shut-down lesson paths and their tests. Catalog offers `en` and the vacation raw material. One graph: summarize once, then buddy turn, no end, no correction.
4. Persist the ongoing conversation. WebSocket and hold-to-talk stay. One `ElementSolution` per buddy turn.
5. Virtual stage: one buddy, raw-material choice, theme line, mic button unchanged. No topic list and no correction mode. Verify in the browser at desktop width and a narrow viewport: choose material, see the theme, hold to talk or type, hear one buddy reply, continue a second turn, reload and see the same log.
6. Point the trainer at `simulations/` in this repo. New rubric, three frozen scripts, proposals limited to the two `_en` prompt files, approve/reject, fake-LLM tests. Remove the old worktrees, `data/sim`, and `config/sim` lesson lab. Ignore generated bulk under `simulations/`, and keep the decision records.

Exit of this pass: `pytest` green; a fake-LLM test covers summarize, the 8-sentence window, a passive turn that still returns a line, and a proposal that is refused if it targets any other file; the user can run `improve run`, `approve`, and `reject`; the web buddy can hold a real talk. Prompts are the starters above until the user accepts a proposal.

### Later, in this order, not in this pass

7. The user runs the trainer and accepts or rejects proposals until the two prompts are good.
8. The user holds real conversations with the web buddy.
9. Embodiment `physical_robot` for `buddy-one`: a hexapod adapter consumes the same `ElementSolution`. LogosKittens stays the local server. The hub graph is not rewritten.
10. Activate `buddy-two` on the web stage. The rare-injection rule above is the only new policy.
11. The same `buddy-two` on a second physical robot. Demo.
12. LogosCat client: a personal app-token connection (no password), workspace sessions, and one session's source sentences as raw material. File materials still load when LogosCat is down.
13. Polish. Norwegian Bokmål (`nb`) was opened early. The pack is live: `_nb` prompts, the vacation text, Lucas, Ingrid, and the recognizer. No English sentence is reused as Norwegian copy. Items 7–11 stay closed. Item 9 is open.

## Coverage

| # | Request | Where it is handled |
| :--- | :--- | :--- |
| 1 | Only free speech, rebuilt; other types later and only from a good free-speech base | Conversation types; Later stage 13 is language, not a new type; concrete types wait |
| 2 | Human (real or pseudo-human) and buddy; local LLM default | Participants; Trainer |
| 3 | LogosCat lessons are raw material | Raw material; an app-token connection and a workspace-session import |
| 4 | Raw material into the summarize node; LLM-subject-creator | Summarize node |
| 5 | Lesson subject fields and `prompt-of-subject-creation` | Summarize node, starter prompt |
| 6 | Lesson subject is part of the ongoing conversation | Ongoing conversation |
| 7 | Last 8 sentences plus a real instruction prompt | Ongoing conversation, starter prompt |
| 8 | Human, buddy, no end; mic button as now; talk uses the subject | Turn loop |
| 9 | Predefined raw material and a future LogosCat download | Raw material; vacation text is the test file |
| 10 | Simulation or a real talk | Turn loop and Trainer |
| 11 | Keep the judge and the trainer | Trainer |
| 12 | Optimize the two prompts; goodness criteria | Trainer, Goodness |
| 13 | Ignore human speech errors | Turn loop; fail-flag `corrected_human` |
| 14 | English first; language is a parameter | Language |
| 15 | Not in the request | Nothing invented for a missing item |
| 16 | Vacation in Norway, tunnels and fjords | Raw material, full text |
| 17 | Same directives can drive a robot; hexapod is the next body | What stays; Later stage 9 |
| 18 | Nth partner exists and stays inactive | Participants, `buddy-two` |
| 19 | Remove what hides the goal | What to remove |
| 20 | After the build, the user runs accept/reject | Later stage 7; Build now makes the commands work |
| 21 | Then real web talks | Later stage 8 |
| 22 | Then one hexapod, hub as local server | Later stage 9 |
| 23 | Then second buddy on the web, rare injection | Later stage 10 |
| 24 | Then second physical buddy | Later stage 11 |
| 25 | Then LogosCat raw data | Later stage 12 |
| 26 | Norwegian Bokmål `_nb` is a live pack. Items 7–12 stay later | Language; work-plan item 13 |
| 27 | Sims under `simulations/` in this repo; gitignore generated bulk; delete old sims | Simulation files |
