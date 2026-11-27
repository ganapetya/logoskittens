> Retired. `free_conv.md` replaces this document. Do not follow it.

# Conversation plan — 16 Oct 2026

Build open conversation on the greeting loop that already runs. A user, a language, and a topic are stored in the same SQLite file. The pair **language + topic**, for that user, is the configuration that drives the model, each partner's voice, the recognizer, the prompts, and the page.

`conversational_architecture.md` is the dialogue proposal. This file is the order in which it is built, and the speed limits it has to live inside.

## What is already true

Measured on this Mac (M4 Pro, `qwen3:8b`, thinking off, context 2048), from `faster.md`:

| Slice | Warm |
| --- | --- |
| Whole greeting turn | 2.0 s |
| The model call | 1.55 s, about 42 tokens/s, GPU already full |
| Piper after the model | about 0.45 s if both voices are waited for |

A full 8B reply of ~66 tokens cannot start audio in 300 ms. The proposal's fast loop (≤ 300 ms) is reachable only when the line is already known and no model call runs. An open sentence still costs about one model call before the first voice.

Today `session.py` already does three useful things: the teacher model call finishes before the sibling call starts, her voice and his call overlap, and SQLite does not sit in front of either voice. Speech recognition finishes before any model call. Those rules stay.

The wire message stays `ElementSolution` (`proto/cerm/execution/v1/element_solution.proto`). Pixel mapping stays in `virtual-stage`. LLM calls stay in `cognitive-hub/src/logoskittens/llm.py`.

## The configuration reality

Three axes, one row that wins:

**User × language × topic.**

Language A + topic B for user U is a different saved setup from language B + topic C for the same user, and from the same pair for another user. "Life in Norway" in Norwegian may use a small context, a Norwegian voice, and balanced correction. The same topic in another language may name another model, another voice, and fluency mode. Nothing in code special-cases those combinations. The row does.

Resolution, first hit wins:

1. The row for this user + this language + this topic.
2. The shared template for this language + this topic (no user).
3. The shared template for this topic.
4. The built-in default in code, which matches today's greeting behavior.

Opening Configure and saving writes row 1. Until then the user rides the template, so the three topics work before anyone touches a setting.

**Language** here is the language being practiced. It is not a translation of the whole page chrome. It is the switch that selects the recognizer, each partner's voice, and the prompt set. Labels that belong to the lesson (title, placeholder, partner names) come from the pair for that language.

Changing language loads that language's stack before the next turn. Norwegian and English are both real stacks in the first test, not a label on one shared voice.

| | Norwegian `nb` | English `en` |
| --- | --- | --- |
| Recognizer weight | NbAiLab `nb-whisper-medium` | whisper.cpp `ggml-base.en` |
| Recognizer language | `no` | `en` |
| Male Piper voice | `no_NO-talesyntese-medium` | `en_US-ryan-medium` |
| Female Piper voice | `no_NO-talesyntese-medium` | `en_US-lessac-medium` |
| Chat model seed | `qwen3:8b` | `qwen3:8b` |
| Prompts and dossier | Norwegian | English |

The chat model id is stored on the pair, so a language is allowed to name a different one. Both seeds use `qwen3:8b` on purpose. A second 8B on the same GPU is the overload this plan is avoiding. The recognizer weight changes with the language. `nb-whisper-medium` is a Norwegian model, so English uses `ggml-base.en`.

Piper's published Norwegian catalog contains one voice, `no_NO-talesyntese-medium`. Male and female Norwegian partners both use that file. English has a male voice and a female voice, so a gender change there changes the sound. The audio image stores `no_NO-talesyntese-medium`, `en_US-ryan-medium`, and `en_US-lessac-medium`, and loads the one the speaking partner's config names.

The host recognizer is one process. On a language change it is restarted onto the other weight and stopped on the previous one. Both weights may sit on disk. They are not loaded together. The restart happens once when the language is selected, before the next Speak, not in the middle of a sentence. The model call uses the pair's chat-model id and that language's prompt.

## Teacher and student

The student is the sibling partner already in `actor_sibling_01.json`. The teacher is `actor_tutor_01.json`. Each partner has a config. A pair stores both, so Norwegian and English, and one user and another, can differ.

Gender is a personality trait beside `patience`, `expressiveness`, and `assertiveness`. It can be changed. The seed is teacher `male` and student `female` in both languages. The left panel offers male or female for each partner. Saving writes that trait on this user + language + topic.

The voice follows the trait. The map is language × gender:

| | male | female |
| --- | --- | --- |
| `nb` | `no_NO-talesyntese-medium` | `no_NO-talesyntese-medium` |
| `en` | `en_US-ryan-medium` | `en_US-lessac-medium` |

