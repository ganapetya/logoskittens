# Cognitive Edge & Robot Middleware (CERM)
## High-Level Architectural Specification & Implementation Blueprint

---

## 1. Executive Summary & Vision

The **Cognitive Edge & Robot Middleware (CERM)** is a domain-agnostic, distributed orchestration platform that decouples high-level cognitive reasoning (language models, multi-agent dialogues, strategic planning) from execution media (web avatars, screen sprites, embedded microcontrollers, and physical robotic actuators). 

Originally conceived to power an interactive, multi-persona language learning environment (LogosCat) and parallel robotics hardware (ROS 2 hexapods and wheeled bots), the system is designed to scale from local desktop applications to physical robot swarms.

### Core Architectural Value Proposition
* **Decoupled Agency:** Cognitive planning operates strictly on semantic and affective intents, remaining unaware of whether an actor is rendered on a browser canvas or actuated via physical servos.
* **Desktop/Edge-First Realization:** Packaged as a local, containerized runtime (Docker) that executes on macOS, Linux, or Windows. It runs entirely local, zero-cost, open-source AI pipelines for Speech-to-Text (STT) and Text-to-Speech (TTS), avoiding vendor lock-in and API fees.
* **Seamless Physical Transference:** The foundational message contracts (`Situation`, `Task`, `Actor`, `GroupSolution`, `ElementSolution`) remain invariant across screen-based avatars and multi-agent physical hardware.
* **Cloud-Edge Synchronization:** Functions autonomously as an edge client while optionally synchronizing curricula and progression metrics with cloud services.

---

## 2. Universal Primitive Ontology

The middleware models all interactive and operational contexts using five immutable primitives:

1. **`Situation` (Contextual Envelope):** Captures the environment, operational constraints, participant state, and physical/virtual bounds. It represents the objective ground truth of "what is."
2. **`Task` (Strategic Intent):** The objective injected into the system (e.g., *"Debate Norwegian grammatical structures"*, *"Clear and patrol corridor alpha"*).
3. **`Actor` (Identity, Embodiment & Personality):** An entity capable of state perception and action. An Actor couples an *Embodiment* (hardware capabilities or UI render targets) with a persistent *Personality Profile* (biases, temperament, linguistic quirks).
4. **`GroupSolution` (Choreographed Coordination):** A high-level plan synthesized by the cognitive engine. It dictates turn-taking, role distribution, dialogue structure, and collaborative movement strategies across participating actors without dictating low-level execution details.
5. **`ElementSolution` (Atomic Execution Directive):** The compiled, single-actor directive containing exact phonetic, linguistic, emotional, and kinematic trajectories customized for that specific actor's embodiment.

---

## 3. Multi-Domain Projection Matrix

| Architectural Primitive | Domain 1: Local Desktop Edge (Web Stage) | Domain 2: Tabletop Embodied Robotics |
| :--- | :--- | :--- |
| **`Situation`** | Local Docker environment, 1 human via microphone, WebGL canvas, 2 virtual partners. | Living-room table, 1 human, ambient acoustic noise, Wi-Fi latency, 2 physical robots. |
| **`Task`** | Conversational language practice: finding lost items. | Coordinated physical search: locate dynamic object. |
| **`Actor A`** | **Screen Actor:** SVG Avatar (*Sarcastic Native Speaker*). | **Physical Actor:** Hexapod with 3-DoF arm (*Pedantic Tutor*). |
| **`Actor B`** | **Screen Actor:** SVG Avatar (*Encouraging Peer*). | **Physical Actor:** Wheeled Bot with camera (*Eager Scout*). |
| **`GroupSolution`** | Socratic dialogue protocol: Actor A challenges user grammar; Actor B provides helpful hints. | Coordinated search & point: Actor B explores; Actor A tracks and articulates arm toward target. |
| **`ElementSolution` (A)**| Stream TTS; trigger CSS eye-roll animations. | Stream TTS audio; command arm inverse kinematics to point at coordinate $[x,y,z]$. |
| **`ElementSolution` (B)**| Stream TTS; render grammar cheat-sheet overlay. | Navigate toward target; publish coordinate transform relative to base frame (`tf2`). |

---

