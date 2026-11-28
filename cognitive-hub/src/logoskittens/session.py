"""Live free-speech session.

Speech-to-text finishes before the buddy thinks. One human line produces one
ElementSolution for buddy-one. The summarize node runs when the raw material
is chosen, not on later turns.
"""

import base64
import json
import sys
import threading
import time
import uuid
from collections.abc import Callable

from logoskittens.actors import load_actors
from logoskittens.audio import AudioClient
from logoskittens.bob import BobSkipped, bob_due, buddy_turns, load_settings, suggest, watch_text
from logoskittens.catalog import language_brief, seed_store
from logoskittens.content import default_language_id, language as language_doc
from pydantic import ValidationError

from logoskittens.games.models import GameDeck
from logoskittens.games import speed
from logoskittens.games.speed import round_key
from logoskittens.games.host import (
    game_options,
    last_results,
    stt_prompt,
    take_prefetched,
    session_targets,
    listed_games,
    wren_ready,
    material_text,
    run_game_prepare,
    run_game_turn,
    session_chrome,
    speak_opening,
)
from logoskittens.games.registry import get_plugin, load_builtin
from logoskittens.graph import run_buddy_turn, run_prepare
from logoskittens.logoscat import target_codes
from logoskittens.llm import complete
from logoskittens.materials import DEFAULT_MATERIAL_ID, MaterialLibrary, menu_item
from logoskittens.personalities import DEFAULT_PERSONALITY_ID, get_personality, list_personalities
from logoskittens.persistence import Store
from logoskittens.primitives import DESKTOP_SITUATION, FREE_SPEECH_TASK, ElementSolutionModel
from logoskittens.expert import ExpertSkipped
from logoskittens.face import SpokenTurn, deliver_spoken
from logoskittens.mimics import keep_tokens
from logoskittens.rob import RobSkipped, human_count, human_records, pedantic_due, rob_due
from logoskittens.scenes import require_material_mode, require_scene
from logoskittens.rob import load_settings as load_rob_settings
from logoskittens.rob import pedantic_watch_text, suggest as rob_suggest
from logoskittens.rob import suggest_pedantic as rob_suggest_pedantic
from logoskittens.rob import unassessed, watch_text as rob_watch_text
from logoskittens.talk import (
    BuddyReply,
    LessonSubjectInput,
    SpokenSentence,
    clean_transcript,
    ongoing_for,
    solution_for,
    split_sentences,
    steer_applies,
    steer_taken,
)
from logoskittens.teachers import get_teacher
from logoskittens.wire import encode

CompleteFn = Callable[..., tuple]


NO_SESSION = "No conversation is running. Choose the settings and press Start."

