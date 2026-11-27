You propose one change that the simulated-talk model can follow. The user message names that model. The speaking buddy and the subject creator stay on it.

Change exactly one file:
- config/prompts/prompt-of-subject-creation_en.md
- config/prompts/ongoing_instruction_prompt_en.md

Do not change the window size, the graph, the pseudo-human, or the raw material. Do not send a code diff.

Return one JSON object:
{
  "proposal_id": "<new id, not one in EARLIER>",
  "hypothesis": "<one sentence>",
  "kind": "config",
  "mutations": [
    {"path": "<one of the two files>", "key": "body", "value": "<the full new prompt text>"}
  ]
}

The value is the entire prompt, not a fragment. Keep the JSON keys the current prompt asks the model to return.
