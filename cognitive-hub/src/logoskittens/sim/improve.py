"""Train the two English prompts. Local model speaks. Grok judges and proposes.

Trials are written under ``simulations/`` in this repository.
``approve`` copies a prompt back only when the scores accept it.
``reject`` records the refusal and does not ask for another proposal.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from logoskittens.llm import LLMError
from logoskittens.sim.schema import apply_proposal, check_proposal, compare_verdicts, parse_verdict
from logoskittens.sim.training_env import talk_label

PROMPT_NAMES = (
    "config/prompts/prompt-of-subject-creation_en.md",
    "config/prompts/ongoing_instruction_prompt_en.md",
)


def sim_root() -> Path:
    raw = os.environ.get("LOGOSKITTENS_SIM_ROOT", "").strip()
    if raw:
        return Path(raw)
    return find_repo(Path(__file__).resolve()) / "simulations"


def find_repo(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / "config" / "sim" / "matrix.json").is_file():
            return candidate
    raise FileNotFoundError("config/sim/matrix.json was not found")


def parse_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("model did not return a JSON object")
    payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("model did not return a JSON object")
    return payload


def load_state(work: Path) -> dict:
    path = work / "state.json"
    if not path.is_file():
        return {
            "status": "idle",
            "round": 0,
            "pending_proposal": None,
            "history": [],
            "report": str(work / "report.md"),
        }
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(work: Path, state: dict) -> None:
    work.mkdir(parents=True, exist_ok=True)
    (work / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_runner(matrix: Path, out: Path, config: Path, repo: Path) -> None:
    """Replay the simulated talk. The child reads `.env_training` for that role."""
    env = os.environ.copy()
    env["LOGOSKITTENS_CONFIG"] = str(config)
    env.setdefault("LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    cmd = [
        sys.executable,
        "-m",
        "logoskittens.sim",
        "run",
        "--matrix",
        str(matrix),
        "--out",
        str(out),
    ]
    subprocess.run(cmd, cwd=repo, env=env, check=True)


def run_cycle(repo: Path, work: Path, *, complete, runner, fresh: bool = False) -> dict:
    work.mkdir(parents=True, exist_ok=True)
    os.environ["LOGOSKITTENS_CALL_LOG"] = str(work / "calls.log")
    state = load_state(work)
    if fresh:
        state["history"] = []
    matrix = repo / "config" / "sim" / "matrix.json"
    baseline = work / "baseline"
    if fresh or not (baseline / "passive_en.json").is_file():
        runner(matrix, baseline, repo / "config", repo)
    traces = _load_traces(baseline, _ids(matrix))
    verdicts = judge_lessons(complete, repo, traces)
    _write_json(work / "baseline.verdicts.json", verdicts)
    proposal = propose_change(complete, repo, verdicts, traces, state.get("history") or [])
    check_proposal(proposal)
    state["pending_proposal"] = proposal
    state["status"] = "awaiting_approval"
    state["round"] = int(state.get("round") or 0)
    report = render_report(state, verdicts, proposal)
    (work / "report.md").write_text(report, encoding="utf-8")
    state["report"] = str(work / "report.md")
    save_state(work, state)
    _write_json(work / "pending.json", proposal)
    return state


def approve_pending(repo: Path, work: Path, *, complete, runner) -> dict:
    state = load_state(work)
    proposal = state.get("pending_proposal")
    if not proposal:
        raise ValueError("nothing is waiting")
    check_proposal(proposal)
    state["round"] = int(state.get("round") or 0) + 1
    round_id = f"round-{state['round']}-{proposal['proposal_id']}"
    trial_root = sim_root() / round_id
    config = trial_root / "config"
    if config.exists():
        shutil.rmtree(config)
    shutil.copytree(repo / "config", config)
    apply_proposal(trial_root, proposal)
    out = trial_root / "traces"
    try:
        runner(repo / "config" / "sim" / "matrix.json", out, config, repo)
    except subprocess.CalledProcessError as exc:
        _record_decision(trial_root, proposal, "lesson run failed", [])
        state["history"].append({"proposal_id": proposal["proposal_id"], "outcome": "lesson run failed"})
        state["pending_proposal"] = None
        state["status"] = "idle"
        _write_report(work, state, [], proposal, note="The lesson run failed.")
        save_state(work, state)
        raise ValueError("lesson run failed") from exc
    traces = _load_traces(out, _ids(repo / "config" / "sim" / "matrix.json"))
    verdicts = judge_lessons(complete, repo, traces)
    before = _read_json(work / "baseline.verdicts.json")
    compared = compare_verdicts(before, verdicts)
    outcome = "accepted" if compared["accept"] else "scores fell"
    _record_decision(trial_root, proposal, outcome, verdicts, compared)
    if compared["accept"]:
        for change in proposal["mutations"]:
            source = trial_root / change["path"]
            target = repo / change["path"]
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        runner(repo / "config" / "sim" / "matrix.json", work / "baseline", repo / "config", repo)
        _write_json(work / "baseline.verdicts.json", verdicts)
    state["history"].append({"proposal_id": proposal["proposal_id"], "outcome": outcome})
    state["history"] = state["history"][-8:]
    nxt = propose_change(complete, repo, verdicts, traces, state["history"])
    check_proposal(nxt)
    state["pending_proposal"] = nxt
    state["status"] = "awaiting_approval"
    _write_report(work, state, verdicts, nxt, note=outcome)
    save_state(work, state)
    _write_json(work / "pending.json", nxt)
    return state


def reject_pending(repo: Path, work: Path) -> dict:
    del repo
    state = load_state(work)
    proposal = state.get("pending_proposal")
    if not proposal:
        raise ValueError("nothing is waiting")
    round_id = f"round-reject-{proposal['proposal_id']}"
    _record_decision(sim_root() / round_id, proposal, "rejected by the user", [])
    state["history"].append({"proposal_id": proposal["proposal_id"], "outcome": "rejected by the user"})
    state["history"] = state["history"][-8:]
    state["pending_proposal"] = None
    state["status"] = "rejected"
    _write_report(work, state, [], None, note="Rejected. No new proposal.")
    save_state(work, state)
    pending = work / "pending.json"
    if pending.exists():
        pending.unlink()
    return state


def judge_lessons(complete, repo: Path, traces: list[dict]) -> list[dict]:
    system = (repo / "config" / "sim" / "agents" / "judge.md").read_text(encoding="utf-8")
    rubric = (repo / "config" / "sim" / "rubric.md").read_text(encoding="utf-8")
    verdicts = []
    for trace in traces:
        user = (
            f"The speaking model was {talk_label(repo)}.\n\n"
            + rubric
            + "\n\nDIALOGUE:\n"
            + json.dumps(trace, ensure_ascii=False)
        )
        payload = _complete_json(complete, user, system, label=f"judge {trace['id']}")
        payload = _slim_verdict(payload, trace["id"])
        verdicts.append(parse_verdict(payload).model_dump())
    return verdicts


def propose_change(complete, repo: Path, verdicts: list[dict], traces: list[dict], history: list[dict]) -> dict:
    system = (repo / "config" / "sim" / "agents" / "optimizer.md").read_text(encoding="utf-8")
    prompts = []
    for name in PROMPT_NAMES:
        prompts.append(f"FILE {name}\n{(repo / name).read_text(encoding='utf-8')}")
    user = (
        f"The simulated talk runs on {talk_label(repo)}.\n\n"
        "CURRENT PROMPTS:\n"
        + "\n\n".join(prompts)
        + "\n\nVERDICTS:\n"
        + json.dumps(verdicts, ensure_ascii=False)
        + "\n\nEARLIER:\n"
        + json.dumps(history[-8:], ensure_ascii=False)
        + "\n\nChange exactly one of the two prompt files."
    )
    payload = _complete_json(complete, user, system, label="propose")
    return check_proposal(payload).model_dump()


def _complete_json(complete, user: str, system: str, *, label: str) -> dict:
    last_error = "model did not return a JSON object"
    prompt = user
    for attempt in range(2):
        print(f"{label} attempt {attempt + 1}", file=sys.stderr, flush=True)
        try:
            raw, _record = complete(
                prompt,
                system=system,
                temperature=0,
                backend="grok",
                timeout=420,
                num_predict=1200,
            )
        except LLMError as exc:
            last_error = str(exc)
            print(f"{label} failed: {last_error[:180]}", file=sys.stderr, flush=True)
            continue
        try:
            return parse_json_object(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            prompt = user + "\n\nThe last reply was invalid. Return one JSON object.\n" + last_error
    raise ValueError(last_error)


def _slim_verdict(payload: dict, scenario_id: str) -> dict:
    critiques = []
    for item in payload.get("critiques") or []:
        if isinstance(item, str):
            critiques.append({"text": item, "evidence": item})
            continue
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("comment") or item.get("reason") or ""
        evidence = item.get("evidence") or text
        if text and evidence:
            critiques.append(
                {
                    "dimension": str(item.get("dimension") or ""),
                    "turn_index": int(item.get("turn_index") or 0),
                    "text": str(text),
                    "evidence": str(evidence),
                }
            )
    payload["critiques"] = critiques
    payload.setdefault("scenario_id", scenario_id)
    payload.setdefault("dialogue_id", scenario_id)
    return payload


def _record_decision(folder: Path, proposal: dict, outcome: str, verdicts: list[dict], compared: dict | None = None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    change = proposal["mutations"][0]
    body = [
        f"# {proposal['proposal_id']}",
        "",
        f"Outcome: {outcome}",
        "",
        f"File: `{change['path']}`",
        "",
        "Hypothesis:",
        "",
        proposal["hypothesis"],
        "",
        "Proposed prompt:",
        "",
        change["value"],
        "",
    ]
    if compared:
        body.extend(["Scores:", "", "```json", json.dumps(compared, ensure_ascii=False, indent=2), "```", ""])
    (folder / "decision.md").write_text("\n".join(body), encoding="utf-8")
    (folder / "scores.json").write_text(
        json.dumps({"outcome": outcome, "verdicts": verdicts, "compared": compared or {}}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def render_report(state: dict, verdicts: list[dict], proposal: dict | None) -> str:
    lines = ["# Free-speech trainer", "", f"Status: {state.get('status')}", ""]
    if verdicts:
        lines.append("## Scores")
        lines.append("")
        for item in verdicts:
            scores = item["scores"]
            rendered = ", ".join(f"{key} {scores[key]}" for key in scores)
            lines.append(f"- {item['scenario_id']}: {rendered}")
        lines.append("")
    if proposal:
        change = proposal["mutations"][0]
        lines.extend(
            [
                "## Waiting",
                "",
                f"{proposal['proposal_id']}: {proposal['hypothesis']}",
                "",
                f"File: `{change['path']}`",
                "",
            ]
        )
    return "\n".join(lines)


def _write_report(work: Path, state: dict, verdicts: list[dict], proposal: dict | None, *, note: str) -> None:
    text = note + "\n\n" + render_report(state, verdicts, proposal)
    (work / "report.md").write_text(text, encoding="utf-8")
    state["report"] = str(work / "report.md")


def _ids(matrix: Path) -> list[str]:
    return [item["id"] for item in json.loads(matrix.read_text(encoding="utf-8"))]


def _load_traces(directory: Path, ids: list[str]) -> list[dict]:
    traces = []
    for scenario_id in ids:
        path = directory / f"{scenario_id}.json"
        traces.append(json.loads(path.read_text(encoding="utf-8")))
    return traces


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))
