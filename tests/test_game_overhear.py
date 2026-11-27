"""OverhearGame (H8). Savelij and the buddy talk first, each through their own role. Then she asks the user."""

import base64
import json
from pathlib import Path

from logoskittens.games.host import listed_games
from logoskittens.wire import decode

from phase2 import Wren, deck_of, prompts_differ, start, stored, turn

DECK = {
    "targets": [
        {
            "phrase": "lange tunneler",
            "forms": ["lang tunnel"],
            "lead": [
                {"speaker": "teacher", "line": "Veien gikk gjennom lange tunneler."},
                {"speaker": "buddy", "line": "Ja, det husker jeg godt."},
            ],
            "stem": "Hva gikk veien gjennom?",
            "retry_line": "Hva sa Savelij om veien?",
        },
        {
            "phrase": "over en fjord",
            "lead": [
                {"speaker": "buddy", "line": "Hvor stoppet vi om morgenen?"},
                {"speaker": "teacher", "line": "Dere stoppet over en fjord."},
            ],
            "stem": "Hvor stoppet de om morgenen?",
            "retry_line": "Hør en gang til. Hvor stoppet de?",
        },
        {
            "phrase": "helt utslitt",
            "lead": [
                {"speaker": "teacher", "line": "Om kvelden var de helt utslitt."},
                {"speaker": "buddy", "line": "Ikke rart, etter den turen."},
            ],
            "stem": "Hvordan hadde de det om kvelden?",
            "retry_line": "Hvordan var de om kvelden?",
        },
        {
            # The answer is never said aloud: dropped.
            "phrase": "den kalde luften",
            "lead": [
                {"speaker": "teacher", "line": "Husker du været?"},
                {"speaker": "buddy", "line": "Ja, det var kaldt."},
            ],
            "stem": "Hva husker hun fortsatt?",
            "retry_line": "Hva husket hun?",
        },
    ]
}


class Desk:
    """The Botnet switch and the bodies. Records each role a line was sent to, with its tokens."""

    def __init__(self, on: bool):
        self.on = on
        self.sent: list[tuple[str, list[str]]] = []

    def deliver(self, pcm, tokens=None, language="", role="buddy"):
        del pcm, language
        self.sent.append((role, list(tokens or [])))


def _actors(emitted):
    return [item for item in emitted if item["type"] == "actor"]


def _start(tmp_path, desk: Desk, verdicts=None):
    wren = Wren(DECK, verdicts=verdicts)
    service, session_id = start(tmp_path, "overhear", wren)
    service.deliver_pcm = desk.deliver
    service.botnet = lambda: desk.on
    return service, session_id, wren


def test_overhear_is_listed_with_its_prompts_and_needs_the_teacher_voice():
    prompts_differ("overhear", roles=("wren", "judge"))
    rows = {item["id"]: item for item in listed_games("nb")}
    assert rows["overhear"]["title"] == "OverhørtGame"
    assert "Two voices" in rows["overhear"]["tags"]


def test_switch_on_sends_the_lead_to_each_role_in_order_and_the_page_plays_nothing(tmp_path):
    desk = Desk(on=True)
    service, session_id, _wren = _start(tmp_path, desk)
    # Only targets whose answer is heard in the lead are kept.
    assert [target["phrase"] for target in deck_of(service, session_id)["targets"]] == [
        "lange tunneler",
        "over en fjord",
        "helt utslitt",
    ]
    emitted: list[dict] = []
    service.voice_opening(session_id, emitted.append)
    assert [role for role, _tokens in desk.sent] == ["teacher", "buddy", "buddy"]
    actors = _actors(emitted)
    assert [item["play_on_page"] for item in actors] == [False, False, False]
    assert actors[0]["speaker"] == "Savelij"
    teacher = decode(base64.b64decode(actors[0]["solutions"][0]))
    assert teacher.actor_id == "teacher-one" and teacher.speech.precomputed_audio_pcm == b""
    assert all(decode(base64.b64decode(item["solutions"][0])).actor_id == "buddy-one" for item in actors[1:])
    # The log holds the lead before the opening question.
    log = [(item["speaker"], item["text"]) for item in json.loads(service.store.get_session_row(session_id).sentences_json)]
    assert log == [
        ("teacher", "Veien gikk gjennom lange tunneler."),
        ("buddy", "Ja, det husker jeg godt."),
        ("buddy", "Hva gikk veien gjennom?"),
    ]
    # A hit: the next target's lead, then its stem, in order.
    desk.sent.clear()
    game, actors = turn(service, session_id, "Lange tunneler.")
    assert game["feedback"] == "match"
    assert [role for role, _tokens in desk.sent] == ["buddy", "teacher", "buddy"]
    assert [item["text"] for item in stored(service, session_id, "teacher")] == [
        "Veien gikk gjennom lange tunneler.",
        "Dere stoppet over en fjord.",
    ]


def test_switch_off_plays_the_lead_on_the_page_in_order(tmp_path):
    desk = Desk(on=False)
    service, session_id, _wren = _start(tmp_path, desk)
    emitted: list[dict] = []
    service.voice_opening(session_id, emitted.append)
    assert desk.sent == []
    actors = _actors(emitted)
    assert [item["play_on_page"] for item in actors] == [True, True, True]
    texts = [decode(base64.b64decode(item["solutions"][0])).speech.text for item in actors]
    assert texts == ["Veien gikk gjennom lange tunneler.", "Ja, det husker jeg godt.", "Hva gikk veien gjennom?"]
    assert all(decode(base64.b64decode(item["solutions"][0])).speech.precomputed_audio_pcm for item in actors)


def test_a_retry_replays_the_lead_line_with_the_answer_and_no_robot_runs(tmp_path, monkeypatch):
    desk = Desk(on=True)
    service, session_id, wren = _start(tmp_path, desk, verdicts=[False])

    def refuse(*_args, **_kwargs):
        raise AssertionError("a game session does not schedule Bob or Rob")

    monkeypatch.setattr(service, "_schedule_rob", refuse)
    monkeypatch.setattr(service, "_schedule_bob", refuse)
    service.voice_opening(session_id, lambda _payload: None)
    desk.sent.clear()
    game, actors = turn(service, session_id, "Mørke huler.")
    assert game["feedback"] == "miss" and len(wren.judged()) == 1
    texts = [decode(base64.b64decode(item["solutions"][0])).speech.text for item in actors]
    assert texts == ["Veien gikk gjennom lange tunneler.", "Hva sa Savelij om veien?"]
    assert [role for role, _tokens in desk.sent] == ["teacher", "buddy"]
    assert all(
        decode(base64.b64decode(item["solutions"][0])).actor_id in {"buddy-one", "teacher-one"} for item in actors
    )
    # buddy-two stays inactive and the role table is the shipped one.
    assert service.actors["buddy-two"].active is False
    roles = json.loads((Path(__file__).resolve().parents[1] / "config" / "roles.json").read_text(encoding="utf-8"))
    assert roles == {"open": [{"role": "buddy", "steerer": "bob"}, {"role": "teacher", "steerer": "rob"}]}
