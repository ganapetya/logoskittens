"""Host mode, attach, and the map from a pose token to that body's action name.

The talk asks this package to deliver. It does not open the player socket.
"""

import asyncio
import base64
import contextlib
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from bot_link.auth import tokens_match
from bot_link.players import Player, load_open_pairs, load_players

_OPEN_ROLE = "buddy"
_PCM_RATE = 22050
_MOUTH_PAD_S = 0.45


class HostModeBody(BaseModel):
    on: bool


@dataclass
class StanceRow:
    token: str
    action: str
    intent: str


@dataclass
class Speaking:
    action: str
    intent: str


@dataclass
class Registration:
    speaking: Speaking
    stances: list[StanceRow] = field(default_factory=list)


@dataclass
class _Conn:
    player: Player
    socket: WebSocket
    stop: asyncio.Event
    registration: Registration | None = None
    status_ready: bool | None = None
    status_reason: str = ""


class BotLink:
    """One process-wide player table. Host mode starts off."""

    def __init__(
        self,
        players: list[Player] | None = None,
        *,
        path: Path | None = None,
        open_pairs: frozenset[tuple[str, str]] | None = None,
    ):
        loaded = list(players) if players is not None else load_players(path)
        self._open_pairs = open_pairs if open_pairs is not None else load_open_pairs()
        self._players = loaded
        self._by_id = {player.body_id: player for player in loaded}
        self._host_mode = False
        self._refusal = ""
        self._connections: dict[str, _Conn] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._listen_mode = "speak"
        self._pending_session: str | None = None
        self._audio_handler = None
        self._mouth_role = ""
        self._mouth_queue: list[tuple] = []
        self._mouth_timer: asyncio.TimerHandle | None = None
        self.router = self._build_router()

    @property
    def host_mode(self) -> bool:
        with self._lock:
            return self._host_mode

    @property
    def players(self) -> list[Player]:
        return list(self._players)

    def registration(self, body_id: str) -> dict | None:
        """Speaking action and stance rows for an attached body. None after the socket drops."""
        with self._lock:
            conn = self._connections.get(body_id)
            if conn is None or conn.registration is None:
                return None
            return _public(conn.registration)

    def attached_ids(self) -> list[str]:
        with self._lock:
            return list(self._connections)

    def snapshot(self) -> dict:
        """What the Talk page shows: host mode, the latest refusal, and attached rows."""
        with self._lock:
            return {
                "host_mode": self._host_mode,
                "refusal": self._refusal,
                "players": [_row(conn) for conn in self._connections.values()],
            }

    def deliver(self, *, role: str, pcm: bytes, tokens: list[str], language: str = "") -> list[str]:
        """Send that role's action basenames. Unknown tokens are left out.

        Call this off the player loop. A worker thread is the expected caller.
        Names from any other body are not included.
        """
        with self._lock:
            loop = self._loop
            conn = _conn_for_role(self._connections, role)
            if conn is None or conn.registration is None or loop is None:
                return []
            actions = [conn.registration.speaking.action]
            for name in action_names(conn.registration, tokens):
                if name not in actions:
                    actions.append(name)
            socket = conn.socket
        payload = {
            "type": "delivery",
            "actions": actions,
            "pcm": base64.b64encode(pcm).decode("ascii"),
            "language": language or "",
        }
        if not pcm:
            asyncio.run_coroutine_threadsafe(socket.send_json(payload), loop).result(timeout=5)
            return actions
        seconds = _play_seconds(pcm)
        with self._lock:
            if self._mouth_role:
                self._mouth_queue.append((role, socket, payload, seconds))
                return actions
            self._mouth_role = role
        try:
            asyncio.run_coroutine_threadsafe(socket.send_json(payload), loop).result(timeout=5)
        except Exception:
            loop.call_soon_threadsafe(self._mouth_free, role)
            return actions
        self._arm_mouth(role, seconds)
        return actions

    def cue(self, *, role: str, tokens: list[str]) -> list[str]:
        """A pose with no voice, for example while the reply is being thought.

        No speaking action and no mouth slot: a voice already playing keeps its place,
        and the body's played answer frees nothing. Skipped while that role is speaking.
        """
        with self._lock:
            loop = self._loop
            conn = _conn_for_role(self._connections, role)
            if conn is None or conn.registration is None or loop is None or self._mouth_role == role:
                return []
            actions = action_names(conn.registration, tokens)
            socket = conn.socket
        if not actions:
            return []
        payload = {"type": "delivery", "actions": actions, "pcm": "", "language": ""}
        asyncio.run_coroutine_threadsafe(socket.send_json(payload), loop).result(timeout=5)
        return actions

    async def apply_host_mode(self, on: bool) -> None:
        """Off refuses later attaches and closes the player sockets already open."""
        closing: list[_Conn] = []
        with self._lock:
            self._loop = asyncio.get_running_loop()
            self._host_mode = bool(on)
            if self._host_mode:
                self._refusal = ""
            else:
                closing = list(self._connections.values())
                self._connections.clear()
                self._pending_session = None
                self._mouth_role = ""
                self._mouth_queue.clear()
                self._cancel_mouth_timer()
        for conn in closing:
            conn.stop.set()
            with contextlib.suppress(RuntimeError):
                await conn.socket.close()

    def _build_router(self) -> APIRouter:
        router = APIRouter()
        link = self

        @router.websocket("/players")
        async def players(socket: WebSocket) -> None:
            await link._session(socket)

        @router.get("/host-mode")
        def read_mode() -> dict:
            return {"on": link.host_mode}

        @router.post("/host-mode")
        async def write_mode(body: HostModeBody) -> dict:
            await link.apply_host_mode(body.on)
            return {"on": link.host_mode}

        @router.get("/console")
        def console() -> dict:
            return link.snapshot()

        return router

    async def _session(self, socket: WebSocket) -> None:
        await socket.accept()
        with self._lock:
            self._loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        conn: _Conn | None = None
        try:
            frame = await _next_message(socket, stop)
            if not isinstance(frame, dict) or frame.get("type") != "attach":
                await self._refuse(socket, "role_not_open")
                return
            reason, conn = self._claim(frame, socket, stop)
            if reason or conn is None:
                await self._refuse(socket, reason or "role_not_open")
                conn = None
                return
            await socket.send_json(
                {
                    "type": "attached",
                    "body_id": conn.player.body_id,
                    "role": conn.player.role,
                    "actor": conn.player.actor,
                }
            )
            registered = False
            while True:
                frame = await _next_message(socket, stop)
                if not isinstance(frame, dict):
                    await socket.send_json({"type": "error", "reason": "register_required"})
                    continue
                kind = frame.get("type")
                if kind == "register":
                    if not self._store_register(conn, frame):
                        await socket.send_json({"type": "error", "reason": "bad_register"})
                        continue
                    registered = True
                    await socket.send_json({"type": "registered"})
                    await socket.send_json(self._config(conn))
                elif not registered:
                    await socket.send_json({"type": "error", "reason": "register_required"})
                elif kind == "status":
                    self._store_status(conn, frame)
                elif kind == "audio":
                    self._schedule_audio(frame)
                elif kind == "played":
                    self._mouth_free(conn.player.role)
                else:
                    await socket.send_json({"type": "error", "reason": "unexpected"})
        except WebSocketDisconnect:
            return
        finally:
            if conn is not None:
                self._forget(conn)

    def set_audio_handler(self, handler) -> None:
        """Called with the page session id and one wav after Speak is released."""
        self._audio_handler = handler

    def _config(self, conn: _Conn) -> dict:
        return {
            "type": "config",
            "role": conn.player.role,
            "actor": conn.player.actor,
            "listen_mode": self._listen_mode,
            "listen": False,
        }

    def _store_status(self, conn: _Conn, frame: dict) -> None:
        ready = frame.get("ready") is True
        reason = frame.get("reason") if isinstance(frame.get("reason"), str) else ""
        with self._lock:
            current = self._connections.get(conn.player.body_id)
            if current is not conn:
                return
            conn.status_ready = ready
            conn.status_reason = "" if ready else reason

    def _schedule_audio(self, frame: dict) -> None:
        handler = self._audio_handler
        with self._lock:
            session_id = self._pending_session
            self._pending_session = None
        if not session_id or handler is None:
            return
        raw = frame.get("data") or ""
        try:
            wav = base64.b64decode(raw, validate=False)
        except (ValueError, TypeError):
            return
        mime = str(frame.get("mime") or "audio/wav")
        asyncio.create_task(handler(session_id, wav, mime))

    async def forward_speak(self, *, down: bool, session_id: str) -> str | None:
        """Send the Speak button to the ready buddy. None means it was sent."""
        with self._lock:
            conn = _conn_for_role(self._connections, _OPEN_ROLE)
            if conn is None or conn.registration is None or conn.player.role != _OPEN_ROLE:
                return "No ready player."
            if conn.status_ready is False:
                return conn.status_reason or "Not ready."
            socket = conn.socket
            if down:
                self._pending_session = session_id
        await socket.send_json({"type": "speak", "down": bool(down)})
        return None

    def _claim(self, frame: dict, socket: WebSocket, stop: asyncio.Event) -> tuple[str | None, _Conn | None]:
        body_id = frame.get("body_id")
        with self._lock:
            if not self._host_mode:
                return "host_mode_off", None
            player = self._by_id.get(body_id) if isinstance(body_id, str) else None
            if not _role_open(player, self._open_pairs):
                return "role_not_open", None
            expected = os.environ.get(player.token_env, "") if player is not None else ""
            if not tokens_match(frame.get("token"), expected):
                return "bad_token", None
            if any(item.player.role == player.role for item in self._connections.values()):
                return "one_player", None
            assert player is not None
            conn = _Conn(player=player, socket=socket, stop=stop)
            self._connections[player.body_id] = conn
            self._refusal = ""
            return None, conn

    def _store_register(self, conn: _Conn, frame: dict) -> bool:
        parsed = parse_register(frame)
        if parsed is None:
            return False
        with self._lock:
            current = self._connections.get(conn.player.body_id)
            if current is not conn:
                return False
            conn.registration = parsed
            return True

    def _forget(self, conn: _Conn) -> None:
        role = conn.player.role
        with self._lock:
            current = self._connections.get(conn.player.body_id)
            if current is conn:
                self._connections.pop(conn.player.body_id, None)
            self._mouth_queue = [item for item in self._mouth_queue if item[1] is not conn.socket]
            speaking = self._mouth_role == role and current is conn
        if speaking:
            self._mouth_free(role)

    def _arm_mouth(self, role: str, seconds: float) -> None:
        """Fallback so a body that never says it finished does not hold the other voice."""
        loop = self._loop
        if loop is None:
            return

        def arm() -> None:
            self._cancel_mouth_timer()
            self._mouth_timer = asyncio.get_running_loop().call_later(seconds, self._mouth_free, role)

        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            arm()
        else:
            loop.call_soon_threadsafe(arm)

    def _cancel_mouth_timer(self) -> None:
        timer = self._mouth_timer
        self._mouth_timer = None
        if timer is not None:
            timer.cancel()

    def _mouth_free(self, role: str) -> None:
        """That role's sentence is done. The other voice may start."""
        nxt = None
        with self._lock:
            if self._mouth_role != role:
                return
            self._cancel_mouth_timer()
            self._mouth_role = ""
            if self._mouth_queue:
                nxt = self._mouth_queue.pop(0)
                self._mouth_role = nxt[0]
        if nxt is None:
            return
        next_role, socket, payload, seconds = nxt
        asyncio.create_task(self._send_mouth(next_role, socket, payload, seconds))

    async def _send_mouth(self, role: str, socket: WebSocket, payload: dict, seconds: float) -> None:
        try:
            await socket.send_json(payload)
        except Exception:
            self._mouth_free(role)
            return
        self._arm_mouth(role, seconds)

    async def _refuse(self, socket: WebSocket, reason: str) -> None:
        with self._lock:
            self._refusal = reason
        await socket.send_json({"type": "refused", "reason": reason})
        await socket.close()


