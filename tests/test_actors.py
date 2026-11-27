import json
from pathlib import Path

import pytest

from logoskittens.actors import ActorLoadError, load_actors


def test_mvp_actors_load():
    actors = load_actors()
    assert set(actors) == {"buddy-one", "buddy-two", "teacher-one"}
    buddy = actors["buddy-one"]
    other = actors["buddy-two"]
    teacher = actors["teacher-one"]
    assert buddy.active is True
    assert other.active is False
    assert teacher.active is True
    assert buddy.role == "buddy"
    assert other.role == "buddy"
    assert teacher.role == "teacher"
    assert teacher.embodiment.voice_profile.voice_id == "en_US-ryan-medium"
    assert buddy.embodiment.voice_profile.voice_id == "en_US-lessac-medium"
    assert buddy.embodiment.medium == "virtual_screen"
    assert other.embodiment.medium == "virtual_screen"


def test_missing_role_is_rejected(tmp_path: Path):
    payload = json.loads(
        Path("config/actors/buddy-one.json").read_text()
    )
    del payload["role"]
    (tmp_path / "broken.json").write_text(json.dumps(payload))
    with pytest.raises(ActorLoadError):
        load_actors(tmp_path)


def test_missing_voice_is_rejected(tmp_path: Path):
    payload = json.loads(
        Path("config/actors/buddy-two.json").read_text()
    )
    del payload["embodiment"]["voice_profile"]
    (tmp_path / "broken.json").write_text(json.dumps(payload))
    with pytest.raises(ActorLoadError):
        load_actors(tmp_path)


def test_missing_primitives_is_rejected(tmp_path: Path):
    payload = json.loads(
        Path("config/actors/buddy-one.json").read_text()
    )
    payload["embodiment"]["supported_primitives"] = []
    (tmp_path / "broken.json").write_text(json.dumps(payload))
    with pytest.raises(ActorLoadError):
        load_actors(tmp_path)
