"""InterviewerGame. Wren writes the questions. Ingrid asks deck lines. Wren judges what the contains-check missed."""

import json
from pathlib import Path

from logoskittens.games.host import load_game_prompt
from logoskittens.llm import LLMError
from logoskittens.persistence import Store
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete


SOURCE = (
    "Frokosten kom på et lite fat, slik de gjør det i Italia, og det var mat jeg kan svelge. "
    "Fluer lå i olje ved brødet, og jeg tok dem først. "
    "Maur var strødd over hornene i stedet for sukker, små og søte. "
    "Koppen sto der bare for varmen."
)

TARGETS = [
    ("Italia", "Hvor serverer de frokosten slik?", "Hvilket land nevner teksten ved frokosten?"),
    ("olje", "Hva lå fluene i?", "Fluene lå ved brødet. I hva da?"),
    ("sukker", "Hva var maurene strødd i stedet for?", "Hva er vanligvis søtt på hornene?"),
    ("varmen", "Hvorfor sto koppen der?", "Koppen ble ikke drukket. Hva var den for?"),
]

ROOT = Path(__file__).resolve().parents[1]


def _deck(rows=None) -> str:
    chosen = rows if rows is not None else TARGETS
    return json.dumps(
        {
            "targets": [
                {"id": f"t{index}", "phrase": phrase, "stem": stem, "retry_line": retry}
                for index, (phrase, stem, retry) in enumerate(chosen, start=1)
            ]
        }
    )


def _service(tmp_path) -> SessionService:
    service = SessionService(Store(tmp_path / "interview.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.store.save_logoscat_material(
        "logoscat-88",
        logoscat_user_id=1,
        workspace_session_id=88,
        language="nb",
        title="Edderkoppfrokost",
        text=SOURCE,
    )
    return service


class Wren:
    """Fake Wren: a deck at prepare, then the queued judge verdicts in order."""

    def __init__(self, verdicts=(), rows=None, error: Exception | None = None):
        self.verdicts = list(verdicts)
        self.rows = rows
        self.error = error
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, user: str, *, system: str = "", purpose: str = "", game_id: str = ""):
        del game_id
        self.calls.append((purpose, user, system))
        if purpose == "prepare":
            return _deck(self.rows)
        if self.error is not None:
            raise self.error
        hit = self.verdicts.pop(0)
        return json.dumps({"hit": hit, "why": "Kort grunn."})

    def purposes(self) -> list[str]:
        return [purpose for purpose, _user, _system in self.calls]


def _start(tmp_path, wren: Wren):
    service = _service(tmp_path)
    service.wren_fn = wren
    completes: list[str] = []

    def complete(user, *, system, **kwargs):
        completes.append(user)
        return fake_complete(user, system=system, **kwargs)

    service.complete_fn = complete
    session_id = service.select("user-local", "nb", "logoscat-88", "lucas", game_id="interviewer")
    return service, session_id, completes


def _turn(service, session_id, text):
    emitted: list[dict] = []
    service.perform_text(session_id, text, emitted.append)
    game = [item for item in emitted if item["type"] == "game"][0]
    return game, emitted


def _stored(service, session_id, speaker):
    rows = json.loads(service.store.get_session_row(session_id).sentences_json)
    return [item for item in rows if item["speaker"] == speaker]


def test_prompts_are_per_language_and_there_is_no_partner(tmp_path):
    games = ROOT / "config" / "prompts" / "games"
    for role in ("wren", "judge"):
        english = (games / f"interviewer_{role}_en.md").read_text(encoding="utf-8")
        norsk = (games / f"interviewer_{role}_nb.md").read_text(encoding="utf-8")
        assert english.strip() != norsk.strip()
        assert load_game_prompt("interviewer", role, "nb") == norsk
    assert not (games / "interviewer_partner_en.md").exists()
    assert not (games / "interviewer_partner_nb.md").exists()
    service = _service(tmp_path)
    assert "interviewer" in [item["id"] for item in service.catalog("user-local", "nb")["games"]]


def test_the_opening_is_the_first_question_in_the_learning_language(tmp_path):
    wren = Wren()
    service, session_id, completes = _start(tmp_path, wren)
    buddy = _stored(service, session_id, "buddy")
    assert [item["text"] for item in buddy] == ["Hvor serverer de frokosten slik?"]
    described = service.describe(session_id)
    assert described["game"]["phrase"] == ""
    assert described["game"]["source"] == SOURCE
    assert "What is missing" not in json.dumps(described)
    assert completes == []
    assert wren.purposes() == ["prepare"]


