"""Registries added so a later language, scene, or expert is files, not a fork."""

import base64
import importlib.util
from pathlib import Path

from logoskittens.content import language_gaps
from logoskittens.expert import ExpertSkipped, expert_prompt
from logoskittens.mimics import keep_tokens
from logoskittens.scenes import SceneNotBuilt, require_material_mode, require_scene
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete
from logoskittens.persistence import Store

import pytest


def test_live_packs_name_every_prompt_they_call():
    assert language_gaps("en") == []
    assert language_gaps("nb") == []
    assert language_gaps("uk") == []
    assert language_gaps("de") == []


def test_a_missing_expert_prompt_is_a_gap_and_a_skip(tmp_path, monkeypatch):
    assert any(item.endswith("rob_it.md") for item in language_gaps("it")) or "languages/it.json" in language_gaps("it")
    with pytest.raises(ExpertSkipped, match="rob_it"):
        expert_prompt("rob", "it")


def test_joint_hunting_is_reserved_and_attached_does_not_switch_the_files(tmp_path):
    with pytest.raises(SceneNotBuilt, match="not built"):
        require_scene("joint_hunting")
    assert require_scene("") == "free_speech"
    with pytest.raises(ValueError, match="not implemented"):
        require_material_mode("attached")
    assert require_material_mode("") == "detached"
    service = SessionService(Store(tmp_path / "scene.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    with pytest.raises(SceneNotBuilt):
        service.select("user-local", "en", "norway_vacation_tunnels_fjords", "peter", scene_id="joint_hunting")
    session_id = service.start()
    described = service.describe(session_id)
    assert described["scene_id"] == "free_speech"
    assert described["material_mode"] == "detached"


def test_unknown_mimic_tokens_are_dropped():
    assert keep_tokens(["frustration", "dance", "frustration", ""]) == ["frustration"]


def test_a_due_expert_does_not_run_before_the_actor_line(tmp_path, monkeypatch):
    monkeypatch.setenv("BOB_ENABLED", "on")
    monkeypatch.setenv("BOB_EVERY", "1")
    monkeypatch.setenv("ROB_ENABLED", "off")
    monkeypatch.setenv("XAI_API_KEY", "xai-from-env")
    emitted: list[dict] = []

    def suggestion(user: str, *, language_id: str = "en"):
        del user, language_id
        assert any(item["type"] == "actor" for item in emitted)
        return "Ask about the tunnel.", "A nearby subject.", ""

    monkeypatch.setattr("logoskittens.session.suggest", suggestion)
    service = SessionService(Store(tmp_path / "expert.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service._launch = lambda fn: fn()
    session_id = service.start()
    service.perform_text(session_id, "The water was cold.", emitted.append)
    kinds = [item["type"] for item in emitted]
    assert kinds.index("actor") < kinds.index("bob")


def test_a_body_registers_its_actions_and_reports_when_the_line_finishes():
    path = Path("bodies/lk_body/lk_body/loop.py")
    spec = importlib.util.spec_from_file_location("lk_body_loop", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    body = module.BodyLoop(
        "savelij",
        speaking="speaking_savelij",
        stances=[{"token": "curiosity", "action": "curiosity", "intent": "ask"}],
    )
    assert body.register()["speaking"]["action"] == "speaking_savelij"
    heard: list[bytes] = []
    note = body.on_delivery(
        {"type": "delivery", "pcm": base64.b64encode(b"pcm").decode()},
        heard.append,
    )
    assert note == {"type": "played"}
    assert heard == [b"pcm"]
