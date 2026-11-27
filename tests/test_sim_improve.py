"""Approve copies a prompt only when scores rise. Reject does not ask again."""

import json
from pathlib import Path

import pytest

from logoskittens.sim.improve import approve_pending, reject_pending, run_cycle


def _trace(scenario: str) -> dict:
    return {
        "id": scenario,
        "language": "en",
        "material_id": "norway_vacation_tunnels_fjords",
        "subject": {
            "used_words": ["fjords"],
            "significant_words": ["fjords"],
            "theme": "Fjords.",
            "small_talk_subjects": ["What did the water look like?"],
        },
        "turns": [{"human": "yes", "buddy": "The fjord stayed bright.", "emotion": "EMOTION_CURIOSITY"}],
        "transcript": ["human: yes", "buddy: The fjord stayed bright."],
    }


def _verdict(scenario: str, initiative: int = 3, corrected: bool = False) -> dict:
    return {
        "scenario_id": scenario,
        "dialogue_id": scenario,
        "scores": {
            "subject_fidelity": 3,
            "responsiveness": 3,
            "initiative": initiative,
            "naturalness": 3,
            "subject_card": 3,
        },
        "flags": {
            "corrected_human": corrected,
            "recited_human": False,
            "ended_conversation": False,
            "language_match": True,
        },
        "critiques": [
            {
                "dimension": "initiative",
                "turn_index": 0,
                "text": "The buddy opened the fjord.",
                "evidence": "The fjord stayed bright.",
            }
        ],
        "summary": "Usable.",
    }


def _proposal(text: str = "Speak about the fjord in one sentence.\n") -> dict:
    return {
        "proposal_id": "fjord-line",
        "hypothesis": "A shorter buddy instruction.",
        "kind": "config",
        "mutations": [
            {
                "path": "config/prompts/ongoing_instruction_prompt_en.md",
                "key": "body",
                "value": text,
            }
        ],
    }


def _layout(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "config" / "sim" / "agents").mkdir(parents=True)
    (repo / "config" / "prompts").mkdir()
    (repo / "config" / "sim" / "matrix.json").write_text(
        json.dumps(
            [
                {
                    "id": "passive_en",
                    "language": "en",
                    "material_id": "norway_vacation_tunnels_fjords",
                    "script": "config/sim/scripts/passive_en.jsonl",
                }
            ]
        ),
        encoding="utf-8",
    )
    (repo / "config" / "sim" / "rubric.md").write_text("rubric\n", encoding="utf-8")
    (repo / "config" / "sim" / "agents" / "judge.md").write_text("judge\n", encoding="utf-8")
    (repo / "config" / "sim" / "agents" / "optimizer.md").write_text("optimize\n", encoding="utf-8")
    (repo / "config" / "prompts" / "ongoing_instruction_prompt_en.md").write_text("old instruction\n", encoding="utf-8")
    (repo / "config" / "prompts" / "prompt-of-subject-creation_en.md").write_text("old subject\n", encoding="utf-8")
    return repo


def _runner(matrix, out, config, repo):
    del matrix, config, repo
    out.mkdir(parents=True, exist_ok=True)
    (out / "passive_en.json").write_text(json.dumps(_trace("passive_en")), encoding="utf-8")


def _complete_factory(initiative: int):
    calls = {"n": 0, "backends": []}

    def complete(user: str, *, system: str, backend: str = "", **kwargs):
        del kwargs
        calls["n"] += 1
        calls["backends"].append(backend)
        from logoskittens.llm import ComparisonRecord

        record = ComparisonRecord(backend=backend, model="fake", latency_ms=0, prompt_tokens=1, completion_tokens=1)
        if system.startswith("optimize") or "CURRENT PROMPTS:" in user:
            return json.dumps(_proposal(f"Speak about the fjord in one sentence. {calls['n']}\n")), record
        return json.dumps(_verdict("passive_en", initiative=initiative)), record

    complete.calls = calls
    return complete


def test_run_reports_and_waits(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGOSKITTENS_SIM_ROOT", str(tmp_path / "sims"))
    repo = _layout(tmp_path)
    work = tmp_path / "work"
    complete = _complete_factory(3)
    state = run_cycle(repo, work, complete=complete, runner=_runner)
    assert state["status"] == "awaiting_approval"
    assert state["pending_proposal"]["proposal_id"] == "fjord-line"
    assert complete.calls["backends"] == ["grok", "grok"]
    assert "Waiting" in Path(state["report"]).read_text(encoding="utf-8")


def test_reject_does_not_create_a_new_proposal(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGOSKITTENS_SIM_ROOT", str(tmp_path / "sims"))
    repo = _layout(tmp_path)
    work = tmp_path / "work"
    run_cycle(repo, work, complete=_complete_factory(4), runner=_runner)
    state = reject_pending(repo, work)
    assert state["status"] == "rejected"
    assert state["pending_proposal"] is None
    with pytest.raises(ValueError, match="nothing is waiting"):
        reject_pending(repo, work)
    decision = next((tmp_path / "sims").rglob("decision.md"))
    assert "rejected by the user" in decision.read_text(encoding="utf-8")


def test_approval_copies_the_prompt_only_when_a_score_rises(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGOSKITTENS_SIM_ROOT", str(tmp_path / "sims"))
    repo = _layout(tmp_path)
    work = tmp_path / "work"
    run_cycle(repo, work, complete=_complete_factory(3), runner=_runner)
    approve_pending(repo, work, complete=_complete_factory(4), runner=_runner)
    text = (repo / "config" / "prompts" / "ongoing_instruction_prompt_en.md").read_text(encoding="utf-8")
    assert "fjord" in text
    decision = next(path for path in (tmp_path / "sims").rglob("decision.md") if "accepted" in path.read_text(encoding="utf-8"))
    assert "Speak about the fjord" in decision.read_text(encoding="utf-8")


def test_approval_of_a_drop_keeps_the_prompt(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGOSKITTENS_SIM_ROOT", str(tmp_path / "sims"))
    repo = _layout(tmp_path)
    work = tmp_path / "work"
    run_cycle(repo, work, complete=_complete_factory(3), runner=_runner)
    approve_pending(repo, work, complete=_complete_factory(2), runner=_runner)
    text = (repo / "config" / "prompts" / "ongoing_instruction_prompt_en.md").read_text(encoding="utf-8")
    assert text == "old instruction\n"


def test_a_comment_field_is_kept_as_the_critique_text(tmp_path, monkeypatch):
    monkeypatch.setenv("LOGOSKITTENS_SIM_ROOT", str(tmp_path / "sims"))
    repo = _layout(tmp_path)
    work = tmp_path / "work"
    complete = _complete_factory(3)

    def wrapped(user: str, *, system: str, **kwargs):
        raw, record = complete(user, system=system, **kwargs)
        payload = json.loads(raw)
        if "critiques" in payload:
            payload["critiques"] = [
                {"comment": "The line stayed on the fjord.", "evidence": "The fjord stayed bright."}
            ]
            raw = json.dumps(payload)
        return raw, record

    state = run_cycle(repo, work, complete=wrapped, runner=_runner)
    assert state["status"] == "awaiting_approval"
