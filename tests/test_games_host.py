"""Stage A: the plugin host. Free speech stays on its own graph."""

import base64
import inspect
import json
from typing import TypedDict

from fastapi.testclient import TestClient
from langgraph.graph import END, StateGraph
from sqlmodel import select

from logoskittens.api import create_app
from logoskittens.games.host import (
    apply_local,
    check_exit,
    contains_phrase,
    fold,
    game_message,
    load_game_prompt,
    prompt_opens,
    same_phrase,
    wren_result_applies,
)
from logoskittens.games.models import CursorState, GameCapabilities, GameDeck, GameManifest, TurnExit
from logoskittens.games.probe import ProbePlugin
from logoskittens.games.registry import get_plugin, register
from logoskittens.games.wren import WrenSkipped, call as wren_call
from logoskittens.persistence import SessionRow, Store
from logoskittens.scenes import SceneNotBuilt, require_material_mode, require_scene
from logoskittens.session import SessionService
from logoskittens.sim.schema import mutation_allowed
from logoskittens.wire import decode

from fakes import FakeAudio, fake_complete

import pytest


class _Prep(TypedDict, total=False):
    rejection: str
    language_id: str
    material_id: str
    raw_text: str
    wren_system: str
    partner_system: str
    game_id: str
    deck: dict
    state: dict


class _Turn(TypedDict, total=False):
    heard: str
    deck: dict
    state: dict
    exit: dict


def _manifest(caps: GameCapabilities | None = None, **kwargs) -> GameManifest:
    return GameManifest(
        id=kwargs.get("id", "scripted"),
        phase=1,
        listed=False,
        titles={"en": "ScriptedGame", "nb": "ScriptedGame"},
        min_targets=kwargs.get("min_targets", 1),
        max_targets=kwargs.get("max_targets", 4),
        max_attempts=kwargs.get("max_attempts", 0),
        reveal_phrase=kwargs.get("reveal_phrase", False),
        phrase_grounding=kwargs.get("phrase_grounding", "unchecked"),
        opening=kwargs.get("opening", "none"),
        capabilities=caps or GameCapabilities(),
    )


def _target(phrase: str = "fjord", **kwargs) -> dict:
    return {
        "id": kwargs.get("id", "t1"),
        "phrase": phrase,
        "instruction": kwargs.get("instruction", "Say this."),
        "hint": kwargs.get("hint", ""),
        "stem": kwargs.get("stem", ""),
        "retry_line": kwargs.get("retry_line", ""),
        "prompt_to_partner": kwargs.get("prompt_to_partner", ""),
        "banned": kwargs.get("banned", []),
        "status": "pending",
    }


class Scripted:
    def __init__(self, manifest: GameManifest, targets: list[dict], decision: TurnExit | None = None):
        self.id = manifest.id
        self.manifest = manifest
        self.targets = targets
        self.decision = decision or TurnExit(source="none")
        self.prepare_calls: list[str] = []
        self.calls_wren = False
        self.explode = False
        self.wren_hits: list = []

    def load_manifest(self) -> GameManifest:
        return self.manifest

    def state_type(self):
        return CursorState

    def build_prepare_graph(self, wren):
        plugin = self

        def prepare(state: _Prep) -> dict:
            plugin.prepare_calls.append(state.get("rejection") or "")
            if plugin.calls_wren:
                wren("deck", system=state.get("wren_system") or "")
            return {
                "deck": {"targets": plugin.targets},
                "state": {"state_version": 1, "active_id": "t1"},
            }

        graph = StateGraph(_Prep)
        graph.add_node("prepare", prepare)
        graph.set_entry_point("prepare")
        graph.add_edge("prepare", END)
        return graph.compile()

    def build_turn_graph(self):
        plugin = self

        def decide(state: _Turn) -> dict:
            if plugin.explode:
                raise RuntimeError("stop the turn")
            return {"exit": plugin.decision.model_dump()}

        graph = StateGraph(_Turn)
        graph.add_node("decide", decide)
        graph.set_entry_point("decide")
        graph.add_edge("decide", END)
        return graph.compile()

    def apply_wren(self, deck: GameDeck, state, payload: dict):
        self.wren_hits.append(payload)
        targets = []
        hit = payload.get("hit")
        for target in deck.targets:
            if target.status == "active" and hit is True:
                target = target.model_copy(update={"status": "hit"})
            elif target.status == "active" and hit is False:
                target = target.model_copy(update={"status": "missed"})
            targets.append(target)
        if not any(item.status == "active" for item in targets):
            for index, item in enumerate(targets):
                if item.status == "pending":
                    targets[index] = item.model_copy(update={"status": "active"})
                    break
        return deck.model_copy(update={"targets": targets}), state, str(payload.get("why") or "")

    def finish(self, deck, state, wren):
        del wren
        return deck, state, "noted"


