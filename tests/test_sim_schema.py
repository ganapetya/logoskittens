import pytest

from logoskittens.sim.schema import apply_proposal, check_proposal, compare_verdicts, parse_verdict


def _verdict(scenario: str, **scores):
    base = {
        "subject_fidelity": 3,
        "responsiveness": 3,
        "initiative": 3,
        "naturalness": 3,
        "subject_card": 3,
    }
    base.update(scores)
    return {
        "scenario_id": scenario,
        "dialogue_id": scenario,
        "scores": base,
        "flags": {
            "corrected_human": False,
            "recited_human": False,
            "ended_conversation": False,
            "language_match": True,
        },
        "critiques": [{"dimension": "naturalness", "turn_index": 0, "text": "Short.", "evidence": "The fjord was quiet."}],
        "summary": "Held.",
    }


def test_a_score_of_six_is_rejected():
    payload = _verdict("passive_en", initiative=6)
    with pytest.raises(ValueError):
        parse_verdict(payload)


def test_compare_accepts_a_rise_and_rejects_a_drop_or_a_correction():
    before = [_verdict("passive_en")]
    risen = [_verdict("passive_en", initiative=4)]
    assert compare_verdicts(before, risen)["accept"] is True
    fallen = [_verdict("passive_en", naturalness=2)]
    assert compare_verdicts(before, fallen)["accept"] is False
    corrected = _verdict("passive_en", initiative=5)
    corrected["flags"]["corrected_human"] = True
    compared = compare_verdicts(before, [corrected])
    assert compared["accept"] is False
    assert "passive_en.flags" in compared["regressed"]


def test_apply_writes_one_prompt_and_refuses_any_other_file(tmp_path):
    prompt = tmp_path / "config" / "prompts" / "ongoing_instruction_prompt_en.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("old\n", encoding="utf-8")
    proposal = {
        "proposal_id": "prompt-1",
        "hypothesis": "A shorter instruction.",
        "kind": "config",
        "mutations": [
            {
                "path": "config/prompts/ongoing_instruction_prompt_en.md",
                "key": "body",
                "value": "Speak one sentence about the fjord.\n",
            }
        ],
    }
    written = apply_proposal(tmp_path, proposal)
    assert written == ["config/prompts/ongoing_instruction_prompt_en.md"]
    assert "fjord" in prompt.read_text(encoding="utf-8")
    refused = {
        **proposal,
        "mutations": [{"path": "cognitive-hub/src/logoskittens/conversation.py", "key": "body", "value": "x"}],
    }
    with pytest.raises(ValueError, match="allowlist"):
        check_proposal(refused)
    for path in (
        "config/prompts/bob_en.md",
        "config/bob.json",
        "config/prompts/rob_en.md",
        "config/prompts/rob_nb.md",
        "config/prompts/rob_pedantic_en.md",
        "config/prompts/rob_pedantic_nb.md",
        "config/rob.json",
    ):
        with pytest.raises(ValueError, match="allowlist"):
            check_proposal(
                {
                    **proposal,
                    "mutations": [{"path": path, "key": "body", "value": "x"}],
                }
            )
    with pytest.raises(ValueError, match="person"):
        check_proposal({**proposal, "kind": "code", "needs_human": True, "diff": "diff"})
