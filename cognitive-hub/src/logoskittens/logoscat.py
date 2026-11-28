"""LogosCat account and workspace sessions.

The page talks only to this hub. The hub calls LogosCat. ``MODE`` in the
environment picks the server. A missing server leaves the file materials
running.

LogosKittens never sees a LogosCat password. The user creates a personal,
read-only ``lkc_`` token on LogosCat (Settings, Connected apps) and pastes it
here. LogosCat rate limits that token, so this client is polite: one call at a
time, short caches, and no call to an endpoint before its ``Retry-After``.
"""

from __future__ import annotations

import html
import json
import os
import re
import threading
import time
from hashlib import sha256
from html.parser import HTMLParser

import httpx
from pydantic import BaseModel

from logoskittens.persistence import Store


class ConnectIn(BaseModel):
    token: str = ""


class ImportIn(BaseModel):
    workspace_session_id: int = 0
    language_id: str = "en"
    name: str = ""

SOURCE_LINE_CAP = 500
# LogosCat allows 60 recap pages a minute per token. One import reads at most 50.
_MAX_PAGES = 50
TOKEN_PREFIX = "lkc_"
TOKEN_MIN, TOKEN_MAX = 40, 80
TOKENS_PATH = "/?settings=connected-apps"
SETTINGS_TTL_S = 600.0
SESSIONS_TTL_S = 60.0
_LIVE = {"en": "en", "nb": "nb", "uk": "uk", "de": "de", "he": "he"}
_NORWEGIAN = {"no", "nb", "nob", "nb-no", "no-no"}
_UKRAINIAN = {"uk", "ukr", "uk-ua"}
_GERMAN = {"de", "deu", "ger", "de-de", "de-at", "de-ch"}
_HEBREW = {"he", "heb", "iw", "he-il", "iw-il"}
_NAMES = {"en": "English", "nb": "Norsk", "uk": "Українська", "de": "Deutsch", "he": "עברית"}
_CODE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8})*$")
# LogosCat's own defaults when a user has never saved a set.
LOGOSCAT_DEFAULTS = ["en", "no", "de"]
# The order the panel lists the live packs in. A new pack under config/ follows them.
PACK_ORDER = ["en", "nb", "uk", "de", "he"]
MAX_TARGETS = 4
NO_SOURCE = "None of your LogosCat source languages is supported here yet"


class LogosCatError(Exception):
    """The call did not produce a subject. ``status`` is the hub's HTTP status."""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)


def logoscat_base_url() -> str:
    """Dev is the local Actors server. Prod is logoscat.com.

    Inside the hub container, dev uses the host gateway. The container's own
    port 8080 is this hub, not Actors.
    """
    mode = os.environ.get("MODE", "dev").strip().lower() or "dev"
    if mode == "prod":
        return "https://logoscat.com"
    if os.environ.get("LOGOSKITTENS_IN_DOCKER") == "1":
        return "http://host.docker.internal:8080"
    return "http://localhost:8080"


def logoscat_public_url() -> str:
    """The address the user's browser opens. In dev it is never the container's host gateway."""
    mode = os.environ.get("MODE", "dev").strip().lower() or "dev"
    return "https://logoscat.com" if mode == "prod" else "http://localhost:8080"


def live_language(code: str) -> str | None:
    """A LogosCat language code this hub can talk in, or None."""
    value = (code or "").strip().lower().replace("_", "-")
    if value in {"en", "en-us", "en-gb"}:
        return "en"
    if value in _NORWEGIAN:
        return "nb"
    if value in _UKRAINIAN:
        return "uk"
    if value in _GERMAN:
        return "de"
    if value in _HEBREW:
        return "he"
    return None


def language_code(code: str) -> str:
    """One hub code. Norwegian becomes nb, Ukrainian uk, German de, and Hebrew he, as live_language maps them. Other codes pass unchanged."""
    value = (code or "").strip().lower().replace("_", "-")
    return live_language(value) or value