@pytest.fixture(autouse=True)
def _no_live_recognizer(monkeypatch):
    monkeypatch.setattr(
        "logoskittens.api.switch_recognizer",
        lambda language: {"ok": True, "restarted": False, "language": language},
    )
    monkeypatch.setattr(
        "logoskittens.games.host.load_game_prompt",
        lambda game_id, role, language_id: f"{game_id} {role} {language_id}",
    )


def _service(tmp_path, complete=None) -> SessionService:
    return SessionService(
        Store(tmp_path / "games.db"),
        FakeAudio(),  # type: ignore[arg-type]
        complete or fake_complete,
    )


def _rows(service: SessionService) -> int:
    with service.store.open() as db:
        return len(db.exec(select(SessionRow)).all())


def test_fold_keeps_norwegian_letters():
    assert fold("Kjølig!") == fold("kjølig")
    assert "ø" in fold("ø")
    assert same_phrase("Kjølig!", "kjølig")
    assert same_phrase("Jeg er sliten.", "jeg er sliten")
    assert contains_phrase("the quiet fjord", "quiet")
    assert not same_phrase("", "fjord")


def test_probe_is_unlisted_and_instruction_only():
    probe = get_plugin("probe")
    assert probe is not None
    manifest = probe.load_manifest()
    assert manifest.listed is False
    assert manifest.opening == "none"
    assert manifest.capabilities.instruction is True
    assert manifest.capabilities.model_dump()["exact_match"] is False
    assert list(inspect.signature(ProbePlugin.build_turn_graph).parameters) == ["self"]
    assert "complete" not in inspect.signature(ProbePlugin.build_prepare_graph).parameters
    assert "wren" in inspect.signature(ProbePlugin.build_prepare_graph).parameters


def test_every_turn_flag_is_refused_until_the_manifest_allows_it():
    bare = _manifest()
    flagged = {
        "hint": TurnExit(show_hint=True),
        "exact_match": TurnExit(local_check="exact"),
        "contains_match": TurnExit(local_check="contains"),
        "buzzer": TurnExit(local_check="banned"),
        "hidden_steer": TurnExit(prompt_suffix="ask"),
        "deck_line": TurnExit(source="deck"),
        "async_score": TurnExit(schedule_wren=True),
        "remote_gate": TurnExit(remote_gate=True),
        "withhold": TurnExit(withhold=True),
        "mimic": TurnExit(mimic="curiosity"),
        "end_score": TurnExit(finished=True),
    }
    for name, decision in flagged.items():
        with pytest.raises(ValueError, match=f"game flag {name}"):
            check_exit(decision, bare)
        allowed = GameCapabilities(**{name: True})
        check_exit(decision, _manifest(allowed))
    deck = GameDeck(
        game_id="scripted",
        language="en",
        material_id="m",
        targets=[{"id": "t1", "phrase": "fjord", "instruction": "Say it.", "status": "active"}],
    )
    hidden = game_message(
        session_id="s",
        manifest=bare,
        deck=deck,
        decision=TurnExit(),
        qa=False,
        steer="secret",
        finished=False,
        score={"kind": "hits", "hit": 1, "total": 2},
    )
    assert hidden["instruction"] == ""
    assert hidden["quest"] == []
    assert hidden["score"] is None
    assert hidden["steer"] == ""
    shown = game_message(
        session_id="s",
        manifest=_manifest(GameCapabilities(instruction=True, quest=True, end_score=True)),
        deck=deck,
        decision=TurnExit(),
        qa=True,
        steer="secret",
        finished=False,
        score={"kind": "hits", "hit": 1, "total": 2},
    )
    assert shown["instruction"] == "Say it."
    assert shown["quest"] == [{"id": "t1", "text": "fjord", "status": "active"}]
    assert shown["score"]["hit"] == 1
    assert shown["steer"] == "secret"


