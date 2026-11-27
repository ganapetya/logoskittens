# LogosKittens
## Cognitive Edge & Robot Middleware (CERM)
### High-Level Architectural Specification & Implementation Blueprint

The live conversation is free speech. `free_conv.md` is the design of record for the talk, the prompts, the trainer, and the later stages. Sections 2, 6, and 8 below stay as written. Sections 3, 5, and 12 match that design. `flow.md`, `impl-conversation-oct-16.md`, and `conversational_architecture.md` are retired.

---

## 1. Executive Summary & Vision

**LogosKittens** is a domain-agnostic, distributed orchestration platform that decouples high-level cognitive reasoning (language models, multi-agent dialogues, strategic planning) from execution media (web avatars, screen sprites, embedded microcontrollers, and physical robotic actuators).

Originally conceived to power an interactive, multi-persona language learning environment and parallel robotics hardware (ROS 2 hexapods and wheeled bots), the system is designed to scale from local desktop applications to physical robot swarms.

### Core Architectural Value Proposition
* **Decoupled Agency:** Cognitive planning operates strictly on semantic and affective intents, remaining unaware of whether an actor is rendered on a browser canvas or actuated via physical servos.
* **Desktop/Edge-First Realization:** Packaged as a local, containerized runtime (Docker) that executes on macOS, Linux, or Windows. It runs entirely local, zero-cost, open-source AI pipelines for Speech-to-Text (STT) and Text-to-Speech (TTS), avoiding vendor lock-in and API fees.
* **LLM Provider Abstraction:** A single OpenAI-compatible interface (via LiteLLM or equivalent) allows swapping between local models (Ollama, llama.cpp), Grok (xAI), and other providers. Local and Grok are the MVP milestones; performance comparison is built in.
* **Seamless Physical Transference:** The foundational message contracts (`Situation`, `Task`, `Actor`, `GroupSolution`, `ElementSolution`) remain invariant across screen-based avatars and multi-agent physical hardware.
* **Embedded Persistence:** Lightweight SQLite (via SQLModel) for sessions, progress, actor state, and learning metrics. Zero external database server.
* **Cloud-Edge Synchronization:** Functions autonomously as an edge client while optionally synchronizing curricula and progression metrics with cloud services.

---

## 2. Universal Primitive Ontology

The middleware models all interactive and operational contexts using five immutable primitives:

1. **`Situation` (Contextual Envelope):** Captures the environment, operational constraints, participant state, and physical/virtual bounds. It represents the objective ground truth of "what is."
2. **`Task` (Strategic Intent):** The objective injected into the system (e.g., *"Norwegian greeting practice"*, *"Clear and patrol corridor alpha"*).
3. **`Actor` (Identity, Embodiment, Role & Personality):** An entity capable of state perception and action. An Actor couples an *Embodiment* (hardware capabilities or UI render targets) with a persistent *Role* (functional purpose in the dialogue) and *Personality Profile* (biases, temperament, linguistic quirks, emotional style).
4. **`GroupSolution` (Choreographed Coordination):** A high-level plan synthesized by the cognitive engine. On the MVP this is realized as **LangGraph conversation logic** that defines the overall conversation type, turn-taking protocol, and coordination strategy across participating actors. It does not dictate low-level execution details.
5. **`ElementSolution` (Atomic Execution Directive):** The compiled, single-actor directive containing exact phonetic, linguistic, emotional, and kinematic trajectories. It is produced by applying a specific Actor’s **Role** and **Personality** to the current turn.

---

## 3. Multi-Domain Projection Matrix

The same primitives project onto a screen now and onto a body later. Detail of the talk is in `free_conv.md`. The human is a participant, not an actor the hub compiles.

