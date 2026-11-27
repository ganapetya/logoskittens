"""Player attach and one Speak turn. The talk socket stays /ws."""

import asyncio
import base64
import hmac

import pytest
from fastapi import WebSocketDisconnect
from fastapi.testclient import TestClient

from bot_link import BotLink
from bot_link.players import Player, load_players
from fakes import FakeAudio, fake_complete
from logoskittens.api import create_app
from logoskittens.persistence import Store
from logoskittens.session import SessionService

TOKEN = "m" * 32
OTHER = "n" * 32


@pytest.fixture(autouse=True)
def _no_live_recognizer(monkeypatch):
    monkeypatch.setattr(
        "logoskittens.api.switch_recognizer",
        lambda language: {"ok": True, "restarted": False, "language": language},
    )


def test_the_shipped_player_list_is_masha_and_savelij():
    players = load_players()
    assert [item.body_id for item in players] == ["masha", "savelij"]
    masha = players[0]
    assert masha.body_id == "masha"
    assert masha.display_name == "Masha"
    assert masha.role == "buddy"
    assert masha.actor == "buddy-one"
    assert masha.steerer == "bob"
    assert masha.enabled is True
    assert masha.token_env == "MASHA_ATTACH_TOKEN"
    teacher = players[1]
    assert teacher.display_name == "Savelij"
    assert teacher.role == "teacher"
    assert teacher.actor == "teacher-one"
    assert teacher.steerer == "rob"
    assert teacher.enabled is True
    assert teacher.token_env == "SAVELIJ_ATTACH_TOKEN"
    assert masha.gain("de") == 0.7
    assert masha.gain("en") == 1.0
    assert teacher.gain("de") == 1.0