def test_free_speech_does_not_call_wren_and_still_summarizes(tmp_path):
    service = _service(tmp_path)

    def explode(*_args, **_kwargs):
        raise AssertionError("wren")

    service.wren_fn = explode
    session_id = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter")
    described = service.describe(session_id)
    assert described["game_id"] == ""
    assert described["game"] is None
    assert "Norway" in described["theme"] or "fjord" in described["theme"].lower()
    assert all(item["id"] != "probe" for item in described["games"])
    assert all(item["id"] != "probe" for item in service.catalog("user-local", "en")["games"])


def test_probe_stores_a_deck_and_speaks_no_line(tmp_path, monkeypatch):
    service = _service(tmp_path)
    prepared = []

    def no_prepare(*_args, **_kwargs):
        prepared.append(1)
        raise AssertionError("run_prepare")

    monkeypatch.setattr("logoskittens.session.run_prepare", no_prepare)
    monkeypatch.setattr(
        "logoskittens.games.host.solution_for",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("solution_for")),
    )
    scheduled = []
    monkeypatch.setattr(service, "_schedule_bob", lambda *_args, **_kwargs: scheduled.append("bob"))
    monkeypatch.setattr(service, "_schedule_rob", lambda *_args, **_kwargs: scheduled.append("rob"))
    session_id = service.select(
        "user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="probe"
    )
    row = service.store.get_session_row(session_id)
    assert row.topic_id == "talking_game"
    assert row.task_id == "talking_game"
    assert row.subject_json == ""
    deck = json.loads(row.deck_json)
    assert deck["targets"][0]["status"] == "active"
    assert json.loads(row.game_state_json)["state_version"] == 1
    emitted: list[dict] = []
    service.perform_text(session_id, "hello there", emitted.append)
    assert [item["type"] for item in emitted] == ["heard", "game"]
    assert emitted[1]["instruction"] == "Probe."
    assert emitted[1]["phrase"] == ""
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    assert stored[0]["speaker"] == "human"
    assert stored[0]["text"] == "hello there"
    assert not any(item["speaker"] == "buddy" for item in stored)
    assert prepared == []
    assert scheduled == []
    service.ensure(session_id)
    service._ensure_subject(session_id)
    assert prepared == []


def test_an_empty_deck_errors_on_the_next_turn_without_summarizing(tmp_path, monkeypatch):
    service = _service(tmp_path)
    session_id = service.select(
        "user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="probe"
    )
    service.store.save_game(session_id, "", "", "")

    def no_prepare(*_args, **_kwargs):
        raise AssertionError("run_prepare")

    monkeypatch.setattr("logoskittens.session.run_prepare", no_prepare)
    with pytest.raises(ValueError, match="no deck"):
        service.perform_text(session_id, "hello", lambda _payload: None)


def test_a_withheld_turn_keeps_the_human_line_and_emits_no_actor(tmp_path):
    service = _service(tmp_path)
    plugin = Scripted(_manifest(GameCapabilities(withhold=True)), [_target()])
    register(plugin)
    session_id = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="scripted")
    plugin.decision = TurnExit(withhold=True, source="partner")
    emitted: list[dict] = []
    service.perform_text(session_id, "The fjord was quiet.", emitted.append)
    assert [item["type"] for item in emitted] == ["heard", "game"]
    assert emitted[1]["withheld"] is True
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    assert stored[-1]["speaker"] == "human"
    assert stored[-1]["text"] == "The fjord was quiet."


def test_the_human_line_is_stored_before_the_turn_graph(tmp_path):
    service = _service(tmp_path)
    plugin = Scripted(_manifest(), [_target()])
    plugin.explode = True
    register(plugin)
    session_id = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="scripted")
    with pytest.raises(RuntimeError, match="stop the turn"):
        service.perform_text(session_id, "Still heard.", lambda _payload: None)
    stored = json.loads(service.store.get_session_row(session_id).sentences_json)
    assert stored[-1]["text"] == "Still heard."