| Architectural Primitive | Domain 1: Local Desktop Edge (Web Stage) | Domain 2: Tabletop Embodied Robotics |
| :--- | :--- | :--- |
| **`Situation`** | Local Docker environment, 1 human via microphone, SVG canvas, language parameter. First live value is English. | Same situation. The human and the buddy share a room. The hub still does not know the body. |
| **`Task`** | Free speech. The subject is a lesson subject summarized once from raw material. | The same free-speech task. The adapter changes. The task does not. |
| **`Actor` `buddy-one`** | **Screen actor:** one SVG buddy. Voice from the language pack. English uses `en_US-lessac-medium`. Active. | **Physical actor:** hexapod spider. Same actor id, same `ElementSolution`, embodiment medium `physical_robot`. |
| **`Actor` `buddy-two`** | Stored and inactive. No avatar and no turn. | The same inactive actor. A later stage may put it on a second robot. |
| **`GroupSolution`** | Protocol `free_speech`. Turn order is `buddy-one` only. The talk does not end and does not correct the human. | The same group solution. A robotics bridge executes it. |
| **`ElementSolution`** | One per buddy turn. Stream TTS. One screen cue. Gestures empty in this pass. | The same message. A later adapter maps `KinematicGesture` and PCM onto the hexapod. |

---

## 4. System Architecture: Desktop Edge Topology

The system is deployed locally via a containerized multi-service architecture using Docker Compose.

### 4.1. `audio-engine` (The Ingress/Egress Senses)
* **Ingress (STT):** `whisper.cpp` server coupled with Silero VAD (Voice Activity Detection). Transcribes spoken audio chunks only when human speech is detected. Model weights are swappable (e.g., `nb-whisper-medium` for Norwegian; standard `whisper-base` for German, English, Russian, Hebrew).
* **Egress (TTS):** Piper TTS runtime. Provides real-time, zero-cost, localized acoustic synthesis. Executes language-specific voice checkpoints.
* **Interface:** Exposes internal HTTP/gRPC endpoints (`POST /transcribe`, `POST /synthesize`).

### 4.2. `cognitive-hub` (The Core Reasoning Engine)
* **Framework:** Python 3.11+, FastAPI, LangGraph, Pydantic v2, SQLModel.
* **LLM Provider Layer:** OpenAI-compatible abstraction (LiteLLM recommended). Configurable backends: local (Ollama/llama.cpp), Grok (xAI), or others. Performance comparison harness logs latency, token usage, and qualitative metrics.
* **Persistence:** Embedded SQLite database (single file, WAL mode) for sessions, actor state, user progress, vocabulary, and error tracking.
* **Responsibilities:**
  * Maintains the multi-agent state graph and conversation turn-taking logic (LangGraph).
  * Evaluates linguistic correctness (grammar, lexical choice).
  * Executes the **Role + Personality Filter** to generate multimodal outputs.
  * Exposes WebSocket servers for real-time state synchronization with frontend stages and edge hardware.

### 4.3. `virtual-stage` (The Frontend Interface)
* **Framework:** Vite, React, TypeScript, Tailwind CSS, Canvas / WebGL or SVG.
* **Responsibilities:**
  * Captures browser microphone input and routes it through an in-browser VAD gate.
  * Renders virtual actors and interactive contextual UI overlays.
  * Dispatches animations synchronized with audio playback.

---

## 5. The Actor, Role & Personality Engine

Actors are buddies. The human is ingress. Teacher and sibling roles are retired. See `free_conv.md`.

### Actor Definition Structure (JSON Schema Extract)
```json
{
  "actor_id": "buddy-one",
  "active": true,
  "embodiment": {
    "medium": "virtual_screen",
    "voice_profile": { "engine": "piper", "voice_id": "en_US-lessac-medium" },
    "supported_primitives": ["nod", "look"]
  },
  "role": "buddy",
  "personality": {
    "archetype": "conversation_buddy",
    "traits": { "patience": 0.8, "expressiveness": 0.6, "assertiveness": 0.4 },
    "linguistic_style": { "vocabulary_complexity": "everyday", "correction_strictness": "none" },
    "emotional_baseline": "curious"
  }
}
```