Each partner config holds the resolved voice id. Changing gender on the form sets the voice id from this map for the language that is selected. A later edit may name another voice id. The next spoken line uses the saved id. Piper does not reload a Whisper weight for this. Only the voice file changes, and in Norwegian the file stays `talesyntese`.

How they speak follows the same trait. The prompt for that partner includes gender together with the other traits. In Norwegian, words the speaker uses about themselves take the matching form (`liten` / `lita`, `sulten` / `sulta`, and the same class of agreement). In English the grammar does not change with the speaker. The prompt still says the partner is a man or a woman, so the wording fits that person, and it does not invent endings. Switching gender updates the prompt on the next turn. It does not add a model call.

**Topic** is the subject. It is also the door for every setting that is allowed to change. A topic does not have its own hidden code path.

Seeded topics:

| Id | Title | Role |
| --- | --- | --- |
| `greetings` | Greetings | The drill that already ships. Kept so the current tests and the fast greeting path still have a door. |
| `free_conversation` | Free conversation | Thin dossier. Fluency. One partner answers. |
| `life_in_norway` | Talk about life in Norway | Fixed dossier with a few anchors. Balanced correction. |
| `life_in_user_country` | Talk about life in user country | Same shape as Norway. The user's country is filled into the dossier from the user row. |

The left panel shows all four. The three conversation titles are the ones asked for. Greetings stays first so the working lesson is not removed to make room.

## Speed rules

These override the proposal where they disagree.

1. **One model call produces the line that is spoken.** The grammar check is not a second call placed in front of it. Rules handle the cheap cases (empty utterance, a target word missing a marker we can see, a direct "what does this word mean" question). Anything that needs judgment rides inside the same scorecard the speaker call already returns. Strict mode uses that scorecard. It does not add an evaluator model call.
2. **One partner speaks per human turn.** The floor alternates teacher, then sibling, then teacher. The teacher takes the floor early when the rules or the scorecard say the intervention mode requires it. She does not then hand the same turn to the sibling. A same-turn handoff is a setting, default off, because it is a second model call and another Piper clip before the turn feels finished.
3. **Speech recognition and the model do not overlap.** The recording is transcribed, then the model runs. A background guess is cancelled as soon as audio arrives, and as soon as the foreground call needs the model.
4. **The speculative buffer is off unless this pair turns it on.** When it is on, at most one guess runs, and only while the GPU is idle: after the current reply has been sent, before the human speaks. It guesses the single next line of the partner who is likely next. It does not precompute agreement and disagreement, and it does not precompute both partners. A miss falls through to the normal call. If a measurement shows first-audio getting slower with the buffer on, the template default goes back to off.
5. **One chat model resident, one recognizer resident.** A language switch replaces the recognizer process with that language's weight (`nb-whisper-medium` or `ggml-base.en`). Piper then uses the voice on the partner who is about to speak. The recognizer replacement finishes before the next transcription. The two Whisper weights are never loaded at the same time, and a second `qwen3:8b` is not loaded beside the first. The chat-model id still travels on the pair. The seeds both say `qwen3:8b`, with different prompts. A gender change does not restart the recognizer. Mid-sentence hot-swap is not required.
6. **Dossier preparation is not on the speech path.** Fixed topics ship their dossier as data. Extracting a dossier from a pasted article, which the proposal budgets at 1.5 s, is a button on that topic for later. It is not part of the first build, and it never runs while the user is waiting for a reply.
7. **Known greeting lines stay allowed to skip the model.** That fast path belongs to the `greetings` topic only. Conversation topics do not pretend a free sentence will beat one short model call.
8. **Context stays small.** Template `num_ctx` is 2048 and `num_predict` is 256, the same caps as today. A pair may lower `num_predict`. It may not raise `num_ctx` above 2048 in the template. Thinking stays off.

Honest targets, typed text, warm stack, one speaker:

| Situation | Target |
| --- | --- |
| Greetings topic, line already in the lexicon | Keep the aim already written in `faster.md`: first audio at or under 0.7 s once that lexicon exists. This plan does not build the lexicon. |
| Scripted first line of an anchor, audio already rendered for that pair | First audio under 0.7 s. No model call. |
| Open reply | First audio about one model call plus one Piper clip. On today's 8B that is near 2 s. Record the number. Do not claim 300 ms. |

Measured on this Mac while the turn was built: a typed Norwegian free-conversation line, warm `qwen3:8b`, one speaker, voice `no_NO-talesyntese-medium`, first audio 2.5 s. The greeting number above is 2.0 s. English speech was not measured. The audio image that is running does not contain `en_US-ryan-medium` until it is rebuilt. This measurement does not mark the open-reply target met.