def _play_seconds(pcm: bytes) -> float:
    """How long the PCM takes, plus a short tail, if the body never reports played."""
    samples = max(0, len(pcm) // 2)
    return samples / _PCM_RATE + _MOUTH_PAD_S


def action_names(registration: Registration, tokens: list[str]) -> list[str]:
    """Basenames for this registration only, in the order the tokens were asked."""
    by_token: dict[str, str] = {}
    for row in registration.stances:
        by_token.setdefault(row.token, row.action)
    names: list[str] = []
    for token in tokens:
        action = by_token.get(token)
        if action and action not in names:
            names.append(action)
    return names


def parse_register(frame: dict) -> Registration | None:
    speaking = frame.get("speaking")
    stances = frame.get("stances")
    if not isinstance(speaking, dict) or not isinstance(stances, list):
        return None
    action = _basename(speaking.get("action"))
    intent = speaking.get("intent")
    if action is None or not isinstance(intent, str):
        return None
    rows: list[StanceRow] = []
    seen: set[str] = set()
    for item in stances:
        row = _stance(item)
        if row is None or row.token in seen:
            return None
        seen.add(row.token)
        rows.append(row)
    return Registration(speaking=Speaking(action=action, intent=intent), stances=rows)


def _role_open(player: Player | None, open_pairs: frozenset[tuple[str, str]]) -> bool:
    return (
        player is not None
        and player.enabled
        and (player.role, player.steerer) in open_pairs
    )


def _conn_for_role(connections: dict[str, _Conn], role: str) -> _Conn | None:
    for conn in connections.values():
        if conn.player.role == role:
            return conn
    return None


def _row(conn: _Conn) -> dict:
    registration = conn.registration
    ready = registration is not None
    return {
        "body_id": conn.player.body_id,
        "display_name": conn.player.display_name,
        "role": conn.player.role,
        "steerer": conn.player.steerer,
        "speaking": registration.speaking.action if registration else "",
        "stances": [row.token for row in registration.stances] if registration else [],
        "ready": ready and conn.status_ready is not False,
        "reason": "" if conn.status_ready is not False else conn.status_reason,
    }


def _public(registration: Registration) -> dict:
    return {
        "speaking": {"action": registration.speaking.action, "intent": registration.speaking.intent},
        "stances": [
            {"token": row.token, "action": row.action, "intent": row.intent}
            for row in registration.stances
        ],
    }


def _stance(item: object) -> StanceRow | None:
    if not isinstance(item, dict):
        return None
    token = item.get("token")
    action = _basename(item.get("action"))
    intent = item.get("intent")
    if not isinstance(token, str) or not token or any(ch.isspace() for ch in token):
        return None
    if action is None or not isinstance(intent, str):
        return None
    return StanceRow(token=token, action=action, intent=intent)


def _basename(value: object) -> str | None:
    if not isinstance(value, str) or not value or value.strip() != value:
        return None
    if "/" in value or "\\" in value or value.endswith(".d6a") or value in {".", ".."}:
        return None
    return value


async def _next_message(socket: WebSocket, stop: asyncio.Event) -> dict:
    recv = asyncio.create_task(socket.receive_json())
    halted = asyncio.create_task(stop.wait())
    try:
        done, _pending = await asyncio.wait({recv, halted}, return_when=asyncio.FIRST_COMPLETED)
    except asyncio.CancelledError:
        recv.cancel()
        halted.cancel()
        raise
    if recv not in done:
        recv.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await recv
        raise WebSocketDisconnect()
    halted.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await halted
    message = recv.result()
    if not isinstance(message, dict):
        raise WebSocketDisconnect()
    return message