**Live actors**
* **`buddy-one` (active):** The partner the human talks to. An LLM agent, local by default, remote when the hub backend is Grok. Embodiment `virtual_screen` on the web stage. The same actor id and the same `ElementSolution` are what a hexapod adapter executes later. Switching body is an adapter and a medium (`physical_robot`), not a new brain. English voice `en_US-lessac-medium`. Correction strictness is `none`.
* **`buddy-two` (inactive):** Stored in the actor model. No graph node, no avatar, no turn. Voice `en_US-ryan-medium` is stored for a later stage. A second physical robot is this actor with `medium: physical_robot`. The later injection rule is fixed in `free_conv.md` and is not active.

---

## 6. Formal Data Contracts (Protobuf Specification)

The concrete, serialized directive dispatched to each actor adapter (whether web canvas or ROS 2 node).

```protobuf
syntax = "proto3";
package cerm.execution.v1;

enum EmotionType {
  EMOTION_NEUTRAL = 0;
  EMOTION_CURIOSITY = 1;
  EMOTION_DISAPPOINTMENT = 2;
  EMOTION_AMUSEMENT = 3;
  EMOTION_ENCOURAGEMENT = 4;
  EMOTION_FRUSTRATION = 5;
}

message Vector3 {
  double x = 1;
  double y = 2;
  double z = 3;
}

message AudioPayload {
  string text = 1;
  string language_code = 2;
  string voice_model_id = 3;
  bytes precomputed_audio_pcm = 4;
}

message KinematicGesture {
  string primitive_name = 1;      // e.g., "point", "shake_head", "recoil"
  Vector3 target_vector = 2;
  double duration_ms = 3;
}

message ScreenVisualCue {
  string animation_id = 1;
  string focus_target_id = 2;
  repeated string highlight_elements = 3;
}

message ElementSolution {
  string solution_id = 1;
  string actor_id = 2;
  EmotionType emotion = 3;
  AudioPayload speech = 4;
  repeated KinematicGesture physical_gestures = 5;
  ScreenVisualCue screen_visuals = 6;
}
```

---

## 7. Execution Lifecycle: The Conversational Loop

The running loop is the free-speech turn in `free_conv.md`: summarize the raw material once, then human and `buddy-one` alternate with no end. The steps below are the media path around that loop.

1. **Ingress:** Human holds the mic button. Audio buffer pushed to local STT. Typed text skips recognition.
2. **Transcription:** Whisper model transcribes buffer. String dispatched to Cognitive Hub via WebSocket.
3. **Planning:** LangGraph evaluates text against active Situation and Task. Synthesizes a `GroupSolution` (conversation orchestration).
4. **Compilation:** Intent is transformed into Actor-specific `ElementSolutions` by applying each Actor’s Role and Personality. Speech synthesis is triggered via Piper TTS.
5. **Execution:** Web browser or physical robot receives serialized payload. Playback triggers alongside facial/kinematic routines synchronously.
6. **Persistence:** The raw material id, the lesson subject, and the sentence log are written to SQLite. The last eight sentences are derived from that log.

---

## 8. Transition Architecture: Moving to Physical Robotics

To transition this system to physical robots (e.g., C++ ROS 2 nodes), the cognitive core remains completely untouched. Only the edge adapter layer is modified:

1. **The Edge Bridge:** Deploy a lightweight bridge node (C++ or Python) subscribing to the middleware's event bus via Zenoh or MQTT.
2. **Kinematic Mapping Server:** Receives `KinematicGesture(primitive_name="point")`. Evaluates URDF kinematics using an inverse kinematics solver. Generates `trajectory_msgs/msg/JointTrajectory` for the serial bus servo controller.
3. **Audio Routing:** The robot's onboard audio client subscribes to the synthesized PCM stream over the bridge and pipes the audio bytes directly to the onboard amplifier via ALSA.

---

## 9. Technology Stack

