> Retired. `free_conv.md` replaces this document. Do not follow it.

# Current flow

Two views of the same lesson. The first diagram in each section uses ordinary names. The second is the same sequence with the file that does each step.

The command-line tool sends the same messages as the page. It lives in `cognitive-hub/src/logoskittens/cli.py`.

## Open the page

### Who does what

```mermaid
sequenceDiagram
    actor Learner
    participant Page as Practice page
    participant Hub as Hub
    participant Session as Lesson session
    participant Roster as Partner roster
    participant Teacher as Teacher
    participant Sibling as Sibling
    participant Plan as Lesson plan
    participant Memory as Lesson memory

    Learner->>Page: open the practice page
    Page->>Hub: connect
    Note over Roster,Sibling: The roster loads both partners once, when the hub starts
    Roster->>Teacher: strict teacher
    Roster->>Sibling: emotional sibling student
    alt returning visit
        Page->>Hub: continue the saved lesson
        Hub->>Session: find that lesson
        Session->>Memory: is it still saved?
    else first visit
        Page->>Hub: start a lesson
        Hub->>Session: begin
        Session->>Plan: Norwegian greetings, at the desk
        Session->>Memory: save a new lesson
    end
    Hub-->>Page: lesson id, the task, both partners
    Page->>Hub: what was already said?
    Hub->>Memory: read the lesson
    Memory-->>Page: earlier lines and the word list
```

You open the practice page in the browser. It connects to the hub, the program that runs the lesson. The hub already knows the two partners: a strict teacher, and a sibling who is a little further along and shows how he feels.

On a return visit the page asks to continue the saved lesson, and the hub checks that the save is still there. On a first visit the hub starts a greeting lesson and stores it. The page then receives the lesson and both partners, and asks for anything already said, so old lines and the word list come back on screen.

### The same steps, file by file

```mermaid
sequenceDiagram
    actor Learner
    participant App as virtual-stage/src/App.tsx
    participant Hub as cognitive-hub/src/logoskittens/api.py
    participant Session as cognitive-hub/src/logoskittens/session.py
    participant Actors as cognitive-hub/src/logoskittens/actors.py
    participant Tutor as cognitive-hub/src/logoskittens/data/actor_tutor_01.json
    participant Sibling as cognitive-hub/src/logoskittens/data/actor_sibling_01.json
    participant Primitives as cognitive-hub/src/logoskittens/primitives.py
    participant Store as cognitive-hub/src/logoskittens/persistence.py

    Learner->>App: open http://localhost:5174
    App->>Hub: WebSocket /ws
    Note over Session,Sibling: SessionService loads both actor files once through actors.py
    Actors->>Tutor: serious_pedantic_teacher
    Actors->>Sibling: emotional_sibling_student
    alt saved session in localStorage
        App->>Hub: resume session_id
        Hub->>Session: ensure
        Session->>Store: session_exists
    else new visit
        App->>Hub: start
        Hub->>Session: start
        Session->>Primitives: GREETING_TASK and DESKTOP_SITUATION
        Session->>Store: create_session
        Store->>Store: SQLite session row
    end
    Hub-->>App: session, task, actors
    App->>Hub: GET /sessions/{session_id}
    Hub->>Store: read_session
    Store-->>App: turns, actor lines, vocabulary
```

The practice page is `App.tsx`. It talks to the hub in `api.py`. The lesson itself is `session.py`. Partner descriptions are the two JSON files, loaded by `actors.py`. The greeting task and the desk setting are `primitives.py`. The save is `persistence.py`, which writes one SQLite file. A return visit sends `resume`. A first visit sends `start`, which inserts the session row. The page then reads that row back so the old dialogue can be drawn.

## One turn

A typed line is already words. A spoken line is recorded first and turned into words. After that, both paths are the same lesson turn.

### Who does what