def test_a_one_word_right_answer_is_a_hit_without_wren(tmp_path):
    wren = Wren()
    service, session_id, completes = _start(tmp_path, wren)
    game, emitted = _turn(service, session_id, "Italia.")
    assert game["feedback"] == "match"
    assert game["matches"] == 1
    human = _stored(service, session_id, "human")[-1]
    assert human["verdict"] == "correct"
    assert _stored(service, session_id, "buddy")[-1]["text"] == "Hva lå fluene i?"
    assert [item["type"] for item in emitted] == ["heard", "game", "actor"]
    assert wren.purposes() == ["prepare"]
    assert completes == []


def test_a_reworded_answer_is_judged_by_wren_before_the_next_question(tmp_path):
    wren = Wren(verdicts=[True])
    service, session_id, _completes = _start(tmp_path, wren)
    game, _emitted = _turn(service, session_id, "I et italiensk hotell, tror jeg")
    assert game["feedback"] == "match"
    purpose, user, system = wren.calls[-1]
    assert purpose == "judge"
    assert "question: Hvor serverer de frokosten slik?" in user
    assert "expected: Italia" in user
    assert "answer: I et italiensk hotell, tror jeg" in user
    assert system == load_game_prompt("interviewer", "judge", "nb")
    assert _stored(service, session_id, "buddy")[-1]["text"] == "Hva lå fluene i?"


def test_a_miss_asks_the_retry_then_a_second_miss_shows_the_sentence(tmp_path):
    wren = Wren(verdicts=[False, False])
    service, session_id, _completes = _start(tmp_path, wren)
    game, _emitted = _turn(service, session_id, "Spania")
    assert game["feedback"] == "miss"
    assert game["misses"] == 1
    assert game["miss_note"]["explanation"] == "Not quite. Try again."
    assert "Italia" not in json.dumps(game["miss_note"])
    assert _stored(service, session_id, "buddy")[-1]["text"] == "Hvilket land nevner teksten ved frokosten?"
    # The retry is what Wren is told was asked.
    game, _emitted = _turn(service, session_id, "Frankrike")
    assert "question: Hvilket land nevner teksten ved frokosten?" in wren.calls[-1][1]
    assert game["feedback"] == "miss"
    assert game["misses"] == 2
    assert game["miss_note"]["explanation"].startswith("The passage says: Frokosten kom på et lite fat")
    deck = json.loads(service.store.get_session_row(session_id).deck_json)
    assert [target["status"] for target in deck["targets"][:2]] == ["missed", "active"]
    assert _stored(service, session_id, "buddy")[-1]["text"] == "Hva lå fluene i?"
    assert [item["text"] for item in _stored(service, session_id, "human")] == ["Spania", "Frankrike"]


def test_the_last_answer_speaks_the_closing_and_the_round_stays_over(tmp_path):
    wren = Wren()
    service, session_id, completes = _start(tmp_path, wren)
    for answer in ("Italia", "I olje", "Sukker!"):
        _turn(service, session_id, answer)
    game, _emitted = _turn(service, session_id, "For varmen.")
    assert game["finished"] is True
    buddy = [item["text"] for item in _stored(service, session_id, "buddy")]
    assert " ".join(buddy[-2:]) == "Det var siste spørsmål. Du klarte 4 av 4."
    game, emitted = _turn(service, session_id, "Hallo?")
    assert [item["type"] for item in emitted] == ["game"]
    assert game["finished"] is True
    assert wren.purposes() == ["prepare"]
    assert completes == []


def test_a_failed_judge_call_falls_back_to_the_local_check(tmp_path):
    wren = Wren(error=LLMError("timeout"))
    service, session_id, _completes = _start(tmp_path, wren)
    game, _emitted = _turn(service, session_id, "Et sted i sør")
    assert game["feedback"] == "miss"
    assert _stored(service, session_id, "buddy")[-1]["text"] == "Hvilket land nevner teksten ved frokosten?"


def test_a_question_that_names_its_answer_is_dropped_at_prepare(tmp_path):
    import pytest

    rows = [("Italia", "Var det i Italia?", "Hvilket land?")] + TARGETS[1:]
    service = _service(tmp_path)
    service.wren_fn = Wren(rows=rows)
    with pytest.raises(ValueError, match="grounded 3"):
        service.select("user-local", "nb", "logoscat-88", "lucas", game_id="interviewer")
