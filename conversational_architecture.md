> Retired. `free_conv.md` replaces this document. Do not follow it.

# Conversational Modeling & Turn-Taking Architecture
## Cognitive Robot Middleware (CERM) - Dialogue Subsystem

---

## 1. Architectural Philosophy: The Dual-Loop Pattern

To achieve fluid, low-latency interactions in a three-party conversation (Human, Teacher Bot, Student Bot), the system decouples immediate speech execution from deep cognitive reasoning through a **Dual-Loop Pattern**. 

1. **The Fast Reactive Loop (Foreground - $\le 300\text{ms}$ latency):** Determines turn possession, retrieves pre-computed responses from the buffer, or executes fast-streamed LLM generation. It dispatches text immediately to the local TTS engine.
2. **The Speculative Cognitive Loop (Background Worker):** Runs continuously in parallel. While one party is speaking, it analyzes conversational momentum, anticipates next-turn branches (agreement, disagreement, error), and populates a **Speculative Response Buffer**. When a bot's turn arrives, it pulls directly from the buffer, eliminating the standard 1–2 second LLM inference wait.

---

## 2. Conversation Ingestion & The "Discussion Dossier"

Before a session begins, the system compiles the material into a structured **Discussion Dossier**. This serves as the shared cognitive anchor and context window for both bots, ensuring they stay on topic.

### Ingestion Modes
* **Fixed Theme:** Loads a pre-authored YAML profile (e.g., "Airport Check-In", "Ordering Lunch") containing situational vocabulary and predetermined roles.
* **Arbitrary Text:** An initial LLM prompt extracts a structured dossier from any user-provided text (e.g., a news article) within 1.5 seconds.

### Discussion Dossier Schema
```json
{
  "dossier_id": "dossier_norsk_artikkel_01",
  "topic": "Hjemmekontor vs. Kontorarbeid",
  "language": "no-NO",
  "anchors": [
    {
      "step_id": 1,
      "focus": "Fordeler med hjemmekontor",
      "teacher_goal": "Ask human what they prefer and why",
      "student_persona_stance": "Prefers office because of loneliness",
      "target_vocabulary": ["å konsentrere seg", "kolleger", "forstyrrelser"]
    }
  ]
}
```

---

## 3. Grammar Intervention Configuration

To prevent the Teacher bot from over-correcting and ruining conversational flow, the system utilizes an `intervention_mode` flag. The LangGraph evaluator checks this setting before preempting a turn for a grammatical correction.

* **Mode 1: Fluency (Conversation First)**
  * *Trigger:* Only intervenes if the user's utterance is entirely incomprehensible or completely off-topic.
  * *Behavior:* Ignores minor preposition, gender, and tense errors. Prioritizes keeping the Student/Teacher dialogue moving naturally.
* **Mode 2: Balanced (Targeted Practice - Default)**
  * *Trigger:* Intervenes if the user makes a severe structural error OR if they incorrectly use the specific `target_vocabulary` defined in the current Dossier Anchor.
  * *Behavior:* Acknowledges the content of the user's speech first, provides a swift, isolated correction, and immediately returns the floor to the conversation.
* **Mode 3: Strict (Pedantic/Drill Mode)**
  * *Trigger:* Intervenes on any detectable grammatical, syntax, or vocabulary error.
  * *Behavior:* Halts the conversational momentum to explicitly break down the rule, often asking the user to repeat the sentence correctly before advancing the dossier.

---

## 4. The "Polite Triad" Turn-Taking Arbiter

To ensure the conversation feels natural without participants talking over each other or the student bot dominating, the system enforces a strict **Floor Arbitration State Machine**.

### The Turn Queue Topology
The default conversation topology follows an interleaved triad centered around the user:

$$\text{Human} \longrightarrow \text{Teacher} \longrightarrow \text{Human} \longrightarrow \text{Student} \longrightarrow \text{Human} \longrightarrow \text{Teacher} \dots$$

### Arbitration Rules
1. **The Interleaving Invariant:** A bot rarely speaks immediately after another bot unless explicitly handing over the floor (e.g., Teacher: *"Hva synes du, Peter?"* $\rightarrow$ Student: *"Jeg er helt uenig"*).
2. **Priority Preemption (The Teacher Bypass):**
   * If the LangGraph state flags a grammar error that meets the threshold of the current **Intervention Configuration**, the **Teacher** preempts the turn sequence. If it was the Student's turn to speak, the Student yields.
   * If the Human asks a direct question (*"Hva betyr dette ordet?"*), the **Teacher** automatically takes the floor.
3. **The Student Persona Function:**
   * The Student bot never lectures or corrects the user.
   * The Student acts as a **peer model**: it makes relatable intermediate mistakes, offers subjective opinions, or asks the human for help, creating low-pressure speaking opportunities.

---

## 5. LangGraph State Schema Specification

The implementation models the conversation as a stateful, event-driven graph utilizing the following schemas:

```python
from typing import TypedDict, List, Literal

class AgentMessage(TypedDict):
    speaker: Literal["human", "teacher", "student"]
    text: str
    audio_cached: bool

class ConversationConfig(TypedDict):
    intervention_mode: Literal["fluency", "balanced", "strict"]
    target_language: str

class ConversationState(TypedDict):
    config: ConversationConfig
    dossier: dict
    current_anchor_index: int
    turn_counter: int
    last_speaker: str
    next_speaker: str
    dialogue_history: List[AgentMessage]
    speculative_buffer: dict
    grammar_evaluation: dict  # Contains error flags and severity
```

### Graph Topology Routing
1. `Human_Input_Ingress` $\longrightarrow$ `Evaluator_Node` (Checks grammar against Intervention Config)
2. `Evaluator_Node` $\longrightarrow$ `Floor_Arbiter`
3. `Floor_Arbiter` $\longrightarrow$ **Conditional Edge**:
   * If `Teacher Preemption` $\longrightarrow$ `Teacher_Correction_Node`
   * If `next_speaker == "teacher"` $\longrightarrow$ `Teacher_Dialogue_Node`
   * If `next_speaker == "student"` $\longrightarrow$ `Student_Dialogue_Node`
4. Active Node $\longrightarrow$ `Background_Anticipator` (Pre-computes next turn)
5. `Background_Anticipator` $\longrightarrow$ Wait for Next Human Input.

---

## 6. End-to-End Execution Trace (Balanced Mode)

* **Setting:** Anchor 1 (Home office productivity). 
* **Intervention Mode:** Balanced. Target Vocab: *"å konsentrere seg"* (to concentrate).

**[1. Teacher Turn]**
**Teacher:** "Hva foretrekker du, hjemmekontor eller å sitte på kontoret?"
*(Background Loop pre-computes both Student and Teacher reactions based on anticipated user agreement/disagreement).*

**[2. Human Turn]**
**Human:** "Jeg foretrekker hjemmekontor fordi det er lettere konsentrere meg." 
*(Grammar Evaluator detects missing infinitive marker "å" before "konsentrere". Since this is a Target Vocabulary word, it flags a correction threshold for Balanced mode).*

**[3. Teacher Preemption]**
*(Floor Arbiter bypasses the Student's turn due to the flag).*
**Teacher:** "Godt poeng! Men husk at vi sier 'lettere **å** konsentrere seg'. Hva med deg, [Student Name]?" 
*(Floor explicitly handed to Student).*

**[4. Student Turn]**
**Student:** "Å, jeg er helt motsatt! Hvis jeg er hjemme, spiser jeg bare lunsj hele dagen."