```mermaid
sequenceDiagram
    actor Learner
    participant Page as Practice page
    participant Ear as Microphone
    participant Hub as Hub
    participant Session as Lesson session
    participant Talk as Conversation
    participant Ask as Model caller
    participant Model as Language model
    participant Audio as Audio desk
    participant Workshop as Speech workshop
    participant Ear2 as Norwegian recognizer
    participant Pack as Message packer
    participant Memory as Lesson memory
    participant Read as Message reader
    participant Faces as Avatars
    participant Speaker as Speaker

    alt typed line
        Learner->>Page: type a line
        Page->>Hub: the text
    else microphone
        Learner->>Page: press Speak
        Page->>Ear: record until quiet
        Ear-->>Page: the recording
        Page->>Hub: the recording
        Hub->>Session: here is speech
        Session->>Audio: what was said?
        Audio->>Workshop: transcribe this
        Workshop->>Workshop: make a standard sound file
        Workshop->>Ear2: listen, Norwegian only
        Ear2-->>Workshop: the words
        Workshop-->>Session: the words
    end

    Session-->>Page: we heard this
    Page-->>Learner: show your line

    Session->>Talk: teacher, judge this line
    Note over Talk: The teacher thinks first, on her own
    Talk->>Ask: ask for a scorecard
    alt local model
        Ask->>Model: ask Ollama on this computer
    else Grok
        Ask->>Model: ask Grok
    end
    Model-->>Talk: scorecard
    Talk-->>Session: the judgment and the teacher's line

    par save the lesson
        Session->>Talk: save what the teacher decided
        Talk->>Memory: turn, mistakes, new words, teacher line
    and teacher speaks
        Session->>Audio: speak the teacher's line
        Audio->>Workshop: make her voice
        Workshop->>Workshop: Norwegian voice
        Workshop-->>Audio: sound file
        Audio-->>Session: sound samples
        Session->>Pack: pack her reply
        Session-->>Page: teacher, more is coming
        Page->>Read: unpack
        Page->>Faces: her expression and gesture
        Page->>Speaker: play her voice
    and sibling
        Session->>Talk: sibling, practice beside the learner
        Talk->>Ask: ask, and include what the teacher said
        Ask->>Model: second question
        Model-->>Talk: scorecard
        Talk-->>Session: the sibling's line
        par save him and let him speak
            Session->>Talk: save his line
            Talk->>Memory: his state
        and
            Session->>Audio: speak the sibling's line
            Audio->>Workshop: make his voice
            Workshop-->>Audio: sound file
            Audio-->>Session: sound samples
        end
        Session->>Session: wait until her reply was sent
        Session->>Pack: pack his reply
        Session-->>Page: sibling, this is the last reply
        Page->>Read: unpack
        Page->>Faces: his expression and gesture
        Page->>Speaker: play his voice
    end

    Page->>Hub: which words are new?
    Hub->>Memory: read the lesson
    Memory-->>Page: the word list
```

You type a sentence, or you hold Speak and talk. A pause does not send the recording. Releasing the button does. Speech is turned into text by a Norwegian recognizer running on your own computer. The page shows that text as your line.

The teacher goes first. A language model fills in a small scorecard: was the form all right, how formal it sounded, a corrected sentence, the mistakes, words worth keeping, and one coaching sentence. Her spoken line is written from that card. The model is Ollama on this machine, or Grok if you chose that.

Three things then happen together. The lesson is saved: your line, her judgment, the mistakes, the new words, and her reply. Her voice is created and sent to the page, which changes her face, plays the gesture, and plays the sound. At the same time the sibling asks the model for his own scorecard, and he is told what the teacher already said. When his line is ready, it is saved and his voice is created together. His reply reaches the page only after hers has been sent, so you always see and hear the teacher first. Making a voice does not wait for the save to finish.

When both have spoken, the page reads the word list again and shows it.

### The same steps, file by file