def test_apply_local_is_the_status_writer(tmp_path):
    service = _service(tmp_path)
    caps = GameCapabilities(exact_match=True, contains_match=True)
    plugin = Scripted(
        _manifest(caps, max_attempts=2),
        [_target("kjølig"), _target("fjord", id="t2", hint="kjø")],
    )
    register(plugin)
    session_id = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="scripted")
    plugin.decision = TurnExit(source="partner", local_check="exact")
    service.perform_text(session_id, "Kjølig!", lambda _payload: None)
    deck = GameDeck.model_validate_json(service.store.get_session_row(session_id).deck_json)
    assert deck.targets[0].status == "hit"
    assert deck.targets[1].status == "active"
    plugin.decision = TurnExit(source="partner", local_check="contains", match="active")
    service.perform_text(session_id, "nothing like it", lambda _payload: None)
    state = CursorState.model_validate_json(service.store.get_session_row(session_id).game_state_json)
    assert state.pending_hint == "kjø"
    assert state.attempts["t2"] == 1
    service.perform_text(session_id, "still nothing", lambda _payload: None)
    deck = GameDeck.model_validate_json(service.store.get_session_row(session_id).deck_json)
    assert deck.targets[1].status == "missed"


def test_remote_gate_runs_after_chrome_and_before_the_partner(tmp_path):
    events: list[str] = []

    def complete(user: str, *, system: str, **kwargs):
        events.append("complete")
        return fake_complete(user, system=system, **kwargs)

    service = _service(tmp_path, complete)
    plugin = Scripted(_manifest(GameCapabilities(remote_gate=True)), [_target(), _target("slope", id="t2")])
    plugin.decision = TurnExit(source="partner", remote_gate=True, wren_user="score this")
    register(plugin)

    def wren(user, *, system="", purpose="", game_id=""):
        events.append(f"wren:{purpose}")
        return json.dumps({"hit": True, "why": "said it", "target_id": "t1"})

    service.wren_fn = wren
    session_id = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="scripted")
    events.clear()
    emitted: list[dict] = []

    def collect(payload: dict) -> None:
        emitted.append(payload)
        events.append(payload["type"])

    service.perform_text(session_id, "The fjord was quiet.", collect)
    assert events == ["heard", "game", "wren:gate", "game", "complete", "actor"]
    assert emitted[1]["type"] == "game"
    assert emitted[2]["feedback"] == "match"
    plugin.decision = TurnExit(source="partner", remote_gate=True)
    events.clear()

    def miss(user, *, system="", purpose="", game_id=""):
        events.append(f"wren:{purpose}")
        return json.dumps({"hit": False, "why": "no"})

    service.wren_fn = miss
    service.perform_text(session_id, "Another line.", collect)
    assert "complete" not in events
    assert "actor" not in events
    assert events[:4] == ["heard", "game", "wren:gate", "game"]


def test_async_score_starts_after_the_actor(tmp_path):
    events: list[str] = []

    def complete(user: str, *, system: str, **kwargs):
        events.append("complete")
        return fake_complete(user, system=system, **kwargs)

    service = _service(tmp_path, complete)
    service._launch = lambda fn: fn()
    plugin = Scripted(_manifest(GameCapabilities(async_score=True)), [_target()])
    plugin.decision = TurnExit(source="partner", schedule_wren=True, wren_user="score")
    register(plugin)

    def wren(user, *, system="", purpose="", game_id=""):
        events.append(f"wren:{purpose}")
        return json.dumps({"hit": True, "why": "yes"})

    service.wren_fn = wren
    session_id = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="scripted")
    events.clear()
    emitted: list[dict] = []

    def collect(payload: dict) -> None:
        emitted.append(payload)
        events.append(payload["type"])

    service.perform_text(session_id, "The fjord was quiet.", collect)
    assert events.index("actor") < events.index("wren:score")
    assert any(item.get("feedback") == "match" for item in emitted)
    deck = json.loads(service.store.get_session_row(session_id).deck_json)
    assert deck["targets"][0]["status"] == "hit"


def test_a_short_or_long_deck_does_not_write_a_session(tmp_path):
    service = _service(tmp_path)
    plugin = Scripted(
        _manifest(min_targets=1, max_targets=2),
        [_target("one"), _target("two", id="t2"), _target("three", id="t3")],
    )
    plugin.calls_wren = False
    register(plugin)
    before = _rows(service)
    with pytest.raises(ValueError, match="grounded 3"):
        service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="scripted")
    assert _rows(service) == before
    assert plugin.prepare_calls == ["", "grounded 3 targets, need 1 to 2"]