def test_host_mode_off_refuses_attach(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    client = _client(tmp_path)
    assert client.get("/host-mode").json() == {"on": False}
    with client.websocket_connect("/players") as socket:
        socket.send_json({"type": "attach", "body_id": "masha", "token": TOKEN})
        refused = socket.receive_json()
    assert refused == {"type": "refused", "reason": "host_mode_off"}
    assert client.app.state.link.attached_ids() == []


def test_a_teacher_attaches_beside_one_buddy_and_a_second_teacher_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    monkeypatch.setenv("SAVELIJ_ATTACH_TOKEN", OTHER)
    monkeypatch.setenv("SAVELIJ_TWO_ATTACH_TOKEN", "t" * 32)
    client = _client(
        tmp_path,
        [
            _masha(),
            Player("savelij", "Savelij", "teacher", "teacher-one", "rob", True, "SAVELIJ_ATTACH_TOKEN"),
            Player("savelij-two", "Savelij Two", "teacher", "teacher-one", "rob", True, "SAVELIJ_TWO_ATTACH_TOKEN"),
        ],
    )
    _host_on(client)
    with client.websocket_connect("/players") as buddy:
        _attach(buddy, "masha", TOKEN)
        with client.websocket_connect("/players") as teacher:
            _attach(teacher, "savelij", OTHER)
            assert sorted(client.app.state.link.attached_ids()) == ["masha", "savelij"]
            with client.websocket_connect("/players") as second:
                second.send_json({"type": "attach", "body_id": "savelij-two", "token": "t" * 32})
                refused = second.receive_json()
            assert refused == {"type": "refused", "reason": "one_player"}
            assert sorted(client.app.state.link.attached_ids()) == ["masha", "savelij"]


def test_a_buddy_with_the_wrong_steerer_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    monkeypatch.setenv("OTHER_ATTACH_TOKEN", "o" * 32)
    client = _client(
        tmp_path,
        [
            _masha(),
            Player("other", "Other", "buddy", "buddy-one", "rob", True, "OTHER_ATTACH_TOKEN"),
        ],
    )
    _host_on(client)
    with client.websocket_connect("/players") as socket:
        socket.send_json({"type": "attach", "body_id": "other", "token": "o" * 32})
        steerer = socket.receive_json()
    with client.websocket_connect("/players") as socket:
        socket.send_json({"type": "attach", "body_id": "teacher", "token": TOKEN})
        unknown = socket.receive_json()
    assert steerer == {"type": "refused", "reason": "role_not_open"}
    assert unknown == {"type": "refused", "reason": "role_not_open"}
    assert client.app.state.link.attached_ids() == []


def test_a_second_buddy_is_refused_while_one_is_attached(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    monkeypatch.setenv("MINA_ATTACH_TOKEN", OTHER)
    client = _client(
        tmp_path,
        [
            _masha(),
            Player("mina", "Mina", "buddy", "buddy-one", "bob", True, "MINA_ATTACH_TOKEN"),
        ],
    )
    _host_on(client)
    with client.websocket_connect("/players") as first:
        _attach(first, "masha", TOKEN)
        with client.websocket_connect("/players") as second:
            second.send_json({"type": "attach", "body_id": "mina", "token": OTHER})
            refused = second.receive_json()
        assert refused == {"type": "refused", "reason": "one_player"}
        assert client.app.state.link.attached_ids() == ["masha"]
    assert client.app.state.link.attached_ids() == []


def test_a_short_token_is_refused_before_the_digest(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = hmac.compare_digest

    def spy(left, right):
        calls["n"] += 1
        return real(left, right)

    monkeypatch.setattr("bot_link.auth.hmac.compare_digest", spy)
    client = _client(tmp_path)
    _host_on(client)
    cases = [
        (None, TOKEN),
        ("", TOKEN),
        ("short", TOKEN),
        ("x" * 31, TOKEN),
        (TOKEN, ""),
        (TOKEN, "short"),
        (TOKEN, None),
    ]
    for presented, expected in cases:
        calls["n"] = 0
        if expected is None:
            monkeypatch.delenv("MASHA_ATTACH_TOKEN", raising=False)
        else:
            monkeypatch.setenv("MASHA_ATTACH_TOKEN", expected)
        payload = {"type": "attach", "body_id": "masha"}
        if presented is not None:
            payload["token"] = presented
        with client.websocket_connect("/players") as socket:
            socket.send_json(payload)
            refused = socket.receive_json()
        assert refused == {"type": "refused", "reason": "bad_token"}
        assert calls["n"] == 0
        assert client.app.state.link.attached_ids() == []


def test_a_wrong_long_token_is_compared_and_refused(tmp_path, monkeypatch):
    calls = {"n": 0}
    real = hmac.compare_digest

    def spy(left, right):
        calls["n"] += 1
        return real(left, right)

    monkeypatch.setattr("bot_link.auth.hmac.compare_digest", spy)
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    client = _client(tmp_path)
    _host_on(client)
    with client.websocket_connect("/players") as socket:
        socket.send_json({"type": "attach", "body_id": "masha", "token": "z" * 32})
        refused = socket.receive_json()
    assert refused == {"type": "refused", "reason": "bad_token"}
    assert calls["n"] == 1


def test_register_is_forgotten_when_the_socket_drops(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    client = _client(tmp_path)
    _host_on(client)
    with client.websocket_connect("/players") as socket:
        _attach(socket, "masha", TOKEN)
        _register(socket, "speaking_masha", [("curiosity", "lk_curiosity"), ("agreement", "lk_agreement")])
        stored = client.app.state.link.registration("masha")
    assert stored == {
        "speaking": {"action": "speaking_masha", "intent": "jaw"},
        "stances": [
            {"token": "curiosity", "action": "lk_curiosity", "intent": "head up"},
            {"token": "agreement", "action": "lk_agreement", "intent": "nod"},
        ],
    }
    assert client.app.state.link.registration("masha") is None
    assert client.app.state.link.attached_ids() == []


def test_leaving_host_mode_closes_the_socket_and_forgets_the_register(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    client = _client(tmp_path)
    _host_on(client)
    with client.websocket_connect("/players") as socket:
        _attach(socket, "masha", TOKEN)
        _register(socket, "speaking_masha", [("curiosity", "lk_curiosity")])
        assert client.app.state.link.registration("masha")["speaking"]["action"] == "speaking_masha"
        closed = client.post("/host-mode", json={"on": False})
        assert closed.json() == {"on": False}
        with pytest.raises(WebSocketDisconnect):
            while True:
                incoming = socket.receive_json()
                assert incoming["type"] == "config"
    assert client.app.state.link.registration("masha") is None
    assert client.app.state.link.attached_ids() == []


def test_delivery_sends_that_bodys_action_names_only(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    monkeypatch.setenv("MINA_ATTACH_TOKEN", OTHER)
    client = _client(
        tmp_path,
        [
            _masha(),
            Player("mina", "Mina", "buddy", "buddy-one", "bob", True, "MINA_ATTACH_TOKEN"),
        ],
    )
    _host_on(client)
    with client.websocket_connect("/players") as other:
        _attach(other, "mina", OTHER)
        _register(other, "speaking_mina", [("curiosity", "other_curiosity"), ("agreement", "other_agreement")])
    assert client.app.state.link.registration("mina") is None
    with client.websocket_connect("/players") as socket:
        _attach(socket, "masha", TOKEN)
        _register(
            socket,
            "speaking_masha",
            [("curiosity", "lk_curiosity"), ("agreement", "lk_agreement"), ("frustration", "lk_frustration")],
        )
        sent = client.app.state.link.deliver(
            role="buddy",
            pcm=b"pcm-bytes",
            tokens=["curiosity", "agreement", "not-a-token"],
        )
        message = socket.receive_json()
        if message["type"] == "config":
            message = socket.receive_json()
    assert sent == ["speaking_masha", "lk_curiosity", "lk_agreement"]
    assert message["type"] == "delivery"
    assert message["actions"] == ["speaking_masha", "lk_curiosity", "lk_agreement"]
    assert message["pcm"] == base64.b64encode(b"pcm-bytes").decode("ascii")
    blob = str(message)
    assert "other_curiosity" not in blob
    assert "other_agreement" not in blob
    assert "speaking_mina" not in blob
    assert "lk_frustration" not in blob


def test_one_voice_waits_until_the_other_has_finished(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    monkeypatch.setenv("SAVELIJ_ATTACH_TOKEN", OTHER)
    client = _client(
        tmp_path,
        [
            _masha(),
            Player("savelij", "Savelij", "teacher", "teacher-one", "rob", True, "SAVELIJ_ATTACH_TOKEN"),
        ],
    )
    _host_on(client)
    with client.websocket_connect("/players") as buddy:
        _attach(buddy, "masha", TOKEN)
        _register(buddy, "speaking_masha", [])
        with client.websocket_connect("/players") as teacher:
            _attach(teacher, "savelij", OTHER)
            _register(teacher, "speaking_savelij", [])
            assert buddy.receive_json()["type"] == "config"
            assert teacher.receive_json()["type"] == "config"
            client.app.state.link.deliver(role="buddy", pcm=b"\x00\x01" * 400, tokens=[])
            first = buddy.receive_json()
            assert first["type"] == "delivery"
            client.app.state.link.deliver(role="teacher", pcm=b"\x00\x02" * 40, tokens=[])
            link = client.app.state.link
            assert link._mouth_role == "buddy"
            assert len(link._mouth_queue) == 1
            buddy.send_json({"type": "played"})

            async def release() -> None:
                link._mouth_free("buddy")
                await asyncio.sleep(0)

            asyncio.run_coroutine_threadsafe(release(), link._loop).result(timeout=2)
            held = teacher.receive_json()
            assert held["type"] == "delivery"
            assert link._mouth_role == "teacher"
            link.deliver(role="buddy", pcm=b"\x00\x03" * 20, tokens=[])
            assert link._mouth_role == "teacher"
            assert len(link._mouth_queue) == 1


def test_the_console_shows_a_refusal_and_a_registered_player(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    client = _client(tmp_path)
    assert client.get("/console").json() == {"host_mode": False, "refusal": "", "players": []}
    with client.websocket_connect("/players") as socket:
        socket.send_json({"type": "attach", "body_id": "masha", "token": TOKEN})
        assert socket.receive_json()["reason"] == "host_mode_off"
    refused = client.get("/console").json()
    assert refused["host_mode"] is False
    assert refused["refusal"] == "host_mode_off"
    assert refused["players"] == []
    _host_on(client)
    assert client.get("/console").json()["refusal"] == ""
    with client.websocket_connect("/players") as socket:
        _attach(socket, "masha", TOKEN)
        _register(socket, "speaking_masha", [("curiosity", "lk_curiosity"), ("agreement", "lk_agreement")])
        listed = client.get("/console").json()
    assert listed["host_mode"] is True
    assert listed["players"] == [
        {
            "body_id": "masha",
            "display_name": "Masha",
            "role": "buddy",
            "steerer": "bob",
            "speaking": "speaking_masha",
            "stances": ["curiosity", "agreement"],
            "ready": True,
            "reason": "",
        }
    ]


def test_a_text_turn_with_no_player_still_finishes(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    calls: list[dict] = []
    real = BotLink.deliver

    def spy(self, **kwargs):
        calls.append(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(BotLink, "deliver", spy)
    client = _client(tmp_path)
    with client.websocket_connect("/ws") as socket:
        socket.send_json({"type": "start"})
        hello = socket.receive_json()
        assert hello["type"] == "session"
        socket.send_json({"type": "transcript", "text": "The fjords were quiet."})
        heard = socket.receive_json()
        actor = socket.receive_json()
    assert heard["type"] == "heard"
    assert heard["transcript"] == "The fjords were quiet."
    assert actor["type"] == "actor"
    assert actor["final"] is True
    assert actor["play_on_page"] is True
    assert calls == []
    assert client.app.state.link.attached_ids() == []


def test_speak_press_and_release_is_one_audio_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    client = _client(tmp_path)
    _host_on(client)
    with client.websocket_connect("/players") as player:
        _attach(player, "masha", TOKEN)
        _register(player, "speaking_masha", [("curiosity", "lk_curiosity")])
        config = player.receive_json()
        assert config["listen_mode"] == "speak"
        assert config["listen"] is False
        player.send_json({"type": "status", "ready": True, "reason": ""})
        with client.websocket_connect("/ws") as page:
            page.send_json({"type": "start"})
            hello = page.receive_json()
            assert hello["type"] == "session"
            page.send_json({"type": "speak", "down": True})
            assert player.receive_json() == {"type": "speak", "down": True}
            page.send_json({"type": "speak", "down": False})
            assert player.receive_json() == {"type": "speak", "down": False}
            player.send_json({"type": "audio", "data": base64.b64encode(b"RIFFwav").decode("ascii"), "mime": "audio/wav"})
            heard = page.receive_json()
            actor = page.receive_json()
            pose = player.receive_json()
            delivery = player.receive_json()
    assert pose == {"type": "delivery", "actions": ["lk_curiosity"], "pcm": "", "language": ""}
    assert heard["type"] == "heard"
    assert heard["transcript"] == "The fjords were beautiful."
    assert actor["type"] == "actor"
    assert actor["final"] is True
    assert delivery["type"] == "delivery"
    assert delivery["actions"] == ["speaking_masha"]
    assert base64.b64decode(delivery["pcm"]) == b"\x00\x01" * 220


def _client(tmp_path, players: list[Player] | None = None) -> TestClient:
    service = SessionService(
        Store(tmp_path / "players.db"),
        FakeAudio(),  # type: ignore[arg-type]
        fake_complete,
    )
    link = BotLink(players) if players is not None else None
    return TestClient(create_app(service, link))


def _masha() -> Player:
    return Player("masha", "Masha", "buddy", "buddy-one", "bob", True, "MASHA_ATTACH_TOKEN")


def _host_on(client: TestClient) -> None:
    response = client.post("/host-mode", json={"on": True})
    assert response.status_code == 200
    assert response.json() == {"on": True}


def _attach(socket, body_id: str, token: str) -> None:
    socket.send_json({"type": "attach", "body_id": body_id, "token": token})
    attached = socket.receive_json()
    assert attached["type"] == "attached"
    assert attached["body_id"] == body_id


def _register(socket, speaking: str, stances: list[tuple[str, str]]) -> None:
    socket.send_json(
        {
            "type": "register",
            "speaking": {"action": speaking, "intent": "jaw"},
            "stances": [
                {"token": token, "action": action, "intent": "head up" if token == "curiosity" else "nod"}
                for token, action in stances
            ],
        }
    )
    assert socket.receive_json() == {"type": "registered"}


def test_a_cue_sends_only_the_pose_and_holds_no_mouth(tmp_path, monkeypatch):
    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    client = _client(tmp_path, [_masha()])
    _host_on(client)
    with client.websocket_connect("/players") as socket:
        _attach(socket, "masha", TOKEN)
        _register(socket, "speaking_masha", [("curiosity", "lk_curiosity")])
        link = client.app.state.link
        assert link.cue(role="buddy", tokens=["curiosity"]) == ["lk_curiosity"]
        message = socket.receive_json()
        if message["type"] == "config":
            message = socket.receive_json()
        assert message == {"type": "delivery", "actions": ["lk_curiosity"], "pcm": "", "language": ""}
        assert link.cue(role="buddy", tokens=["not-a-token"]) == []
        assert link.cue(role="teacher", tokens=["curiosity"]) == []
        link.deliver(role="buddy", pcm=b"\x00\x01" * 400, tokens=[])
        socket.receive_json()
        assert link.cue(role="buddy", tokens=["curiosity"]) == []


def test_german_is_quieter_on_masha_only(tmp_path, monkeypatch):
    import array

    monkeypatch.setenv("MASHA_ATTACH_TOKEN", TOKEN)
    quiet = Player("masha", "Masha", "buddy", "buddy-one", "bob", True, "MASHA_ATTACH_TOKEN", volume=(("de", 0.7),))
    client = _client(tmp_path, [quiet])
    _host_on(client)
    loud = array.array("h", [1000, -1000, 32000, -32000, 0]).tobytes()
    with client.websocket_connect("/players") as socket:
        _attach(socket, "masha", TOKEN)
        _register(socket, "speaking_masha", [("curiosity", "lk_curiosity")])
        link = client.app.state.link
        link.deliver(role="buddy", pcm=loud, tokens=[], language="de")
        german = socket.receive_json()
        if german["type"] == "config":
            german = socket.receive_json()
        link._mouth_free("buddy")
        link.deliver(role="buddy", pcm=loud, tokens=[], language="en")
        english = socket.receive_json()
    played = array.array("h")
    played.frombytes(base64.b64decode(german["pcm"]))
    assert list(played) == [700, -700, 22400, -22400, 0]
    assert base64.b64decode(english["pcm"]) == loud


def test_scale_pcm_clips_and_a_bad_volume_is_refused(tmp_path):
    import array
    import json

    from bot_link.link import scale_pcm

    louder = array.array("h")
    louder.frombytes(scale_pcm(array.array("h", [30000, -30000]).tobytes(), 2.0))
    assert list(louder) == [32767, -32768]
    bad = tmp_path / "players.json"
    row = {"body_id": "x", "display_name": "X", "role": "buddy", "actor": "buddy-one", "steerer": "bob", "token_env": "X"}
    for volume in ({"de": 0}, {"de": 3}, {"de": "loud"}, ["de"]):
        bad.write_text(json.dumps({"players": [{**row, "volume": volume}]}), encoding="utf-8")
        with pytest.raises(ValueError, match="volume"):
            load_players(bad)