A later change makes a conversation reply answer the meaning instead of repeating the learner. Greetings stay the drill above. An empty conversation lesson starts from the dossier's stored teacher question, with no model call. If the model's line only repeats the learner, Piper speaks that anchor's stored move. One model call per spoken line. Measured after that change: a typed Norwegian life-in-Norway line, warm `qwen3:8b`, recognizer `nb-whisper-base`, voice `no_NO-talesyntese-medium`, first audio 3686 ms. The heard line was a new question, not the typed line. The open-reply target stays unmet.

## What we take from the proposal

- **Dossier.** Each language + topic template has a dossier: topic, language, and a short list of anchors. An anchor has a focus, a teacher goal, the sibling's stance, and target words. The three conversation topics have a Norwegian dossier and an English dossier. `life_in_user_country` leaves the country as a slot filled from the user.
- **Intervention mode.** `fluency`, `balanced`, or `strict`, stored on the pair. Fluency lets the conversation continue unless the line is empty or off the dossier. Balanced corrects a severe flag or a miss on the anchor's target words, acknowledges the content, gives one short correction, and goes on. Strict stops on the scorecard's error flag and asks for the line again before the anchor advances.
- **Floor.** Human, then teacher, then human, then sibling, and so on. A bot speaks after the other bot only when a pair has same-turn handoff on. The sibling never corrects the user. The teacher is the one who corrects.
- **State.** The session stores the dossier anchor index, whose turn it is, the intervention mode, and the recent lines. That is the proposal's `ConversationState`, held in SQLite on the session, not only in process memory.

## What we leave from the proposal until measured

- A background worker that runs the whole time someone is speaking.
- Branching the buffer into several imagined replies.
- A separate evaluator LLM node in front of the speaker.
- Pasted-article ingestion on the way into a turn.
- The 300 ms budget for any turn that still calls the 8B model.

## Database

Same file, SQLModel, WAL. New tables beside the ones in `cognitive-hub/src/logoskittens/persistence.py`.

- **user.** `id`, display name, home country, created time. First launch inserts `user-local`. The name and country are editable. No passwords.
- **language.** `id`, display name, and the stack that id owns: recognizer weight, recognizer language code, the male voice id, the female voice id, chat-model id. Seed `nb` (Norwegian) and `en` (English) with the tables above. Further languages are more rows of the same shape.
- **topic.** `id`, title, sort order. The four rows above.
- **dossier.** `id`, language id, topic id, JSON body in the shape from the proposal. Unique on language + topic. Seed one body per conversation topic for `nb` and one for `en`.
- **pair_config.** `id`, user id or empty for a template, language id, topic id, and the settings JSON. Unique on user + language + topic, with empty user meaning the template.
- **session** gains `user_id`, `language_id`, `topic_id`, and `config_id` of the row that was resolved when the session started. Editing settings does not rewrite an open turn. The next turn reads the saved row again. Switching back to a pair resumes the latest session for that user + language + topic.

Settings JSON, all optional, defaults filled by resolution:

- Model: backend (`local` or `grok`), model id, base URL, temperature, `num_ctx`, `num_predict`, think.
- Speech in: language code, recognizer model id (stored; a second weight is not loaded by this plan).
- Teacher config: gender, the other personality traits, voice id, prompt. Seed gender `male`.
- Student config: gender, the other personality traits, voice id, prompt. Seed gender `female`. The student is the sibling.
- Dialogue: intervention mode, dossier id, same-turn handoff, speculative `off` or `idle_one`.
- Page: lesson title, input placeholder, teacher display name, student display name.

`llm.py` reads the resolved settings for that call. The environment variables remain the fallback when a field is empty, so an unset pair still reaches Ollama and `qwen3:8b`.

## Page

`virtual-stage/src/App.tsx` gains a left panel. On a wide window it stays open. On a narrow window it is a button that opens the same panel, then closes after a choice. Check both widths when this is built.

The panel, top to bottom:

- The user. One local user at first. Name, and country when the selected topic needs it.
- The language. Norwegian and English. Choosing one restarts the recognizer onto that language's weight, loads that language's dossier and prompts, and resumes the lesson for the new pair. Each partner's voice follows their gender on the new language's map. Add language still creates a row and copies templates, for a third language later. The first test uses the two seeds.
- The topics, as a list. Choosing one selects the pair and resumes that pair's lesson.
- The teacher. Male or female. The choice is the gender trait. The voice id and the way they speak update with it.
- The student. Male or female, same rule. Seed is female.
- Configure, for the pair that is selected. A form of the settings above, not a raw JSON box. Save writes the user + language + topic row, including both partner configs. The header, the placeholder, and the partner names change from the saved page fields. The next turn uses the rest.

The stage (both partners, the log, the typed line, Speak) stays on the right. Partner names on the cards come from the pair. Greetings keeps the current cards and the current turn until a conversation topic is selected.