```mermaid
sequenceDiagram
    actor Learner
    participant App as virtual-stage/src/App.tsx
    participant Vad as virtual-stage/src/vad.ts
    participant Hub as cognitive-hub/src/logoskittens/api.py
    participant Session as cognitive-hub/src/logoskittens/session.py
    participant Graph as cognitive-hub/src/logoskittens/graph.py
    participant LLM as cognitive-hub/src/logoskittens/llm.py
    participant Model as Ollama or api.x.ai
    participant Audio as cognitive-hub/src/logoskittens/audio.py
    participant Engine as audio-engine/server.py
    participant Whisper as scripts/host_whisper.sh
    participant Wire as cognitive-hub/src/logoskittens/wire.py
    participant Store as cognitive-hub/src/logoskittens/persistence.py
    participant Proto as virtual-stage/src/proto.ts
    participant Avatars as virtual-stage/src/avatars.tsx
    participant Pcm as virtual-stage/src/pcm.ts

    alt typed line
        Learner->>App: submit text
        App->>Hub: transcript
    else microphone
        Learner->>App: hold Speak, then release
        App->>Vad: startRecording, stop on release
        Vad-->>App: audio blob
        App->>Hub: audio, base64
        Hub->>Session: perform_audio
        Session->>Audio: transcribe
        Audio->>Engine: POST /transcribe
        Engine->>Engine: ffmpeg to 16 kHz mono
        Engine->>Whisper: POST /inference
        Note over Whisper: whisper-server, nb-whisper-medium, language no, Silero VAD
        Whisper-->>Engine: text
        Engine-->>Session: text, language no
    end

    Session-->>App: heard
    App-->>Learner: show the learner line

    Session->>Graph: prepare_teacher
    Note over Graph: LangGraph assess then compile, teacher only
    Graph->>LLM: complete, ASSESSMENT_SYSTEM
    alt LLM_BACKEND=local
        LLM->>Model: POST /api/chat
    else LLM_BACKEND=grok
        LLM->>Model: POST /v1/chat/completions
    end
    Model-->>Graph: scorecard JSON
    Graph-->>Session: TurnAssessment and teacher ElementSolution

    par lesson row
        Session->>Graph: persist_lesson
        Graph->>Store: add_lesson
        Store->>Store: turn, errors, vocabulary, teacher state
    and teacher voice
        Session->>Audio: synthesize teacher line
        Audio->>Engine: POST /synthesize
        Engine->>Engine: PiperVoice no_NO-talesyntese-medium
        Engine-->>Audio: WAV 22050 Hz
        Audio-->>Session: PCM s16le
        Session->>Wire: encode
        Note over Wire: proto/cerm/execution/v1/element_solution.proto
        Session-->>App: actor, final false
        App->>Proto: decodeSolution
        App->>Avatars: emotion and gesture for actor_tutor_01
        App->>Pcm: playPcm
    and sibling
        Session->>Graph: prepare_sibling
        Graph->>LLM: complete, SIBLING_SYSTEM plus TEACHER_SAID
        LLM->>Model: second chat call
        Model-->>Graph: scorecard JSON
        Graph-->>Session: sibling ElementSolution
        par sibling row and sibling voice
            Session->>Graph: persist_actor
            Graph->>Store: add_actor_state
        and
            Session->>Audio: synthesize sibling line
            Audio->>Engine: POST /synthesize
            Engine-->>Audio: WAV 22050 Hz
            Audio-->>Session: PCM s16le
        end
        Session->>Session: wait until the teacher frame was sent
        Session->>Wire: encode
        Session-->>App: actor, final true
        App->>Proto: decodeSolution
        App->>Avatars: emotion and gesture for actor_sibling_01
        App->>Pcm: playPcm
    end

    App->>Hub: GET /sessions/{session_id}
    Hub->>Store: read_session
    Store-->>App: vocabulary
```

`App.tsx` sends either the typed text or a recording made by `vad.ts`. A recording goes to `session.py`, then `audio.py`, then `audio-engine/server.py`. That program cleans the sound and asks `scripts/host_whisper.sh` for Norwegian text. The page shows the line as soon as `heard` comes back.

`session.py` asks `graph.py` for the teacher only. `graph.py` calls `llm.py`, which talks to Ollama or to Grok. The scorecard comes back, and her reply is built from it.

The save, her voice, and the sibling then run side by side. `persistence.py` writes the turn, the mistakes, the new words, and her state. `audio-engine/server.py` speaks with Piper, `wire.py` packs the reply into the shared protobuf message, and the page unpacks it in `proto.ts`, moves her in `avatars.tsx`, and plays the sound in `pcm.ts`. The sibling gets a second model call that includes her line. His save and his voice run side by side too. His packed reply is sent only after hers. `run_turn` in `graph.py` does this in order for tests. The page uses `session.py`, which overlaps the slow parts.