class SessionService:
    def __init__(
        self,
        store: Store,
        audio: AudioClient,
        complete_fn: CompleteFn = complete,
        deliver_pcm: Callable[..., None] | None = None,
    ):
        self.store = store
        self.audio = audio
        self.complete_fn = complete_fn
        self.deliver_pcm = deliver_pcm
        self.botnet: Callable[[], bool] | None = None
        self.actors = load_actors()
        self.situation = DESKTOP_SITUATION
        self.materials = MaterialLibrary(store)
        self._bob_lock = threading.Lock()
        self._bob_token: dict[str, int] = {}
        self._rob_lock = threading.Lock()
        self._rob_token: dict[str, int] = {}
        # Re-entrant: a Wren score saves the deck while it already holds this lock.
        self._talk_lock = threading.RLock()
        self._wren_lock = threading.Lock()
        self._wren_token: dict[str, int] = {}
        self._openings: dict[str, str] = {}
        # Stage X. Deck-line PCM per session, dropped on the next select. Prefetched next rounds.
        self._pcm: dict = {}
        self._pcm_lock = threading.Lock()
        self._prefetch_lock = threading.Lock()
        self._prefetch_started: set[str] = set()
        self._prefetched: dict = {}
        self._session_options: dict[str, dict] = {}
        self.wren_fn = None
        self.qa_choice: bool | None = None
        self._session_qa: dict[str, bool] = {}
        self._launch = _launch_daemon
        load_builtin()

    def start(self) -> str:
        return self.select("user-local", default_language_id(), DEFAULT_MATERIAL_ID, DEFAULT_PERSONALITY_ID)

    def ensure(self, session_id: str | None) -> str:
        """An existing session, ready for a turn. A missing one is an error: only Start creates a session."""
        if not session_id or not self.store.session_exists(session_id):
            raise ValueError(NO_SESSION)
        row = self.store.get_session_row(session_id)
        if row is not None and (row.game_id or "").strip():
            if get_plugin(row.game_id) is None:
                raise ValueError("That game is not on this hub.")
            return session_id
        self._ensure_subject(session_id)
        return session_id

    def select(
        self,
        user_id: str,
        language_id: str,
        material_id: str,
        personality_id: str = "",
        scene_id: str = "free_speech",
        material_mode: str = "detached",
        teacher_mode: str = "relaxed",
        game_id: str = "",
        qa: bool | None = None,
        target_languages: list[str] | None = None,
        game_options: dict | None = None,
    ) -> str:
        session_id = self._create(
            user_id,
            language_id,
            material_id,
            personality_id,
            scene_id,
            material_mode,
            teacher_mode,
            game_id,
            target_languages or [],
            game_options or {},
        )
        if qa is not None:
            self._session_qa[session_id] = bool(qa)
        return session_id

    def _drop_round_caches(self) -> None:
        with self._pcm_lock:
            self._pcm.clear()

    def _create(
        self,
        user_id: str,
        language_id: str,
        material_id: str,
        personality_id: str,
        scene_id: str,
        material_mode: str,
        teacher_mode: str,
        game_id: str,
        target_languages: list[str],
        options: dict,
    ) -> str:
        game_id = (game_id or "").strip()
        scene = require_scene("talking_game" if game_id else scene_id)
        require_material_mode(material_mode)
        seed_store(self.store)
        user_id = (user_id or "user-local").strip() or "user-local"
        language_id = (language_id or default_language_id()).strip()
        material_id = (material_id or DEFAULT_MATERIAL_ID).strip()
        if self.store.get_user(user_id) is None:
            raise ValueError(f"Unknown user {user_id}")
        try:
            language_doc(language_id)
        except KeyError as exc:
            raise ValueError(f"Unknown language {language_id}") from exc
        personality = get_personality(language_id, personality_id)
        material = self.materials.load(language_id, material_id)
        targets = target_codes(target_languages, language_id)
        targets_json = json.dumps(targets)
        session_id = f"sess-{uuid.uuid4().hex[:12]}"
        self._drop_round_caches()
        if game_id:
            plugin = get_plugin(game_id)
            chosen = game_options(plugin.load_manifest(), options, targets) if plugin is not None else {}
            key = round_key(
                user_id=user_id,
                game_id=game_id,
                material_id=material.id,
                material_text=material.text,
                language_id=language_id,
                targets=targets,
                options=chosen,
                personality_id=personality.id,
            )
            prepared = take_prefetched(self, key)
            if prepared is not None:
                print(f"game prefetch used id={game_id}", file=sys.stderr, flush=True)
            else:
                prepared = run_game_prepare(
                    self,
                    game_id=game_id,
                    material=material,
                    language_id=language_id,
                    person=personality,
                    target_languages=targets,
                    options=chosen,
                    seed=session_id,
                    user_id=user_id,
                )
            self._session_options[session_id] = chosen
            sentences = []
            if prepared.opening_line:
                sentences.append(
                    SpokenSentence(speaker="buddy", text=prepared.opening_line, id=f"line-{uuid.uuid4().hex[:12]}")
                )
                self._openings[session_id] = prepared.opening_line
            task = FREE_SPEECH_TASK.model_copy(
                update={"task_id": prepared.task_id, "language_code": language_id}
            )
            self.store.create_session(
                session_id,
                task.task_id,
                self.situation.model_dump(),
                user_id=user_id,
                language_id=language_id,
                topic_id=scene,
                material_id=material.id,
                subject_json="",
                sentences_json=json.dumps([item.model_dump() for item in sentences], ensure_ascii=False),
                personality_id=personality.id,
                teacher_mode=_teacher_mode(teacher_mode),
                game_id=game_id,
                deck_json=prepared.deck.model_dump_json(),
                game_state_json=prepared.state.model_dump_json(),
                target_languages_json=targets_json,
            )
            return session_id
        subject = run_prepare(material.text, language_id, self.complete_fn)
        task = FREE_SPEECH_TASK.model_copy(update={"language_code": language_id})
        self.store.create_session(
            session_id,
            task.task_id,
            self.situation.model_dump(),
            user_id=user_id,
            language_id=language_id,
            topic_id=scene,
            material_id=material.id,
            subject_json=subject.model_dump_json(),
            sentences_json="[]",
            personality_id=personality.id,
            teacher_mode=_teacher_mode(teacher_mode),
            target_languages_json=targets_json,
        )
        return session_id

    def describe(self, session_id: str) -> dict:
        row = self.store.get_session_row(session_id)
        if row is None:
            return {}
        subject = _subject(row.subject_json)
        user = self.store.get_user(row.user_id)
        person = get_personality(row.language_id, row.personality_id)
        return {
            "scene_id": row.topic_id or "free_speech",
            "material_mode": "detached",
            "user_id": row.user_id,
            "display_name": user.display_name if user else "",
            "language_id": row.language_id,
            "target_languages": session_targets(row),
            "material_id": row.material_id,
            "theme": subject.theme if subject else "",
            "subject": subject.model_dump() if subject else {},
            "materials": [menu_item(item) for item in self.materials.list(row.language_id)],
            "buddy_id": "buddy-one",
            "buddy_name": person.name,
            "personality_id": person.id,
            "personalities": [item.model_dump() for item in list_personalities(row.language_id)],
            "bob_steer": row.bob_steer or "",
            "bob_why": row.bob_why or "",
            "bob_pose": row.bob_pose or "",
            "bob_qa": _bob_qa(),
            "teacher_name": teacher.name if (teacher := get_teacher(row.language_id)) else "",
            "teacher_summary": teacher.summary if teacher else "",
            "rob_line": row.rob_line or "",
            "rob_why": row.rob_why or "",
            "rob_quiet": bool(row.rob_quiet),
            "teacher_mode": _teacher_mode(row.teacher_mode),
            "sentences": _with_notes(self.store, session_id, _sentences(row.sentences_json)),
            "game_id": row.game_id or "",
            "games": self.games_for(row.user_id, row.language_id, row.material_id, session_targets(row)),
            "qa": self.qa_enabled(session_id),
            "game": session_chrome(row, self.qa_enabled(session_id), material_text(self, row))
            if (row.game_id or "").strip()
            else None,
        }

    def games_for(self, user_id: str, language_id: str, material_id: str, targets: list[str]) -> list[dict]:
        """The game picker for this source, targets, Wren state, and the last round on this material."""
        last = last_results(self.store, user_id, material_id) if material_id else {}
        return listed_games(
            language_id, targets=target_codes(targets, language_id), ready=wren_ready(self), last=last
        )

    def catalog(
        self, user_id: str, language_id: str, material_id: str = "", targets: list[str] | None = None
    ) -> dict:
        seed_store(self.store)
        language_id = language_id or default_language_id()
        materials = []
        try:
            materials = [menu_item(item) for item in self.materials.list(language_id)]
        except FileNotFoundError:
            materials = []
        teacher = get_teacher(language_id)
        return {
            "users": [
                {"id": row.id, "display_name": row.display_name, "home_country": row.home_country}
                for row in self.store.list_users()
            ],
            "languages": language_brief(self.store),
            "materials": materials,
            "personalities": [item.model_dump() for item in list_personalities(language_id)],
            "teacher_name": teacher.name if teacher else "",
            "teacher_summary": teacher.summary if teacher else "",
            "games": self.games_for(user_id or "user-local", language_id, material_id, targets or []),
        }

    def perform_audio(
        self,
        session_id: str,
        audio: bytes,
        content_type: str,
        emit: Callable[[dict], None],
    ) -> None:
        prompt = self._stt_prompt(session_id)
        if prompt:
            print(f"stt bias {prompt}", file=sys.stderr, flush=True)
        began = speed.clock()
        transcript = clean_transcript(
            self.audio.transcribe(
                audio,
                content_type,
                language=self._stt_language(session_id),
                prompt=prompt,
            )
        )
        stt_ms = (speed.clock() - began) * 1000
        if not transcript:
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
        self.perform_text(session_id, transcript, emit, stt_ms=stt_ms)

    def perform_text(
        self, session_id: str, user_text: str, emit: Callable[[dict], None], stt_ms: float | None = None
    ) -> None:
        row = self.store.get_session_row(session_id)
        if row is None:
            raise ValueError(f"Unknown session {session_id}")
        if (row.game_id or "").strip():
            run_game_turn(self, session_id, row, user_text, emit, stt_ms=stt_ms)
            return
        subject = _subject(row.subject_json)
        if subject is None:
            raise ValueError("This conversation has no lesson subject.")
        heard = user_text.strip()
        sentences = [SpokenSentence.model_validate(item) for item in _sentences(row.sentences_json)]
        response_index = _next_response(sentences)
        pieces = []
        for piece in split_sentences(heard):
            sentence = SpokenSentence(
                speaker="human",
                text=piece,
                id=f"line-{uuid.uuid4().hex[:12]}",
                response_index=response_index,
            )
            sentences.append(sentence)
            pieces.append({"id": sentence.id, "text": sentence.text})
        emit(
            {
                "type": "heard",
                "session_id": session_id,
                "transcript": heard,
                "pieces": pieces,
                "final": False,
            }
        )
        person = get_personality(row.language_id, row.personality_id)
        steer = (row.bob_steer or "").strip()
        ongoing = ongoing_for(
            subject,
            sentences,
            row.language_id,
            person,
            bob_steer=steer,
            latest_human=heard,
        )
        started = time.perf_counter()
        solution = run_buddy_turn(
            ongoing,
            heard,
            complete=self.complete_fn,
            actors=self.actors,
        )
        altered = steer_applies(heard, steer) and steer_taken(
            solution.speech.text, steer, ongoing, heard
        )
        applied = steer if altered else ""
        for piece in split_sentences(solution.speech.text):
            sentences.append(SpokenSentence(speaker="buddy", text=piece, altered=altered, steer=applied))
        turn_id = f"turn-{uuid.uuid4().hex[:12]}"
        errors: list[BaseException] = []

        def write() -> None:
            try:
                with self._talk_lock:
                    current = self.store.get_session_row(session_id)
                    known = {(item.speaker, item.text) for item in sentences}
                    for item in _sentence_models(current.sentences_json if current else "[]"):
                        key = (item.speaker, item.text)
                        if item.speaker == "teacher" and key not in known:
                            sentences.append(item)
                            known.add(key)
                    self.store.add_turn(
                        turn_id=turn_id,
                        session_id=session_id,
                        user_text=heard,
                        assessment={"line": solution.speech.text, "emotion": solution.emotion},
                        actor_states=[
                            (
                                f"state-{uuid.uuid4().hex[:10]}",
                                solution.actor_id,
                                solution.emotion,
                                solution.speech.text,
                            )
                        ],
                        errors=[],
                        words=[],
                    )
                    self.store.save_talk(
                        session_id,
                        material_id=row.material_id,
                        subject_json=subject.model_dump_json(),
                        sentences_json=json.dumps(
                            [item.model_dump() for item in sentences],
                            ensure_ascii=False,
                        ),
                    )
            except BaseException as exc:
                errors.append(exc)

        writer = threading.Thread(target=write)
        writer.start()
        try:
            voiced = _with_audio(self.audio, solution)
            _log_first_audio(
                (time.perf_counter() - started) * 1000,
                language_doc(row.language_id)["recognizer_model"],
                voiced.speech.voice_model_id,
                row.language_id or "",
            )
            pose = (row.bob_pose or "").strip() if altered else ""
            tokens = keep_tokens([pose] if pose else [])
            _deliver_voiced(
                self,
                voiced,
                session_id,
                row.language_id or "",
                emit,
                role="buddy",
                tokens=tokens,
                altered=altered,
                steer=applied,
            )
            if pose:
                self.store.consume_bob_pose(session_id)
        finally:
            writer.join()
        if errors:
            raise errors[0]
        recent = [(item.speaker, item.text) for item in sentences[-8:]]
        watched = watch_text(
            theme=subject.theme,
            name=person.name,
            gender=person.gender,
            mood=person.mood,
            stance=person.stance,
            likes=", ".join(person.likes),
            summary=person.summary,
            steer=steer,
            recent=recent,
        )
        self._schedule_bob(
            session_id,
            row.language_id,
            watched,
            emit,
            turn_count=buddy_turns([item.speaker for item in sentences]),
        )
        self._schedule_rob(session_id, row.language_id, emit)

    def set_qa(self, on: bool, session_id: str | None = None) -> None:
        """QA belongs to a session. Without one it is the default for the next Start."""
        if session_id:
            self._session_qa[session_id] = bool(on)
        else:
            self.qa_choice = bool(on)

    def qa_enabled(self, session_id: str | None = None) -> bool:
        if session_id and session_id in self._session_qa:
            return self._session_qa[session_id]
        if self.qa_choice is None:
            return _bob_qa()
        return self.qa_choice

    def voice_opening(self, session_id: str, emit: Callable[[dict], None]) -> None:
        speak_opening(self, session_id, emit)

    def finish_game(self, session_id: str, emit: Callable[[dict], None]) -> None:
        from logoskittens.games.host import finish_game

        finish_game(self, session_id, emit)

    def set_teacher_mode(self, session_id: str, mode: str) -> str:
        chosen = _teacher_mode(mode)
        if chosen != (mode or "").strip():
            raise ValueError("Teacher mode must be relaxed or pedantic.")
        self.store.save_teacher_mode(session_id, chosen)
        return chosen

    def snapshot(self, session_id: str) -> dict | None:
        return self.store.read_session(session_id)

    def _schedule_bob(
        self,
        session_id: str,
        language_id: str,
        watched: str,
        emit: Callable[[dict], None],
        turn_count: int,
    ) -> None:
        """Start one suggestion after every third buddy reply. This method does not wait."""
        try:
            settings = load_settings()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            if not bob_due(turn_count, 3):
                return
            print(f"bob failed: {exc}", file=sys.stderr, flush=True)
            self._emit_bob(emit, session_id, status="failed")
            return
        if not bob_due(turn_count, settings.every_n):
            return
        if not settings.enabled:
            return
        if not settings.api_key:
            print("bob skipped: no API key", file=sys.stderr, flush=True)
            return
        with self._bob_lock:
            token = self._bob_token.get(session_id, 0) + 1
            self._bob_token[session_id] = token
        self._emit_bob(emit, session_id, status="thinking")

        def work() -> None:
            self._finish_bob(session_id, token, language_id, watched, emit)

        self._launch(work)

    def _finish_bob(
        self,
        session_id: str,
        token: int,
        language_id: str,
        watched: str,
        emit: Callable[[dict], None],
    ) -> None:
        try:
            steer, why, pose = _suggestion(suggest(watched, language_id=language_id))
        except (BobSkipped, ExpertSkipped) as exc:
            if not self._bob_current(session_id, token):
                return
            print(f"bob skipped: {exc}", file=sys.stderr, flush=True)
            self._emit_bob(emit, session_id, status="idle")
            return
        except Exception as exc:
            if not self._bob_current(session_id, token):
                print(f"bob dropped: {type(exc).__name__}: {exc!r}", file=sys.stderr, flush=True)
                return
            print(f"bob failed: {type(exc).__name__}: {exc!r}", file=sys.stderr, flush=True)
            self._emit_bob(emit, session_id, status="failed")
            return
        with self._bob_lock:
            if self._bob_token.get(session_id) != token:
                return
            if steer:
                self.store.save_bob(session_id, steer, why, pose)
        if not self._bob_current(session_id, token):
            return
        if steer:
            self._emit_bob(emit, session_id, status="idle", steer=steer, why=why, pose=pose)
        else:
            self._emit_bob(emit, session_id, status="idle")

    def _bob_current(self, session_id: str, token: int) -> bool:
        with self._bob_lock:
            return self._bob_token.get(session_id) == token

    def _emit_bob(
        self,
        emit: Callable[[dict], None],
        session_id: str,
        *,
        status: str,
        steer: str | None = None,
        why: str | None = None,
        pose: str | None = None,
    ) -> None:
        if steer is None or why is None or pose is None:
            row = self.store.get_session_row(session_id)
            if steer is None:
                steer = (row.bob_steer if row else "") or ""
            if why is None:
                why = (row.bob_why if row else "") or ""
            if pose is None:
                pose = (row.bob_pose if row else "") or ""
        try:
            emit(
                {
                    "type": "bob",
                    "session_id": session_id,
                    "steer": steer,
                    "why": why,
                    "pose": pose,
                    "status": status,
                }
            )
        except Exception as exc:
            print(f"bob failed: {exc}", file=sys.stderr, flush=True)

    def _schedule_rob(self, session_id: str, language_id: str, emit: Callable[[dict], None]) -> None:
        """After enough new human sentences, judge the stretch not yet assessed.

        The buddy line already sent is not held. The cursor moves when the call starts.
        """
        teacher = get_teacher(language_id)
        if teacher is None:
            return
        try:
            settings = load_rob_settings()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            print(f"rob failed: {exc}", file=sys.stderr, flush=True)
            return
        if not settings.enabled:
            return
        with self._talk_lock:
            row = self.store.get_session_row(session_id)
            if row is None:
                return
            sentences = _sentence_models(row.sentences_json)
            cursor = row.rob_cursor if row.rob_cursor > 0 else 0
            if cursor > len(sentences):
                cursor = len(sentences)
            stretch = unassessed(sentences, cursor)
            mode = _teacher_mode(row.teacher_mode)
            humans = human_records(stretch)
            if mode == "pedantic":
                due = pedantic_due(stretch, settings.pedantic_every_responses)
                watched = pedantic_watch_text(teacher, stretch)
            else:
                due = rob_due(human_count(stretch), settings.every_n)
                watched = rob_watch_text(teacher, stretch)
                mode = "relaxed"
            if not due:
                return
            if not settings.api_key:
                print("rob skipped: no API key", file=sys.stderr, flush=True)
                return
            self.store.save_rob_cursor(session_id, len(sentences))
        with self._rob_lock:
            token = self._rob_token.get(session_id, 0) + 1
            self._rob_token[session_id] = token
        self._emit_rob(emit, session_id, status="thinking")

        def work() -> None:
            self._finish_rob(session_id, token, language_id, watched, emit, mode=mode, humans=humans)

        self._launch(work)

    def _finish_rob(
        self,
        session_id: str,
        token: int,
        language_id: str,
        watched: str,
        emit: Callable[[dict], None],
        mode: str = "relaxed",
        humans: list[dict] | None = None,
    ) -> None:
        if mode == "pedantic":
            self._finish_pedantic(session_id, token, language_id, watched, emit, humans or [])
            return
        try:
            line, why = rob_suggest(watched, language_id=language_id)
        except (RobSkipped, ExpertSkipped) as exc:
            if not self._rob_current(session_id, token):
                return
            print(f"rob skipped: {exc}", file=sys.stderr, flush=True)
            self._emit_rob(emit, session_id, status="idle")
            return
        except Exception as exc:
            if not self._rob_current(session_id, token):
                print(f"rob dropped: {type(exc).__name__}: {exc!r}", file=sys.stderr, flush=True)
                return
            print(f"rob failed: {type(exc).__name__}: {exc!r}", file=sys.stderr, flush=True)
            self._emit_rob(emit, session_id, status="failed")
            return
        quiet = not line
        with self._rob_lock:
            if self._rob_token.get(session_id) != token:
                return
            self.store.save_rob(session_id, line, why, quiet=quiet)
        if not self._rob_current(session_id, token):
            return
        self._emit_rob(emit, session_id, status="idle", line=line, why=why, quiet=quiet)
        if line:
            self._speak_teacher(session_id, line, emit)

    def _finish_pedantic(
        self,
        session_id: str,
        token: int,
        language_id: str,
        watched: str,
        emit: Callable[[dict], None],
        humans: list[dict],
    ) -> None:
        """Store one note per corrected sentence. Nothing is spoken until Hear."""
        try:
            notes = rob_suggest_pedantic(
                watched,
                [item["text"] for item in humans],
                language_id=language_id,
            )
        except (RobSkipped, ExpertSkipped) as exc:
            if not self._rob_current(session_id, token):
                return
            print(f"rob skipped: {exc}", file=sys.stderr, flush=True)
            self._emit_rob(emit, session_id, status="idle")
            return
        except Exception as exc:
            if not self._rob_current(session_id, token):
                print(f"rob dropped: {type(exc).__name__}: {exc!r}", file=sys.stderr, flush=True)
                return
            print(f"rob failed: {type(exc).__name__}: {exc!r}", file=sys.stderr, flush=True)
            self._emit_rob(emit, session_id, status="failed")
            return
        if not self._rob_current(session_id, token):
            return
        teacher = get_teacher(language_id)
        voice = teacher.voice_id if teacher else ""
        pending: list[dict] = []
        failed = False
        for human, note in zip(humans, notes):
            correction, why, explanation = note
            if not correction or not explanation or not human.get("id") or not voice:
                continue
            try:
                pcm = self.audio.synthesize(explanation, language_id, voice)
            except Exception as exc:
                failed = True
                print(f"teacher audio failed: {exc}", file=sys.stderr, flush=True)
                continue
            if not pcm:
                failed = True
                continue
            pending.append(
                {
                    "note_id": f"note-{uuid.uuid4().hex[:12]}",
                    "sentence_id": human["id"],
                    "correction": correction,
                    "why": why,
                    "explanation": explanation,
                    "pcm": pcm,
                }
            )
        if not self._rob_current(session_id, token):
            return
        with self._rob_lock:
            if self._rob_token.get(session_id) != token:
                return
            for item in pending:
                self.store.save_teacher_note(
                    note_id=item["note_id"],
                    session_id=session_id,
                    sentence_id=item["sentence_id"],
                    correction=item["correction"],
                    why=item["why"],
                    explanation=item["explanation"],
                    pcm=item["pcm"],
                )
            if pending:
                joined = "\n".join(item["explanation"] for item in pending)
                self.store.save_rob(session_id, joined, "", quiet=False)
            elif not failed:
                self.store.save_rob(session_id, "", "nothing to correct", quiet=True)
        if pending:
            self._emit_rob(
                emit,
                session_id,
                status="idle",
                line="\n".join(item["explanation"] for item in pending),
                why="",
                quiet=False,
            )
            try:
                emit(
                    {
                        "type": "teacher-notes",
                        "session_id": session_id,
                        "notes": [
                            {
                                "sentence_id": item["sentence_id"],
                                "note_id": item["note_id"],
                                "explanation": item["explanation"],
                            }
                            for item in pending
                        ],
                    }
                )
            except Exception as exc:
                print(f"rob failed: {exc}", file=sys.stderr, flush=True)
            return
        if failed:
            self._emit_rob(emit, session_id, status="failed")
            return
        self._emit_rob(emit, session_id, status="idle", line="", why="nothing to correct", quiet=True)

    def _rob_current(self, session_id: str, token: int) -> bool:
        with self._rob_lock:
            return self._rob_token.get(session_id) == token

    def _emit_rob(
        self,
        emit: Callable[[dict], None],
        session_id: str,
        *,
        status: str,
        line: str | None = None,
        why: str | None = None,
        quiet: bool | None = None,
    ) -> None:
        if line is None or why is None or quiet is None:
            row = self.store.get_session_row(session_id)
            if line is None:
                line = (row.rob_line if row else "") or ""
            if why is None:
                why = (row.rob_why if row else "") or ""
            if quiet is None:
                quiet = bool(row.rob_quiet) if row else False
        try:
            emit(
                {
                    "type": "rob",
                    "session_id": session_id,
                    "line": line,
                    "why": why,
                    "quiet": quiet,
                    "status": status,
                }
            )
        except Exception as exc:
            print(f"rob failed: {exc}", file=sys.stderr, flush=True)

    def _speak_teacher(self, session_id: str, line: str, emit: Callable[[dict], None]) -> None:
        """Say Rob's sentence as teacher-one. The text is not sent through another model."""
        row = self.store.get_session_row(session_id)
        if row is None:
            return
        teacher = get_teacher(row.language_id)
        actor = self.actors.get("teacher-one")
        if teacher is None or actor is None or not actor.active:
            print("rob skipped: no teacher", file=sys.stderr, flush=True)
            return
        solution = solution_for(
            BuddyReply(line=line, emotion="neutral"),
            actor,
            row.language_id,
            teacher.voice_id,
        )
        try:
            voiced = _with_audio(self.audio, solution)
        except Exception as exc:
            print(f"teacher audio failed: {exc}", file=sys.stderr, flush=True)
            return
        _deliver_voiced(self, voiced, session_id, row.language_id, emit, role="teacher", speaker=teacher.name)
        sentence = SpokenSentence(speaker="teacher", text=line).model_dump()
        with self._talk_lock:
            self.store.append_sentence(session_id, sentence)

    def _ensure_subject(self, session_id: str) -> None:
        row = self.store.get_session_row(session_id)
        if row is None or (row.game_id or "").strip() or _subject(row.subject_json) is not None:
            return
        material_id = row.material_id or DEFAULT_MATERIAL_ID
        try:
            material = self.materials.load(row.language_id, material_id)
        except FileNotFoundError:
            return
        subject = run_prepare(material.text, row.language_id, self.complete_fn)
        self.store.save_talk(
            session_id,
            material_id=material.id,
            subject_json=subject.model_dump_json(),
            sentences_json=row.sentences_json or "[]",
        )

    def _stt_prompt(self, session_id: str) -> str:
        """The game's speech-recognition bias (H17). Free speech sends none."""
        row = self.store.get_session_row(session_id)
        if row is None or not (row.game_id or "").strip() or not (row.deck_json or "").strip():
            return ""
        plugin = get_plugin(row.game_id)
        if plugin is None:
            return ""
        try:
            deck = GameDeck.model_validate_json(row.deck_json)
            manifest = plugin.load_manifest()
        except (OSError, ValueError, ValidationError):
            return ""
        return stt_prompt(manifest, deck, material_text(self, row))

    def _stt_language(self, session_id: str) -> str:
        row = self.store.get_session_row(session_id)
        if row is None:
            return "en"
        try:
            return str(language_doc(row.language_id)["stt_language"])
        except KeyError:
            return "en"