## 4. System Architecture: Desktop Edge Topology

The system is deployed locally via a containerized multi-service architecture using Docker Compose.

### 4.1. `audio-engine` (The Ingress/Egress Senses)
* **Ingress (STT):** `whisper.cpp` server coupled with Silero VAD (Voice Activity Detection). Transcribes spoken audio chunks only when human speech is detected. Model weights are swappable (e.g., `nb-whisper-base` for Norwegian; standard `whisper-base` for German, English, Russian, Hebrew).
* **Egress (TTS):** Piper TTS runtime. Provides real-time, zero-cost, localized acoustic synthesis. Executes language-specific voice checkpoints.
* **Interface:** Exposes internal HTTP/gRPC endpoints (`POST /transcribe`, `POST /synthesize`).

### 4.2. `cognitive-hub` (The Core Reasoning Engine)
* **Framework:** Python 3.11+, FastAPI, LangGraph, Pydantic v2.
* **Responsibilities:**
  * Maintains the multi-agent state graph and conversation turn-taking logic.
  * Evaluates linguistic correctness (grammar, lexical choice).
  * Executes the **Personality Filter** to generate multimodal outputs.
  * Exposes WebSocket servers for real-time state synchronization with frontend stages and edge hardware.

### 4.3. `virtual-stage` (The Frontend Interface)
* **Framework:** Vite, React, TypeScript, Tailwind CSS, Canvas / WebGL.
* **Responsibilities:**
  * Captures browser microphone input and routes it through an in-browser VAD gate.
  * Renders virtual actors and interactive contextual UI overlays.
  * Dispatches animations synchronized with audio playback.

---

## 5. The Actor & Personality Engine

### Actor Definition Structure (JSON Schema Extract)
```json
{
  "actor_id": "actor_tutor_01",
  "embodiment": {
    "medium": "virtual_screen",
    "voice_profile": { "engine": "piper", "voice_id": "no_NO-tove-medium" },
    "supported_primitives": ["shake_head", "point", "eye_roll"]
  },
  "personality": {
    "archetype": "pedantic_tutor",
    "traits": { "patience": 0.2, "expressiveness": 0.8, "assertiveness": 0.9 },
    "linguistic_style": { "vocabulary_complexity": "academic", "correction_strictness": "pedantic" }
  }
}
```

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

1. **Ingress:** Human speaks. Local VAD flags speech termination. Audio buffer pushed to local STT.
2. **Transcription:** Whisper model transcribes buffer. String dispatched to Cognitive Hub via WebSocket.
3. **Planning:** LangGraph evaluates text against active Situation. Synthesizes a `GroupSolution`.
4. **Compilation:** Intent transformed into Actor-specific `ElementSolutions`. Speech synthesis triggered via Piper TTS.
5. **Execution:** Web browser or physical robot receives serialized payload. Playback triggers alongside facial/kinematic routines synchronously.

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
| **STT Engine & Models** | `whisper.cpp` + Silero VAD | Minimal RAM/CPU overhead; zero API fees. Supports local models (e.g., `nb-whisper-base`). |
| **TTS Engine** | Piper TTS | Ultra-fast local neural text-to-speech. Instantaneous output generation. |
| **Cognitive Framework** | Python 3.11, LangGraph, FastAPI | Expressive state-machine orchestration for multi-agent reasoning and turn-taking. |
| **Data Contracts** | Protocol Buffers v3 | Compact, language-neutral binary serialization enabling Python <-> C++ <-> TS interoperability. |
| **Frontend Virtual Stage**| React, TypeScript, Vite | Highly responsive UI, zero-lag WebSocket handling, cross-platform browser support. |
| **Hardware Bridge** | ROS 2, Zenoh | Industrial-grade robotics communication bus optimized for real-time and lossy networks. |

---

## 10. Implementation Roadmap

### Phase 1: Local Docker Audio & Cognitive MVP
* [ ] Construct `docker-compose.yml` linking `audio-engine` (Whisper + Piper) and `cognitive-hub`.
* [ ] Verify local HTTP/gRPC synthesis and transcription loops in target languages.
* [ ] Implement LangGraph state machine maintaining turn-taking between two virtual personas and one user.

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