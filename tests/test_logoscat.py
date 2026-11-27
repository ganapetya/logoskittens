"""Connecting LogosCat with an app token, and a workspace session used as raw material."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from fakes import FakeAudio, fake_complete
from logoskittens.api import create_app
from logoskittens.logoscat import LogosCatClient, logoscat_base_url, looks_like_token, plain_sentence
from logoskittens.persistence import Store
from logoskittens.session import SessionService

TOKEN = "lkc_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_mode_picks_the_logoscat_server(monkeypatch):
    monkeypatch.delenv("MODE", raising=False)
    monkeypatch.delenv("LOGOSKITTENS_IN_DOCKER", raising=False)
    assert logoscat_base_url() == "http://localhost:8080"
    monkeypatch.setenv("MODE", "prod")
    assert logoscat_base_url() == "https://logoscat.com"
    monkeypatch.setenv("MODE", "dev")
    monkeypatch.setenv("LOGOSKITTENS_IN_DOCKER", "1")
    assert logoscat_base_url() == "http://host.docker.internal:8080"
    assert LogosCatClient().tokens_url() == "http://localhost:8080/?settings=connected-apps"
    monkeypatch.setenv("MODE", "prod")
    assert LogosCatClient().tokens_url() == "https://logoscat.com/?settings=connected-apps"


def test_plain_sentence_drops_tags():
    assert plain_sentence("<p>A fly.</p>") == "A fly."
    assert plain_sentence("  The fjord.  ") == "The fjord."


class _Actors:
    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.calls: list[tuple[str, str, dict | None]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode() or "null") if request.content else None
        self.calls.append((request.method, request.url.path, body))
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        if request.url.path == "/api/app-token/whoami":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "user": {"id": 4, "username": "ada"},
                    "app": "logoskittens",
                    "scopes": ["sessions:read", "settings:read"],
                    "expiresAt": "2027-02-24T00:00:00Z",
                },
            )
        if request.url.path == "/api/workspace-session/all":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "sessions": [
                        {
                            "id": 9,
                            "name": "West coast",
                            "timestampStarted": "2026-01-02T00:00:00Z",
                            "itemCount": 2,
                        }
                    ],
                },
            )
        if request.url.path == "/api/history/recap-by-session":
            page = int(request.url.params["page"])
            payload = self.pages[page]
            return httpx.Response(200, json=payload)
        return httpx.Response(404, json={"success": False, "error": "missing"})


def _page(has_more: bool, items: list[dict]) -> dict:
    return {"success": True, "data": {"pages": [{"pageId": 1, "items": items}], "hasMore": has_more}}


def _text(language: str, text: str, kind: str = "text_input") -> dict:
    return {"itemType": kind, "language": language, "textValue": text}


def _app(tmp_path, actors: _Actors):
    service = SessionService(Store(tmp_path / "logoscat.db"), FakeAudio(), fake_complete)
    app = create_app(service)
    app.state.logoscat = LogosCatClient("http://logoscat.test", transport=httpx.MockTransport(actors.handler))
    return TestClient(app), service


def test_connect_checks_the_token_with_whoami_and_returns_the_user(tmp_path):
    actors = _Actors([])
    client, _service = _app(tmp_path, actors)
    connected = client.post("/logoscat/connect", json={"token": TOKEN})
    assert connected.status_code == 200
    assert connected.json() == {"success": True, "user": {"id": 4, "username": "ada"}, "expiresAt": "2027-02-24T00:00:00Z"}
    assert [path for _m, path, _b in actors.calls] == ["/api/app-token/whoami"]
    again = client.post("/logoscat/validate", headers=AUTH)
    assert again.status_code == 200
    assert len(actors.calls) == 1


def test_a_string_that_is_not_an_app_token_is_refused_without_a_call(tmp_path):
    actors = _Actors([])
    client, _service = _app(tmp_path, actors)
    for value in ["", "s3cret-pass", "eyJhbGciOiJIUzI1NiJ9.e30.sig", "lkc_short", "lkc_" + "a" * 100]:
        refused = client.post("/logoscat/connect", json={"token": value})
        assert refused.status_code == 400
        assert looks_like_token(value) is False
    assert actors.calls == []


def test_password_login_logout_and_altcha_routes_are_gone(tmp_path):
    client, _service = _app(tmp_path, _Actors([]))
    assert client.post("/logoscat/login", json={"usernameOrEmail": "ada", "password": "x", "altchaPayload": "y"}).status_code in {404, 405}
    assert client.post("/logoscat/logout", json={"sessionId": "sid"}).status_code in {404, 405}
    assert client.get("/logoscat/altcha/challenge").status_code in {404, 405}


def test_info_names_the_connected_apps_page_of_this_mode(tmp_path):
    client, _service = _app(tmp_path, _Actors([]))
    assert client.get("/logoscat/info").json()["tokens_url"] == "http://logoscat.test/?settings=connected-apps"


def test_a_revoked_token_is_401_and_a_stored_session_stays(tmp_path):
    actors = _Actors([])
    client, service = _app(tmp_path, actors)
    service.store.save_logoscat_material(
        "logoscat-3",
        logoscat_user_id=4,
        workspace_session_id=3,
        language="en",
        title="Kept",
        text="The road was narrow.",
    )

    def refuse(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"success": False, "error": "Invalid or expired token"})

    client.app.state.logoscat = LogosCatClient("http://logoscat.test", transport=httpx.MockTransport(refuse))
    denied = client.post("/logoscat/validate", headers=AUTH)
    assert denied.status_code == 401
    assert "expired or was revoked" in denied.json()["error"]
    connect = client.post("/logoscat/connect", json={"token": TOKEN})
    assert connect.status_code == 401
    assert service.store.get_logoscat_material("logoscat-3").title == "Kept"


def test_a_429_blocks_that_endpoint_until_retry_after_and_is_not_retried(tmp_path):
    calls: list[str] = []
    now = [1000.0]

    def busy(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(429, headers={"Retry-After": "30"}, json={"success": False, "error": "Too many requests"})

    client, _service = _app(tmp_path, _Actors([]))
    client.app.state.logoscat = LogosCatClient(
        "http://logoscat.test", transport=httpx.MockTransport(busy), clock=lambda: now[0]
    )
    first = client.get("/logoscat/workspace-sessions", headers=AUTH)
    assert first.status_code == 429
    assert "busy" in first.json()["error"] and "30 s" in first.json()["error"]
    now[0] += 10
    second = client.get("/logoscat/workspace-sessions", headers=AUTH)
    assert second.status_code == 429
    assert "20 s" in second.json()["error"]
    assert calls == ["/api/workspace-session/all"]
    now[0] += 21
    client.get("/logoscat/workspace-sessions", headers=AUTH)
    assert calls == ["/api/workspace-session/all", "/api/workspace-session/all"]


def test_language_settings_are_read_once_in_ten_minutes(tmp_path):
    calls: list[str] = []
    now = [0.0]

    def settings(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"success": True, "settings": {"inputLanguagesSet": ["en"], "outputLanguagesSet": ["de"]}})

    client, _service = _app(tmp_path, _Actors([]))
    client.app.state.logoscat = LogosCatClient(
        "http://logoscat.test", transport=httpx.MockTransport(settings), clock=lambda: now[0]
    )
    for _ in range(3):
        assert client.get("/logoscat/language-settings", headers=AUTH).json()["origin"] == "logoscat"
    now[0] += 599
    client.get("/logoscat/language-settings", headers=AUTH)
    assert len(calls) == 1
    now[0] += 2
    client.get("/logoscat/language-settings", headers=AUTH)
    assert len(calls) == 2


def test_an_import_reads_at_most_fifty_recap_pages(tmp_path):
    actors = _Actors([_page(True, [_text("en", f"Line number {n}.")]) for n in range(60)])
    client, service = _app(tmp_path, actors)
    imported = client.post(
        "/logoscat/import", headers=AUTH, json={"workspace_session_id": 4, "language_id": "en", "name": "Many"}
    )
    assert imported.status_code == 200
    assert imported.json()["notice"] == "The rest of this session was left out."
    assert len([p for _m, p, _b in actors.calls if p == "/api/history/recap-by-session"]) == 50
    assert service.store.get_logoscat_material("logoscat-4").text.count("\n") == 49


def test_a_429_partway_through_an_import_keeps_the_pages_read(tmp_path):
    actors = _Actors([_page(True, [_text("en", f"Line number {n}.")]) for n in range(3)])
    handler = actors.handler

    def busy_after_two(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/history/recap-by-session" and int(request.url.params["page"]) == 2:
            return httpx.Response(429, headers={"Retry-After": "40"}, json={"success": False})
        return handler(request)

    client, service = _app(tmp_path, actors)
    client.app.state.logoscat = LogosCatClient("http://logoscat.test", transport=httpx.MockTransport(busy_after_two))
    imported = client.post(
        "/logoscat/import", headers=AUTH, json={"workspace_session_id": 4, "language_id": "en", "name": "Busy"}
    )
    assert imported.status_code == 200
    assert imported.json()["notice"] == "The rest of this session was left out."
    assert service.store.get_logoscat_material("logoscat-4").text == "Line number 0.\nLine number 1."


def test_import_keeps_source_lines_and_select_starts_that_subject(tmp_path):
    actors = _Actors(
        [
            _page(
                True,
                [
                    _text("no", "<p>Fergen krysset fjorden.</p>"),
                    _text("no", "The tunnel was long.", "text_output"),
                    _text("no", "Fergen krysset fjorden."),
                    {"itemType": "mp3_file_name", "language": "no", "textValue": "clip.mp3"},
                ],
            ),
            _page(False, [_text("no", "Lyset kom etter tunnelen.")]),
        ]
    )
    client, service = _app(tmp_path, actors)
    listed = client.get("/logoscat/workspace-sessions", headers=AUTH)
    assert listed.json()["sessions"][0]["name"] == "West coast"
    imported = client.post(
        "/logoscat/import",
        headers=AUTH,
        json={"workspace_session_id": 9, "language_id": "en", "name": "West coast"},
    )
    assert imported.status_code == 200
    body = imported.json()
    assert body["material_id"] == "logoscat-9"
    assert body["language_id"] == "nb"
    assert body["notice"] == ""
    stored = service.store.get_logoscat_material("logoscat-9")
    assert stored.text == "Fergen krysset fjorden.\nLyset kom etter tunnelen."
    assert stored.logoscat_user_id == 4
    session_id = service.select("user-local", "nb", "logoscat-9", "peter")
    described = service.describe(session_id)
    assert described["material_id"] == "logoscat-9"
    titles = {item["id"]: item for item in described["materials"]}
    assert titles["logoscat-9"]["title"] == "West coast"
    assert titles["logoscat-9"]["origin"] == "logoscat"
    assert "text" not in titles["logoscat-9"]
    assert titles["norway_vacation_tunnels_fjords"]["origin"] == "file"
    assert service.materials.load("nb", "norway_vacation_tunnels_fjords").origin == "file"
    again = client.post(
        "/logoscat/import",
        headers=AUTH,
        json={"workspace_session_id": 9, "language_id": "nb", "name": "West coast"},
    )
    assert again.status_code == 200
    assert service.store.get_logoscat_material("logoscat-9").text.startswith("Fergen")


def test_import_refuses_an_empty_session_and_a_language_we_do_not_speak(tmp_path):
    empty = _Actors([_page(False, [_text("en", "hello", "text_output")])])
    client, service = _app(tmp_path, empty)
    refused = client.post(
        "/logoscat/import",
        headers=AUTH,
        json={"workspace_session_id": 2, "language_id": "en", "name": "Empty"},
    )
    assert refused.status_code == 400
    assert "no source sentences" in refused.json()["error"]
    assert service.store.get_logoscat_material("logoscat-2") is None

    german = _Actors([_page(False, [_text("de", "Der Hafen ist still.")])])
    client.app.state.logoscat = LogosCatClient("http://logoscat.test", transport=httpx.MockTransport(german.handler))
    blocked = client.post(
        "/logoscat/import",
        headers=AUTH,
        json={"workspace_session_id": 5, "language_id": "en", "name": "Hafen"},
    )
    assert blocked.status_code == 400
    assert "cannot talk" in blocked.json()["error"]


def test_a_mixed_session_keeps_the_language_already_open(tmp_path):
    actors = _Actors(
        [
            _page(
                False,
                [
                    _text("en", "The ferry crossed."),
                    _text("nb", "Fergen krysset."),
                ],
            )
        ]
    )
    client, service = _app(tmp_path, actors)
    imported = client.post(
        "/logoscat/import",
        headers=AUTH,
        json={"workspace_session_id": 8, "language_id": "en", "name": "Both"},
    )
    assert imported.status_code == 200
    assert imported.json()["language_id"] == "en"
    assert service.store.get_logoscat_material("logoscat-8").text == "The ferry crossed."


def test_a_long_session_says_the_rest_was_left_out(tmp_path):
    actors = _Actors([_page(False, [_text("en", "First line."), _text("en", "Second line.")])])
    client, service = _app(tmp_path, actors)
    client.app.state.logoscat.import_session = lambda *args, **kwargs: client.app.state.logoscat.__class__.import_session(
        client.app.state.logoscat,
        *args,
        cap=1,
        **kwargs,
    )
    imported = client.post(
        "/logoscat/import",
        headers=AUTH,
        json={"workspace_session_id": 6, "language_id": "en", "name": "Long"},
    )
    assert imported.status_code == 200
    assert imported.json()["notice"] == "The rest of this session was left out."
    assert service.store.get_logoscat_material("logoscat-6").text == "First line."


def test_logoscat_down_does_not_hide_the_file_material(tmp_path, monkeypatch):
    def down(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    service = SessionService(Store(tmp_path / "down.db"), FakeAudio(), fake_complete)
    app = create_app(service)
    app.state.logoscat = LogosCatClient("http://logoscat.test", transport=httpx.MockTransport(down))
    client = TestClient(app)
    connect = client.post("/logoscat/connect", json={"token": TOKEN})
    assert connect.status_code == 502
    catalog = client.get("/catalog").json()
    assert "norway_vacation_tunnels_fjords" in {item["id"] for item in catalog["materials"]}
    monkeypatch.delenv("MODE", raising=False)
    assert logoscat_base_url().startswith("http://")
    with pytest.raises(ValueError):
        service.materials.load("en", "logoscat-1")