def _teacher_mode(value: str | None) -> str:
    mode = (value or "").strip()
    if mode in {"relaxed", "pedantic"}:
        return mode
    return "relaxed"


def _next_response(sentences: list[SpokenSentence]) -> int:
    highest = 0
    for item in sentences:
        if item.speaker == "human" and item.response_index > highest:
            highest = item.response_index
    return highest + 1


def _with_notes(store, session_id: str, sentences: list[dict]) -> list[dict]:
    """Attach note ids. The PCM stays in the note table."""
    ids = store.teacher_note_ids(session_id)
    marked = []
    for item in sentences:
        row = dict(item)
        note_id = ids.get(str(row.get("id") or ""))
        if note_id:
            row["note_id"] = note_id
        marked.append(row)
    return marked


def _subject(payload: str) -> LessonSubjectInput | None:
    if not payload:
        return None
    try:
        return LessonSubjectInput.model_validate(json.loads(payload))
    except (json.JSONDecodeError, ValueError):
        return None


def _sentence_models(payload: str) -> list[SpokenSentence]:
    models: list[SpokenSentence] = []
    for item in _sentences(payload):
        try:
            models.append(SpokenSentence.model_validate(item))
        except ValueError:
            continue
    return models


def _sentences(payload: str) -> list[dict]:
    try:
        data = json.loads(payload or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    sentences: list[dict] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        sentence = dict(item)
        sentence["altered"] = bool(sentence.get("altered", False))
        sentences.append(sentence)
    return sentences


def _actor_message(
    session_id: str,
    solution: ElementSolutionModel,
    *,
    altered: bool,
    steer: str,
    final: bool,
    play_on_page: bool = False,
    speaker: str = "",
) -> dict:
    message = {
        "type": "actor",
        "session_id": session_id,
        "final": final,
        "altered": altered,
        "steer": steer,
        "play_on_page": play_on_page,
        "solutions": [base64.b64encode(encode(solution)).decode("ascii")],
    }
    if speaker:
        message["speaker"] = speaker
    return message


def _deliver_voiced(
    service: SessionService,
    voiced: ElementSolutionModel,
    session_id: str,
    language_id: str,
    emit: Callable[[dict], None],
    *,
    role: str,
    tokens: list[str] | None = None,
    altered: bool = False,
    steer: str = "",
    speaker: str = "",
) -> None:
    """The line is already voiced. This only chooses the page or the role's body."""
    deliver_spoken(
        SpokenTurn(
            session_id=session_id,
            role=role,
            voiced=voiced,
            language_id=language_id,
            tokens=list(tokens or []),
            altered=altered,
            steer=steer,
            speaker=speaker,
        ),
        emit=emit,
        deliver_pcm=service.deliver_pcm,
        botnet=service.botnet,
    )


def _suggestion(result: tuple) -> tuple[str, str, str]:
    if len(result) == 2:
        steer, why = result
        return steer, why, ""
    steer, why, pose = result
    return steer, why, pose


def _bob_qa() -> bool:
    try:
        return load_settings().qa
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _launch_daemon(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, name="bob", daemon=True).start()


def _log_first_audio(elapsed_ms: float, recognizer: str, voice_id: str, language_id: str = "") -> None:
    from logoskittens.speech.router import last_tts_via, recognizer_label

    print(
        f"first-audio ms={elapsed_ms:.0f} recognizer={recognizer_label(language_id, recognizer)} "
        f"voice={voice_id} tts_via={last_tts_via()}",
        file=sys.stderr,
        flush=True,
    )


def _with_audio(audio: AudioClient, solution: ElementSolutionModel) -> ElementSolutionModel:
    pcm = audio.synthesize(
        solution.speech.text,
        solution.speech.language_code,
        solution.speech.voice_model_id,
    )
    speech = solution.speech.model_copy(update={"precomputed_audio_pcm": pcm})
    return solution.model_copy(update={"speech": speech})