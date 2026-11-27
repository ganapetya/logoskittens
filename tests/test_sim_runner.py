"""The matrix replays frozen human lines. The pseudo-human is a separate command."""

from logoskittens.sim.runner import load_matrix, run_dialogue, talk

from fakes import fake_complete


def test_the_runner_does_not_construct_audio():
    trace = run_dialogue(
        scenario_id="passive_en",
        language="en",
        material_id="norway_vacation_tunnels_fjords",
        lines=["yes", "okay"],
        complete=fake_complete,
    )
    assert trace["turns"][0]["actor_id"] == "buddy-one"
    assert "pcm" not in trace["turns"][0]
    assert trace["transcript"][0] == "human: yes"
    assert any(line.startswith("buddy:") for line in trace["transcript"])


def test_the_matrix_lists_the_three_english_scripts():
    rows = load_matrix(__import__("pathlib").Path("config/sim/matrix.json"))
    assert [row["id"] for row in rows] == ["passive_en", "curious_en", "wanderer_en"]
    assert {row["language"] for row in rows} == {"en"}


def test_talk_runs_the_pseudo_human_and_the_buddy():
    calls = []

    def complete(user: str, *, system: str, **kwargs):
        calls.append(system[:24])
        return fake_complete(user, system=system, **kwargs)

    trace = talk(
        language="en",
        material_id="norway_vacation_tunnels_fjords",
        persona="answers in one or two words",
        turns=2,
        complete=complete,
    )
    assert len(trace["turns"]) == 2
    assert trace["turns"][0]["human"]
    assert trace["turns"][0]["buddy"]
    assert len(calls) >= 3