def test_a_disabled_wren_refuses_prepare(tmp_path):
    service = _service(tmp_path)
    plugin = Scripted(_manifest(), [_target()])
    plugin.calls_wren = True
    register(plugin)
    before = _rows(service)
    with pytest.raises(ValueError, match="Wren is not available"):
        service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="scripted")
    assert _rows(service) == before


def test_logoscat_material_still_loads_and_reserved_scenes_stay_rejected(tmp_path, monkeypatch):
    service = _service(tmp_path)
    monkeypatch.setattr(
        "logoskittens.session.run_prepare",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("run_prepare")),
    )
    service.store.save_logoscat_material(
        "logoscat-42",
        logoscat_user_id=1,
        workspace_session_id=42,
        language="en",
        title="Imported",
        text="The fjord was quiet.",
    )
    session_id = service.select("user-local", "en", "logoscat-42", "peter", game_id="probe")
    row = service.store.get_session_row(session_id)
    assert row.material_id == "logoscat-42"
    assert row.topic_id == "talking_game"
    with pytest.raises(SceneNotBuilt):
        require_scene("joint_hunting")
    with pytest.raises(SceneNotBuilt):
        service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", scene_id="joint_hunting")
    with pytest.raises(ValueError, match="not implemented"):
        require_material_mode("attached")
    assert mutation_allowed("config/prompts/games/probe_partner_en.md", "body") is False


def test_opening_actor_follows_the_session_message(tmp_path):
    service = _service(tmp_path)
    plugin = Scripted(_manifest(opening="partner"), [_target(instruction="Ask one question.")])
    register(plugin)
    seen: list[dict] = []

    def spy(pcm, tokens=None, language="", role="buddy"):
        seen.append({"pcm": pcm, "tokens": list(tokens or []), "role": role})

    app = create_app(service)
    app.state.service.deliver_pcm = spy
    client = TestClient(app)
    with client.websocket_connect("/ws") as socket:
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
                "game_id": "scripted",
            }
        )
        hello = socket.receive_json()
        actor = socket.receive_json()
    assert hello["type"] == "session"
    assert actor["type"] == "actor"
    assert actor["session_id"] == hello["session_id"]
    assert actor["game"] is True
    assert actor["steer"] == ""
    assert actor["play_on_page"] is True
    spoken = decode(base64.b64decode(actor["solutions"][0]))
    assert spoken.speech.precomputed_audio_pcm
    assert seen == []
    assert ProbePlugin().load_manifest().opening == "none"


def test_botnet_opening_goes_to_the_buddy_body(tmp_path):
    service = _service(tmp_path)
    plugin = Scripted(
        _manifest(GameCapabilities(mimic=True), opening="partner"),
        [_target()],
    )
    plugin.decision = TurnExit(source="partner", mimic="curiosity")
    register(plugin)
    seen: list[dict] = []

    def spy(pcm, tokens=None, language="", role="buddy"):
        seen.append({"pcm": pcm, "tokens": list(tokens or []), "role": role})

    app = create_app(service)
    app.state.service.deliver_pcm = spy
    client = TestClient(app)
    assert client.post("/host-mode", json={"on": True}).json() == {"on": True}
    with client.websocket_connect("/ws") as socket:
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
                "game_id": "scripted",
            }
        )
        hello = socket.receive_json()
        actor = socket.receive_json()
        socket.send_json({"type": "transcript", "text": "The fjord was quiet."})
        socket.receive_json()
        turn_game = socket.receive_json()
        turn_actor = socket.receive_json()
        plugin.decision = TurnExit(source="partner", mimic="dance")
        socket.send_json({"type": "transcript", "text": "Again."})
        socket.receive_json()
        socket.receive_json()
        again = socket.receive_json()
    assert hello["type"] == "session"
    assert actor["type"] == "actor"
    assert actor["session_id"] == hello["session_id"]
    opening = decode(base64.b64decode(actor["solutions"][0]))
    assert opening.speech.precomputed_audio_pcm == b""
    assert seen[0]["role"] == "buddy"
    assert seen[0]["pcm"]
    assert turn_game["type"] == "game"
    assert turn_actor["type"] == "actor"
    assert seen[-2]["tokens"] == ["curiosity"]
    assert again["type"] == "actor"
    assert "dance" not in seen[-1]["tokens"]