def _codes(values) -> list[str]:
    seen: list[str] = []
    for value in values if isinstance(values, list) else []:
        if not isinstance(value, str):
            continue
        code = language_code(value)
        if code and _CODE.match(code) and code not in seen:
            seen.append(code)
    return seen[:10]


def target_codes(values, source: str) -> list[str]:
    """The session's targets: hub codes, in order, never the source, at most four."""
    source_code = language_code(source)
    return [code for code in _codes(values) if code != source_code][:MAX_TARGETS]


def supported_languages() -> list[str]:
    """The live packs: a language with no gaps under config/. Only these are offered as source or target."""
    from logoskittens.content import language_gaps, languages

    live = [code for code in languages() if not language_gaps(code)]
    ordered = [code for code in PACK_ORDER if code in live]
    return ordered + sorted(code for code in live if code not in ordered)


def language_sets(inputs, outputs, origin: str) -> dict:
    """The page's Source and Targets lists, supported languages only. The rest is named in `skipped`.

    LogosCat's sets also give the first choice: the first supported source, and every supported
    target except that source.
    """
    supported = supported_languages()
    sources = [code for code in _codes(inputs) if code in supported]
    targets = [code for code in _codes(outputs) if code in supported]
    skipped = [code for code in _codes(inputs) + _codes(outputs) if code not in supported]
    default_source = sources[0] if sources else ""
    return {
        "success": True,
        "origin": origin,
        "sources": [{"id": code, "live": True, "reason": ""} for code in sources],
        "targets": [{"id": code} for code in targets],
        "skipped": list(dict.fromkeys(skipped)),
        "default_source": default_source,
        "default_targets": [code for code in targets if code != default_source][:MAX_TARGETS],
        "max_targets": MAX_TARGETS,
    }


def local_language_sets() -> dict:
    """Logged out: every live pack, as source and as target. The page remembers its own choice."""
    supported = supported_languages()
    found = language_sets(supported, supported, "local")
    found["default_targets"] = found["default_targets"][:1]
    return found


def logoscat_language_sets(inputs, outputs) -> dict:
    """LogosCat's sets, filtered. With no supported source the talk falls back to the local sets."""
    found = language_sets(inputs, outputs, "logoscat")
    if found["sources"]:
        return found
    names = ", ".join(_NAMES.get(code, code) for code in _codes(inputs)) or "none"
    return {**local_language_sets(), "skipped": found["skipped"], "notice": f"{NO_SOURCE} ({names})."}


def plain_sentence(value: str) -> str:
    """The words of one source item. Tags are dropped."""
    raw = value or ""
    if "<" in raw and ">" in raw:
        parser = _VisibleText()
        try:
            parser.feed(raw)
            parser.close()
            raw = " ".join(parser.parts)
        except Exception:
            raw = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(raw)
    return re.sub(r"\s+", " ", text).strip()


def material_id_for(workspace_session_id: int) -> str:
    return f"logoscat-{workspace_session_id}"


def looks_like_token(token: str) -> bool:
    """An app token from LogosCat Connected apps. Anything else is refused without a call."""
    value = token or ""
    return value.startswith(TOKEN_PREFIX) and TOKEN_MIN <= len(value) <= TOKEN_MAX and value.isascii() and " " not in value


ENDED = "The LogosCat token expired or was revoked. Connect again."


