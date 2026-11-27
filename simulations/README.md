# Simulation trials

`python -m logoskittens.sim improve` writes each round here.

Commit `decision.md` and `scores.json` from a round. Those files hold the proposal, the full prompt text, the hypothesis, the scores, and whether it was approved or rejected.

Git ignores the generated bulk in a round: `traces/`, the copied `config/` checkout, `calls.log`, `baseline/`, sqlite, wav, pcm, and model binaries. The accepted prompt is copied back into `config/prompts/` by `approve`.