| Component / Layer | Technology Selected | Purpose / Architectural Justification |
| :--- | :--- | :--- |
| **Containerization** | Docker, Docker Compose | Provides one-click local orchestration across macOS, Linux, and Windows. |
| **STT Engine & Models** | `whisper.cpp` + Silero VAD | Minimal RAM/CPU overhead; zero API fees. Supports local models (e.g., `nb-whisper-medium`). |
| **TTS Engine** | Piper TTS | Ultra-fast local neural text-to-speech. Instantaneous output generation. |
| **LLM Abstraction** | LiteLLM (or OpenAI-compatible client) | Single interface for local models, Grok, and other providers. Enables performance comparison. |
| **Cognitive Framework** | Python 3.11, LangGraph, FastAPI | Expressive state-machine orchestration for multi-agent reasoning and turn-taking. |
| **Persistence** | SQLite + SQLModel | Lightweight, embedded, free, single-file database. Perfect for edge and local use. |
| **Data Contracts** | Protocol Buffers v3 | Compact, language-neutral binary serialization enabling Python <-> C++ <-> TS interoperability. |
| **Frontend Virtual Stage**| React, TypeScript, Vite | Highly responsive UI, zero-lag WebSocket handling, cross-platform browser support. |
| **Hardware Bridge** | ROS 2, Zenoh | Industrial-grade robotics communication bus optimized for real-time and lossy networks. |

---

## 10. Implementation Roadmap

### Phase 1: Local Docker Audio & Cognitive MVP
* [ ] Construct `docker-compose.yml` linking `audio-engine` (Whisper + Piper) and `cognitive-hub`.
* [ ] Verify local HTTP synthesis and transcription. The first live language is English. Norwegian weights stay available for a later pack.
* [ ] Implement the `httpx` LLM client with local Ollama and Grok backends.
* [ ] Implement the LangGraph free-speech loop in `free_conv.md`: one summarize node, then endless `buddy-one` turns.
* [ ] Implement SQLite persistence for the ongoing conversation.

### Phase 2: Virtual Stage & Multimodal Synchronization
* [ ] Build React/Vite web interface with microphone stream ingestion and local VAD gating.
* [ ] Implement animated 2D SVG avatar components on screen.
* [ ] Synchronize incoming `ElementSolution` visual cues with audio playback.

### Phase 3: External Context Integration
* [ ] Implement REST API integration with cloud server to fetch user-specific contexts (texts, vocabulary).
* [ ] Construct automated session summaries tracking user errors and new words introduced.

### Phase 4: Embodied Robotics Expansion
* [ ] Stand up ROS 2 / Zenoh bridge container.
* [ ] Write C++ Action Server mapping `KinematicGesture` messages to physical servo trajectories.
* [ ] Mount microphone/speaker hardware on physical robots.

---

## 11. Observability & Testing (Placeholder)

Structured logging, distributed tracing, conversation replay, and automated evaluation of linguistic quality will be added after the MVP conversational loop is stable. Current focus is functional correctness of the local loop.

---

## 12. MVP Task Specification

**Task:** Free speech in a selected language. The first language parameter is `en`. The subject comes from raw material, summarized once. A LogosCat workspace session can supply that raw material after login. The file source still runs when nobody is logged in. The first test material is a vacation in Norway in which tunnels and fjord beauty are discussed.

**Participants:**
* Human. A person on the microphone, or a pseudo-human only inside the trainer.
* `buddy-one`, active. Screen buddy now, hexapod later, same `ElementSolution`.
* `buddy-two`, stored and inactive until its stage is opened.

**Success criteria:** The human can hold an open talk with the web buddy about the selected raw material. The buddy answers in the session language, stays on the theme, and keeps going when the human is passive. The hub does not correct the human. One `ElementSolution` per turn plays audio and a visual cue. A reload resumes the same log. The trainer can propose a replacement of `prompt-of-subject-creation_en` or `ongoing_instruction_prompt_en`, and the user can approve or reject it. The prompts stay the starters until the user accepts a proposal.