class LogosCatClient:
    """One httpx call at a time, with short caches. The token is kept only as a cache key hash."""

    def __init__(
        self,
        base_url: str | None = None,
        transport: httpx.BaseTransport | None = None,
        clock=time.monotonic,
    ):
        self.base_url = (base_url or logoscat_base_url()).rstrip("/")
        self.public_url = (base_url or logoscat_public_url()).rstrip("/")
        self._transport = transport
        self._clock = clock
        self._lock = threading.Lock()
        self._blocked_until: dict[str, float] = {}
        self._cache: dict[tuple[str, str], tuple[float, tuple[int, dict]]] = {}

    def tokens_url(self) -> str:
        return f"{self.public_url}{TOKENS_PATH}"

    def _cached(self, token: str, path: str, ttl: float | None, method: str = "GET") -> tuple[int, dict]:
        """A 200 is reused for ``ttl`` seconds (None: until a 401). A 401 drops every entry of that token."""
        key = (sha256(token.encode()).hexdigest(), path)
        now = self._clock()
        hit = self._cache.get(key)
        if hit and (ttl is None or now - hit[0] < ttl):
            return hit[1]
        status, payload = self.exchange(method, path, token=token)
        if status == 200 and payload.get("success") is not False:
            self._cache[key] = (now, (status, payload))
        elif status == 401:
            self.forget(token)
        return status, payload

    def forget(self, token: str) -> None:
        digest = sha256(token.encode()).hexdigest()
        for key in [key for key in self._cache if key[0] == digest]:
            del self._cache[key]

    def validate(self, token: str) -> tuple[int, dict]:
        """Who the token belongs to. Cached until a 401."""
        if not looks_like_token(token):
            return 401, {"success": False, "error": ENDED}
        return self._cached(token, "/api/app-token/whoami", None)

    def workspace_sessions(self, token: str) -> tuple[int, dict]:
        if not looks_like_token(token):
            return 401, {"success": False, "error": ENDED}
        return self._cached(token, "/api/workspace-session/all", SESSIONS_TTL_S)

    def language_settings(self, token: str) -> dict:
        """The user's two LogosCat sets, as the page's Source and Targets lists."""
        if not looks_like_token(token):
            raise LogosCatError(ENDED, status=401)
        status, payload = self._cached(token, "/api/language-settings", SETTINGS_TTL_S)
        if status == 401:
            raise LogosCatError(ENDED, status=401)
        if status == 429:
            raise LogosCatError(str(payload.get("error") or "LogosCat is busy."), status=429)
        if status != 200 or payload.get("success") is False:
            raise LogosCatError(str(payload.get("error") or "LogosCat did not return the language settings."))
        settings = payload.get("settings") if isinstance(payload.get("settings"), dict) else {}
        inputs = settings.get("inputLanguagesSet") or LOGOSCAT_DEFAULTS
        outputs = settings.get("outputLanguagesSet") or LOGOSCAT_DEFAULTS
        return logoscat_language_sets(inputs, outputs)

    def exchange(
        self,
        method: str,
        path: str,
        *,
        token: str = "",
        json_body: dict | None = None,
        params: dict | None = None,
    ) -> tuple[int, dict]:
        """One call. A 429 blocks that path until its Retry-After and is never retried here."""
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        with self._lock:
            wait = self._blocked_until.get(path, 0.0) - self._clock()
            if wait > 0:
                return 429, {"success": False, "error": _busy(wait), "retryAfter": int(wait + 0.999)}
            try:
                with httpx.Client(transport=self._transport, timeout=30.0) as client:
                    response = client.request(
                        method,
                        f"{self.base_url}{path}",
                        headers=headers,
                        json=json_body,
                        params=params,
                    )
            except httpx.HTTPError as exc:
                raise LogosCatError("LogosCat is not reachable.") from exc
            if response.status_code == 429:
                try:
                    retry = max(1.0, float(response.headers.get("Retry-After", "60")))
                except ValueError:
                    retry = 60.0
                self._blocked_until[path] = self._clock() + retry
                return 429, {"success": False, "error": _busy(retry), "retryAfter": int(retry + 0.999)}
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise LogosCatError("LogosCat sent an unexpected response.") from exc
        if not isinstance(payload, dict):
            raise LogosCatError("LogosCat sent an unexpected response.")
        return response.status_code, payload

    def import_session(
        self,
        store: Store,
        *,
        token: str,
        workspace_session_id: int,
        talk_language: str,
        name: str,
        cap: int = SOURCE_LINE_CAP,
    ) -> dict:
        """Store source sentences and return the material the page selects."""
        if workspace_session_id <= 0:
            raise LogosCatError("That workspace session is not valid.", status=400)
        talk = live_language(talk_language)
        if talk is None:
            raise LogosCatError("LogosKittens cannot talk in that language yet.", status=400)
        status, identity = self.validate(token)
        if status == 429:
            raise LogosCatError(str(identity.get("error")), status=429)
        if status != 200 or not identity.get("success"):
            raise LogosCatError(ENDED, status=401)
        user = identity.get("user") if isinstance(identity.get("user"), dict) else {}
        try:
            user_id = int(user.get("id"))
        except (TypeError, ValueError) as exc:
            raise LogosCatError("LogosCat did not name the account.") from exc
        grouped, truncated = self._source_lines(token, workspace_session_id, cap)
        language, lines = _choose_lines(grouped, talk)
        title = (name or "").strip() or f"Workspace {workspace_session_id}"
        title = title[:120]
        material_id = material_id_for(workspace_session_id)
        store.save_logoscat_material(
            material_id,
            logoscat_user_id=user_id,
            workspace_session_id=workspace_session_id,
            language=language,
            title=title,
            text="\n".join(lines),
        )
        notice = "The rest of this session was left out." if truncated else ""
        return {
            "success": True,
            "material_id": material_id,
            "title": title,
            "language_id": language,
            "logoscat_user_id": user_id,
            "notice": notice,
        }

    def _source_lines(
        self,
        token: str,
        workspace_session_id: int,
        cap: int,
    ) -> tuple[dict[str, list[str]], bool]:
        grouped: dict[str, list[str]] = {}
        seen: set[str] = set()
        truncated = False
        page = 0
        while page < _MAX_PAGES:
            status, payload = self.exchange(
                "GET",
                "/api/history/recap-by-session",
                token=token,
                params={
                    "workspaceSessionId": workspace_session_id,
                    "page": page,
                    "pageSize": 10,
                },
            )
            if status == 429 and page > 0:
                # Busy partway: keep the pages already read and say the rest was left out.
                return grouped, True
            if status != 200 or not payload.get("success"):
                if status == 401:
                    self.forget(token)
                    raise LogosCatError(ENDED, status=401)
                message = str(payload.get("error") or "LogosCat did not return this session.")
                raise LogosCatError(message, status=429 if status == 429 else 400)
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            pages = data.get("pages") if isinstance(data.get("pages"), list) else []
            for group in pages:
                items = group.get("items") if isinstance(group, dict) else None
                for item in items or []:
                    if not isinstance(item, dict) or item.get("itemType") != "text_input":
                        continue
                    language = live_language(str(item.get("language") or ""))
                    if language is None:
                        if plain_sentence(str(item.get("textValue") or "")):
                            grouped.setdefault("", [])
                        continue
                    text = plain_sentence(str(item.get("textValue") or ""))
                    if not text or text in seen:
                        continue
                    if sum(len(lines) for lines in grouped.values()) >= cap:
                        truncated = True
                        return grouped, truncated
                    seen.add(text)
                    grouped.setdefault(language, []).append(text)
            if truncated or not data.get("hasMore"):
                break
            page += 1
        else:
            truncated = True
        return grouped, truncated