## How a conversation turn runs

For `greetings`, `session.py` keeps the path it has now.

For the other topics:

1. The page sends text or audio, as it does now, plus the active user, language, and topic.
2. Audio, if any, is transcribed by the recognizer already loaded for this language. The model is not called during this.
3. Rules look at the text and the current anchor. The floor picks one speaker. A teacher preemption replaces the sibling for this turn.
4. That speaker gets one model call. The prompt carries the dossier anchor, the intervention mode, that partner's traits including gender, the agreement rule for this language, and the recent lines. The reply is a short scorecard plus the spoken line.
5. The line goes to Piper with that partner's voice id. With the seeds, an English teacher uses `en_US-ryan-medium` and an English student uses `en_US-lessac-medium`. Both Norwegian partners use `no_NO-talesyntese-medium`. The page receives one `ElementSolution` and plays it. SQLite writes the turn beside that voice, as it does today.
6. The anchor advances only when the mode says the exchange is done. Strict mode holds the anchor until the retry.
7. If this pair has speculative `idle_one`, one guess for the next partner may start after the audio was sent. It is discarded when the next recording or the next foreground call begins.

## Build order

Each phase is shippable. Do not start a phase by turning the speculative buffer on.

**1. Tables and seeds.** Schema, the local user, Norwegian and English with their recognizer and the male/female voice map, four topics, six conversation dossiers (three topics × two languages), template pair rows for both languages. Each template includes a teacher config (male) and a student config (female), with the other traits copied from the actor JSON. Resolution function with tests. The greeting page behaves as it does today because nothing reads the tables yet.

**2. Left panel, both languages, session binding.** List languages and topics. Selecting a pair resumes or starts the session for that triple. Selecting a language restarts `scripts/host_whisper.sh` onto that weight. Synthesize uses the speaking partner's voice id. The audio image contains `no_NO-talesyntese-medium`, `en_US-ryan-medium`, and `en_US-lessac-medium`. Gender controls sit on the panel. Greetings in Norwegian still uses the old turn until a conversation topic is selected. Conversation topics use a single speaker call, that partner's prompt (including gender), and that partner's voice. `audio.py` passes the pair's recognizer language into `audio-engine/server.py`. Log first-audio time, the recognizer weight, and the voice id. Run one Norwegian turn and one English turn.

**3. Configure.** The form, save, per-user override, page labels from the row. Country required before the first turn of "life in user country". Add language copies templates.

**4. Dossier and floor.** Anchors, the alternation, teacher preemption from rules plus the scorecard, sibling never corrects. Same-turn handoff stays off in the templates.

**5. Idle guess, opt-in.** Implement `idle_one` behind the setting. Default remains off. Measure one conversation topic with it off and on. Keep the default that wins on first-audio.

## Checks

- Resolving user + `nb` + `life_in_norway` returns that user's row when it exists, and the template when it does not.
- A second user with a different model id on the same pair does not change the first user's turn.
- Switching topic resumes the other topic's lines and does not mix them.
- A greetings turn still passes the current pipeline tests.
- A conversation turn makes one model call and sends one actor frame. A teacher preemption still sends one frame.
- With speculative off, no model call runs after the reply is sent.
- With speculative on, a new recording cancels the guess before the foreground call.
- A Norwegian pair transcribes "Hva skal jeg gjøre?" with `nb-whisper-medium`. The teacher and the student both speak with `no_NO-talesyntese-medium`. The teacher's prompt uses masculine self-reference. The student's prompt uses feminine self-reference.
- An English pair, after the language switch, transcribes "What should I do?" with `ggml-base.en`. The male teacher speaks with `en_US-ryan-medium`. The female student speaks with `en_US-lessac-medium`. The Norwegian weight is not loaded beside it.
- Setting the English student to male stores that trait and the next student line uses `en_US-ryan-medium` and a prompt that speaks as a man. Setting the teacher to female uses `en_US-lessac-medium`. The recognizer stays on `ggml-base.en`.
- Both turns use `qwen3:8b`. The prompts differ. A pair that saves another chat-model id uses that id on the next turn without loading it next to `qwen3:8b`.
- The left panel selects a topic on a wide window and on a narrow window, and Configure saves a value the next turn actually uses.
- First-audio for an open reply is written down next to the 2.0 s greeting number. No target in this file is marked met until that run exists.

## Out of scope

- Stage 10 cloud curricula and Stage 11 robots.
- Accounts, passwords, and more than a named local user row.
- Two chat models or two Whisper weights loaded at the same time. Switching language replaces one resident recognizer with the other.
- Translating the application chrome.
- Building the greeting lexicon from `faster.md`.
- Pasted-article dossiers.
- A raw JSON settings box.
