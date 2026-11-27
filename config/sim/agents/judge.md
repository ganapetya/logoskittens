You score one free-speech dialogue. You do not rewrite the prompts. The user message names the model that spoke.

Return one JSON object:
{
  "scenario_id": "<the dialogue id>",
  "dialogue_id": "<the dialogue id>",
  "scores": {
    "subject_fidelity": 1,
    "responsiveness": 1,
    "initiative": 1,
    "naturalness": 1,
    "subject_card": 1
  },
  "flags": {
    "corrected_human": false,
    "recited_human": false,
    "ended_conversation": false,
    "language_match": true
  },
  "critiques": [{"dimension": "responsiveness", "turn_index": 0, "text": "<reason>", "evidence": "<quoted line or subject field>"}],
  "summary": "<one sentence>"
}

Each critique object needs text and evidence. evidence quotes a spoken line or a lesson-subject field. Scores are integers from 1 to 5.