def _busy(seconds: float) -> str:
    return f"LogosCat is busy. Try again in {int(seconds + 0.999)} s."


def _choose_lines(grouped: dict[str, list[str]], talk: str) -> tuple[str, list[str]]:
    live = {key: lines for key, lines in grouped.items() if key in _LIVE and lines}
    if not live:
        if "" in grouped:
            raise LogosCatError("LogosKittens cannot talk in that language yet.", status=400)
        raise LogosCatError("This session has no source sentences.", status=400)
    if len(live) == 1:
        language = next(iter(live))
        return language, live[language]
    if talk in live:
        return talk, live[talk]
    names = " and ".join(_NAMES.get(key, key) for key in sorted(live))
    raise LogosCatError(
        f"This session mixes {names}. None match the talk that is open.",
        status=400,
    )


def mount(app) -> None:
    """Hub routes the page calls. LogosCat is reached from here."""
    from fastapi import Header
    from fastapi.responses import JSONResponse

    def token_of(authorization: str | None) -> str:
        raw = authorization or ""
        if raw.lower().startswith("bearer "):
            return raw[7:].strip()
        return ""

    def failure(exc: LogosCatError) -> JSONResponse:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=exc.status)

    @app.get("/logoscat/info")
    def logoscat_info():
        """Where the user creates a token. Follows MODE: localhost:8080 in dev, logoscat.com in prod."""
        return {"success": True, "tokens_url": app.state.logoscat.tokens_url()}

    @app.post("/logoscat/connect")
    def logoscat_connect(body: ConnectIn):
        """A pasted lkc_ token. A string that is not one is refused without a call to LogosCat."""
        token = body.token.strip()
        if not looks_like_token(token):
            return JSONResponse(
                {"success": False, "error": "That is not a LogosCat app token. It starts with lkc_."},
                status_code=400,
            )
        try:
            status, payload = app.state.logoscat.validate(token)
        except LogosCatError as exc:
            return failure(exc)
        if status == 401:
            return JSONResponse({"success": False, "error": ENDED}, status_code=401)
        if status != 200 or not payload.get("success"):
            return JSONResponse(payload, status_code=status if status >= 400 else 502)
        return {
            "success": True,
            "user": payload.get("user") or {},
            "expiresAt": payload.get("expiresAt") or "",
        }

    @app.post("/logoscat/validate")
    def logoscat_validate(authorization: str | None = Header(default=None)):
        token = token_of(authorization)
        if not token:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        try:
            status, payload = app.state.logoscat.validate(token)
        except LogosCatError as exc:
            return failure(exc)
        if status == 401:
            return JSONResponse({"success": False, "error": ENDED}, status_code=401)
        return JSONResponse(payload, status_code=status)

    @app.get("/logoscat/workspace-sessions")
    def logoscat_sessions(authorization: str | None = Header(default=None)):
        token = token_of(authorization)
        if not token:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        try:
            status, payload = app.state.logoscat.workspace_sessions(token)
        except LogosCatError as exc:
            return failure(exc)
        if status == 401:
            return JSONResponse({"success": False, "error": ENDED}, status_code=401)
        return JSONResponse(payload, status_code=status)

    @app.get("/logoscat/language-settings")
    def logoscat_language_settings(authorization: str | None = Header(default=None)):
        """Logged out, or LogosCat down: the local defaults, so the talk still starts. A dead login is 401."""
        token = token_of(authorization)
        if not token:
            return local_language_sets()
        try:
            return app.state.logoscat.language_settings(token)
        except LogosCatError as exc:
            if exc.status == 401:
                return failure(exc)
            return {**local_language_sets(), "notice": str(exc)}

    @app.delete("/logoscat/materials/{material_id}")
    def logoscat_delete_material(material_id: str):
        """Local delete. LogosCat itself is not called, and no login is needed."""
        if not material_id.startswith("logoscat-"):
            return JSONResponse({"success": False, "error": "Only an imported session can be deleted."}, status_code=400)
        if not app.state.service.store.delete_logoscat_material(material_id):
            return JSONResponse({"success": False, "error": "That material is already gone."}, status_code=404)
        return {"success": True, "material_id": material_id}

    @app.post("/logoscat/import")
    def logoscat_import(body: ImportIn, authorization: str | None = Header(default=None)):
        token = token_of(authorization)
        if not token:
            return JSONResponse({"success": False, "error": "Unauthorized"}, status_code=401)
        try:
            payload = app.state.logoscat.import_session(
                app.state.service.store,
                token=token,
                workspace_session_id=body.workspace_session_id,
                talk_language=body.language_id,
                name=body.name,
            )
        except LogosCatError as exc:
            return failure(exc)
        return payload
