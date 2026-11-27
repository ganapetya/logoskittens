"""FastAPI WebSocket surface for the cognitive hub."""

import asyncio
import base64
import os
import re
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bot_link import BotLink

from logoskittens.audio import AudioClient, AudioError
from logoskittens.build_id import BUILD
from logoskittens.llm import LLMError
from logoskittens.logoscat import LogosCatClient
from logoskittens.logoscat import mount as mount_logoscat
from logoskittens.persistence import Store
from logoskittens.recognizer import switch_recognizer
from logoskittens.session import SessionService

# A material or language id in a URL: letters, digits, `_` and `-`. Nothing that walks a path.
_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,120}")


def create_app(service: SessionService | None = None, link: BotLink | None = None) -> FastAPI:
    app = FastAPI(title="LogosKittens cognitive hub")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.service = service or _service_from_env()
    app.state.logoscat = LogosCatClient()
    app.state.link = link or BotLink()
    app.state.page_emit = {}
    def _deliver(pcm, tokens=None, language="", role="buddy"):
        return app.state.link.deliver(
            role=role or "buddy",
            pcm=pcm,
            tokens=list(tokens or []),
            language=language or "",
        )

    app.state.service.deliver_pcm = _deliver
    app.state.service.botnet = lambda: app.state.link.host_mode
    print(f"hub build {BUILD}", file=sys.stderr, flush=True)

    def _listening_pose() -> None:
        """The buddy body shows it heard, while recognition and the model run.
        LISTEN_POSE names the mimic token; off (or empty) sends nothing."""
        token = os.environ.get("LISTEN_POSE", "curiosity").strip()
        if not token or token == "off":
            return
        try:
            app.state.link.cue(role="buddy", tokens=[token])
        except Exception as exc:
            print(f"listening pose failed: {exc}", file=sys.stderr, flush=True)

    async def _player_audio(session_id: str, wav: bytes, mime: str) -> None:
        emit = app.state.page_emit.get(session_id)
        if emit is None:
            return

        def run() -> None:
            try:
                if not wav:
                    emit(
                        {
                            "type": "heard",
                            "session_id": session_id,
                            "transcript": "",
                            "notice": "No speech detected.",
                            "final": True,
                        }
                    )
                    return
                _listening_pose()
                app.state.service.perform_audio(session_id, wav, mime, emit)
            except Exception as exc:
                print(f"player audio failed: {exc}", file=sys.stderr, flush=True)
                emit({"type": "error", "message": "The recording was not heard."})

        await asyncio.to_thread(run)

    app.state.link.set_audio_handler(_player_audio)
    app.include_router(app.state.link.router)

    @app.get("/health")
    def health():
        return {"status": "ok", "build": BUILD}

    @app.get("/sessions/{session_id}")
    def read_session(session_id: str):
        snapshot = app.state.service.snapshot(session_id)
        if snapshot is None:
            return {"error": "not found"}
        return snapshot

    @app.get("/catalog")
    def catalog(user_id: str = "user-local", language_id: str = "en", material_id: str = "", targets: str = ""):
        chosen = [item.strip() for item in targets.split(",") if item.strip()]
        return app.state.service.catalog(user_id, language_id, material_id, chosen)

    @app.get("/materials/{material_id}")
    def material(material_id: str, language_id: str = "en"):
        """One material's text, for the Read the text window. The catalog list never carries the sentences."""
        if not (_SAFE_ID.fullmatch(material_id) and _SAFE_ID.fullmatch(language_id)):
            raise HTTPException(status_code=404, detail="not found")
        try:
            item = app.state.service.materials.load(language_id, material_id)
        except (OSError, ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="not found")
        return {"id": item.id, "language": item.language, "title": item.title, "text": item.text}

    class OwnMaterialIn(BaseModel):
        language_id: str = ""
        title: str = ""
        text: str = ""

    def _own_error(message: str, status: int = 400) -> JSONResponse:
        return JSONResponse({"success": False, "error": message}, status_code=status)

    @app.post("/materials")
    def add_material(body: OwnMaterialIn):
        """A material the user wrote. It is stored in this hub's SQLite file only."""
        try:
            item = app.state.service.materials.add_own(body.language_id, body.title, body.text)
        except ValueError as exc:
            return _own_error(str(exc))
        return {"success": True, "material_id": item.id, "language_id": item.language, "title": item.title}

    @app.put("/materials/{material_id}")
    def edit_material(material_id: str, body: OwnMaterialIn):
        if not _SAFE_ID.fullmatch(material_id):
            return _own_error("That material is not on this hub.", 404)
        try:
            item = app.state.service.materials.edit_own(material_id, body.title, body.text)
        except LookupError as exc:
            return _own_error(str(exc), 404)
        except ValueError as exc:
            return _own_error(str(exc))
        return {"success": True, "material_id": item.id, "language_id": item.language, "title": item.title}

    @app.delete("/materials/{material_id}")
    def delete_material(material_id: str):
        if not _SAFE_ID.fullmatch(material_id):
            return _own_error("That material is not on this hub.", 404)
        try:
            gone = app.state.service.materials.delete_own(material_id)
        except ValueError as exc:
            return _own_error(str(exc))
        if not gone:
            return _own_error("That material is already gone.", 404)
        return {"success": True, "material_id": material_id}

    @app.get("/teacher-notes/{note_id}")
    def teacher_note(note_id: str, session_id: str = ""):
        note = app.state.service.store.get_teacher_note(note_id)
        if note is None or not session_id or note.session_id != session_id:
            raise HTTPException(status_code=404, detail="not found")
        return {
            "note_id": note.id,
            "session_id": note.session_id,
            "sentence_id": note.sentence_id,
            "correction": note.correction,
            "why": note.why,
            "explanation": note.explanation,
            "pcm": base64.b64encode(note.pcm).decode("ascii"),
        }

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        service_obj: SessionService = app.state.service
        link_obj: BotLink = app.state.link
        loop = asyncio.get_running_loop()
        session_id: str | None = None

        def emit(payload: dict) -> None:
            asyncio.run_coroutine_threadsafe(socket.send_json(payload), loop).result()

        def remember() -> None:
            if session_id:
                app.state.page_emit[session_id] = emit

        try:
            while True:
                message = await socket.receive_json()
                try:
                    kind = message.get("type")
                    if kind == "start":
                        session_id = service_obj.start()
                        remember()
                        row = service_obj.store.get_session_row(session_id)
                        await _publish(socket, service_obj, session_id, row.language_id if row else "en")
                    elif kind == "resume":
                        # Only an existing session. An unknown id is an error, never a new talk.
                        session_id = service_obj.ensure(str(message.get("session_id") or "") or None)
                        remember()
                        row = service_obj.store.get_session_row(session_id)
                        await _publish(socket, service_obj, session_id, row.language_id if row else "en")
                    elif kind == "select":
                        language_id = str(message.get("language_id") or "en")
                        session_id = service_obj.select(
                            str(message.get("user_id") or "user-local"),
                            language_id,
                            str(message.get("material_id") or ""),
                            str(message.get("personality_id") or ""),
                            scene_id=str(message.get("scene_id") or ""),
                            material_mode=str(message.get("material_mode") or ""),
                            teacher_mode=str(message.get("teacher_mode") or "relaxed"),
                            game_id=str(message.get("game_id") or ""),
                            qa=message.get("qa") if isinstance(message.get("qa"), bool) else None,
                            target_languages=[
                                str(item) for item in message.get("target_languages") or [] if isinstance(item, str)
                            ]
                            if isinstance(message.get("target_languages"), list)
                            else [],
                            game_options=message.get("game_options")
                            if isinstance(message.get("game_options"), dict)
                            else None,
                        )
                        remember()
                        await _publish(socket, service_obj, session_id, language_id)
                        await asyncio.to_thread(service_obj.voice_opening, session_id, emit)
                    elif kind == "transcript":
                        session_id = service_obj.ensure(session_id)
                        remember()
                        text = str(message.get("text", "")).strip()
                        if not text:
                            await socket.send_json({"type": "error", "message": "Empty transcript."})
                            continue
                        await asyncio.to_thread(service_obj.perform_text, session_id, text, emit)
                    elif kind == "audio":
                        session_id = service_obj.ensure(session_id)
                        remember()
                        raw = base64.b64decode(message.get("data", ""))
                        content_type = str(message.get("mime") or "application/octet-stream")
                        await asyncio.to_thread(
                            service_obj.perform_audio, session_id, raw, content_type, emit
                        )
                    elif kind == "qa":
                        service_obj.set_qa(bool(message.get("on")), session_id)
                    elif kind == "game-end":
                        if not session_id:
                            await socket.send_json({"type": "error", "message": "No game is open."})
                            continue
                        await asyncio.to_thread(service_obj.finish_game, session_id, emit)
                    elif kind == "teacher-mode":
                        if not session_id:
                            await socket.send_json({"type": "error", "message": "No conversation yet."})
                            continue
                        mode = service_obj.set_teacher_mode(session_id, str(message.get("mode") or ""))
                        await socket.send_json(
                            {"type": "teacher-mode", "session_id": session_id, "mode": mode}
                        )
                    elif kind == "speak":
                        if not session_id:
                            await socket.send_json({"type": "error", "message": "No conversation yet."})
                            continue
                        reason = await link_obj.forward_speak(
                            down=bool(message.get("down")),
                            session_id=session_id,
                        )
                        if reason:
                            await socket.send_json({"type": "error", "message": reason})
                    else:
                        await socket.send_json({"type": "error", "message": f"Unknown message type: {kind}"})
                except (LLMError, AudioError, ValueError) as exc:
                    await socket.send_json({"type": "error", "message": str(exc)})
        except WebSocketDisconnect:
            return
        finally:
            if session_id:
                app.state.page_emit.pop(session_id, None)

    mount_logoscat(app)
    return app


def _hello(service: SessionService, session_id: str) -> dict:
    described = service.describe(session_id)
    return {"type": "session", "session_id": session_id, **described}


async def _publish(socket: WebSocket, service: SessionService, session_id: str, language_id: str) -> None:
    """Load this language's recognizer, then tell the page the new session.

    The spoken opening is sent only after the recognizer call returns, so speech
    is not transcribed by the weight that was loaded for the previous lesson.
    """
    recognizer = await asyncio.to_thread(switch_recognizer, language_id)
    payload = _hello(service, session_id)
    payload["recognizer"] = recognizer
    await socket.send_json(payload)


def _service_from_env() -> SessionService:
    db_path = Path(os.environ.get("SQLITE_PATH", "data/logoskittens.db"))
    audio_url = os.environ.get("AUDIO_ENGINE_URL", "http://audio-engine:8081")
    return SessionService(Store(db_path), AudioClient(audio_url))


app = create_app()
