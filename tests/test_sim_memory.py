"""Lab memory is a separate SQLite file from the lesson store."""

from logoskittens.persistence import Store
from logoskittens.sim.memory import LabMemory
from logoskittens.sim.schema import parse_verdict


def _verdict():
    return {
        "scenario_id": "passive_en",
        "dialogue_id": "run-mem",
        "scores": {
            "subject_fidelity": 4,
            "responsiveness": 3,
            "initiative": 2,
            "naturalness": 3,
            "subject_card": 3,
        },
        "flags": {
            "corrected_human": False,
            "recited_human": False,
            "ended_conversation": False,
            "language_match": True,
        },
        "critiques": [
            {
                "dimension": "initiative",
                "turn_index": 0,
                "text": "The repair quoted the mistake.",
                "evidence": "The fjord stayed bright.",
            }
        ],
        "summary": "The talk held.",
    }


def test_a_verdict_can_be_queried_by_persona(tmp_path):
    lab = LabMemory(tmp_path / "memory.db")
    lab.add_verdict(_verdict(), persona="shy", cefr="A2")
    lab.add_note(
        note_id="note-other",
        kind="critique",
        body="A rambler note.",
        persona="rambler",
        cefr="A2",
    )
    found = lab.query(persona="shy", cefr="A2", limit=8)
    assert found
    assert all(item["persona"] == "shy" for item in found)
    assert any(item["kind"] == "critique" and "repair" in item["body"] for item in found)
    reopened = LabMemory(tmp_path / "memory.db")
    assert reopened.query(persona="shy", cefr="A2", limit=8)


def test_lab_tables_are_not_created_in_the_lesson_database(tmp_path):
    LabMemory(tmp_path / "memory.db")
    lesson = Store(tmp_path / "lesson.db")
    with lesson.engine.connect() as conn:
        names = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "noterow" not in names
    assert "sessionrow" in names
    parse_verdict(_verdict())