def test_a_buzzer_sends_no_pcm(tmp_path):
    service = _service(tmp_path)
    plugin = Scripted(
        _manifest(GameCapabilities(buzzer=True)),
        [_target(banned=["quiet"])],
    )
    plugin.decision = TurnExit(source="partner", local_check="banned")
    register(plugin)
    seen: list[dict] = []
    service.deliver_pcm = lambda pcm, tokens=None, language="", role="buddy": seen.append(tokens)
    service.botnet = lambda: True
    session_id = service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="scripted")
    emitted: list[dict] = []
    service.perform_text(session_id, "The quiet fjord.", emitted.append)
    assert [item["type"] for item in emitted] == ["heard", "game"]
    assert emitted[1]["buzzer"] is True
    assert seen == []


def test_missing_prompt_names_the_file_and_the_socket_stays_open(tmp_path, monkeypatch):
    monkeypatch.setattr("logoskittens.games.host.load_game_prompt", load_game_prompt)
    plugin = Scripted(_manifest(id="ghost"), [_target()])
    register(plugin)
    service = _service(tmp_path)
    client = TestClient(create_app(service))
    prompt_opens.clear()
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        socket.receive_json()
        prompt_opens.clear()
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "nb",
                "material_id": "norway_vacation_tunnels_fjords",
                "personality_id": "peter",
                "game_id": "ghost",
            }
        )
        failed = socket.receive_json()
        assert failed["type"] == "error"
        assert failed["message"] == "ghost_wren_nb.md"
        assert any(path.endswith("ghost_wren_nb.md") for path in prompt_opens)
        assert not any(path.endswith("ghost_wren_en.md") for path in prompt_opens)
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
                "game_id": "",
            }
        )
        hello = socket.receive_json()
    assert hello["type"] == "session"
    assert hello["game_id"] == ""


def test_a_bad_game_id_keeps_the_socket_and_the_next_line_still_replies(tmp_path):
    service = _service(tmp_path)
    client = TestClient(create_app(service))
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        socket.receive_json()
        socket.send_json(
            {
                "type": "select",
                "user_id": "user-local",
                "language_id": "en",
                "material_id": "norway_vacation_tunnels_fjords",
                "game_id": "no-such-game",
            }
        )
        failed = socket.receive_json()
        socket.send_json({"type": "transcript", "text": "The tunnels were long."})
        heard = socket.receive_json()
        actor = socket.receive_json()
    assert failed["type"] == "error"
    assert "not on this hub" in failed["message"]
    assert heard["type"] == "heard"
    assert actor["type"] == "actor"


def test_game_end_on_free_speech_is_an_error_and_probe_does_not_call_wren(tmp_path):
    service = _service(tmp_path)

    def explode(*_args, **_kwargs):
        raise AssertionError("wren")

    service.wren_fn = explode
    client = TestClient(create_app(service))
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        hello = socket.receive_json()
        socket.send_json({"type": "game-end"})
        failed = socket.receive_json()
        socket.send_json({"type": "transcript", "text": "yes"})
        heard = socket.receive_json()
    assert failed == {"type": "error", "message": "No game is open."}
    assert heard["type"] == "heard"
    session_id = service.select(
        "user-local", "en", "norway_vacation_tunnels_fjords", "peter", game_id="probe"
    )
    emitted: list[dict] = []
    service.finish_game(session_id, emitted.append)
    assert emitted[0]["type"] == "game"
    assert emitted[0]["instruction"] == "Probe."
    assert hello["session_id"]


def test_wren_settings_skip_without_a_key(monkeypatch):
    monkeypatch.setenv("WREN_ENABLED", "on")
    monkeypatch.setenv("WREN_API_KEY", "")
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(WrenSkipped):
        wren_call(game_id="probe", purpose="prepare", system="sys", user="user")


def test_apply_local_any_marks_every_phrase():
    deck = GameDeck(
        game_id="scripted",
        language="en",
        material_id="m",
        targets=[
            {"id": "t1", "phrase": "fjord", "status": "active"},
            {"id": "t2", "phrase": "ferry", "status": "pending"},
        ],
    )
    state = CursorState(active_id="t1")
    updated, _state, decision = apply_local(
        deck,
        state,
        "The ferry crossed the fjord.",
        TurnExit(local_check="contains", match="any"),
        _manifest(GameCapabilities(contains_match=True)),
    )
    assert [item.status for item in updated.targets] == ["hit", "hit"]
    assert decision.feedback == "match"
