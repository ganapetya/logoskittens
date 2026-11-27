"""SQLite session store. One file, WAL mode."""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import event, update
from sqlmodel import Field, Session, SQLModel, UniqueConstraint, create_engine, select


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _migrate_session(engine) -> None:
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(sessionrow)").all()
        present = {row[1] for row in rows}
        additions = {
            "user_id": "VARCHAR NOT NULL DEFAULT 'user-local'",
            "language_id": "VARCHAR NOT NULL DEFAULT 'en'",
            "topic_id": "VARCHAR NOT NULL DEFAULT 'free_speech'",
            "config_id": "VARCHAR NOT NULL DEFAULT ''",
            "anchor_index": "INTEGER NOT NULL DEFAULT 0",
            "next_role": "VARCHAR NOT NULL DEFAULT 'buddy'",
            "hold_anchor": "BOOLEAN NOT NULL DEFAULT 0",
            "material_id": "VARCHAR NOT NULL DEFAULT ''",
            "subject_json": "TEXT NOT NULL DEFAULT ''",
            "sentences_json": "TEXT NOT NULL DEFAULT '[]'",
            "personality_id": "VARCHAR NOT NULL DEFAULT 'peter'",
            "bob_steer": "TEXT NOT NULL DEFAULT ''",
            "bob_why": "TEXT NOT NULL DEFAULT ''",
            "bob_pose": "TEXT NOT NULL DEFAULT ''",
            "rob_cursor": "INTEGER NOT NULL DEFAULT 0",
            "rob_line": "TEXT NOT NULL DEFAULT ''",
            "rob_why": "TEXT NOT NULL DEFAULT ''",
            "rob_quiet": "BOOLEAN NOT NULL DEFAULT 0",
            "teacher_mode": "VARCHAR NOT NULL DEFAULT 'relaxed'",
            "game_id": "VARCHAR NOT NULL DEFAULT ''",
            "deck_json": "TEXT NOT NULL DEFAULT ''",
            "game_state_json": "TEXT NOT NULL DEFAULT ''",
            "wren_note": "TEXT NOT NULL DEFAULT ''",
            "target_languages_json": "TEXT NOT NULL DEFAULT '[]'",
        }
        for name, ddl in additions.items():
            if name not in present:
                conn.exec_driver_sql(f"ALTER TABLE sessionrow ADD COLUMN {name} {ddl}")
        conn.commit()


def _migrate_language(engine) -> None:
    with engine.connect() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(languagerow)").all()
        if not rows:
            return
        present = {row[1] for row in rows}
        if "phrases_json" not in present:
            conn.exec_driver_sql(
                "ALTER TABLE languagerow ADD COLUMN phrases_json TEXT NOT NULL DEFAULT ''"
            )
        conn.commit()


class SessionRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    task_id: str
    situation_json: str
    created_at: datetime = Field(default_factory=_utcnow)
    user_id: str = Field(default="user-local", index=True)
    language_id: str = Field(default="en", index=True)
    topic_id: str = Field(default="free_speech", index=True)
    config_id: str = Field(default="")
    anchor_index: int = Field(default=0)
    next_role: str = Field(default="buddy")
    hold_anchor: bool = Field(default=False)
    material_id: str = Field(default="")
    subject_json: str = Field(default="")
    sentences_json: str = Field(default="[]")
    personality_id: str = Field(default="peter")
    bob_steer: str = Field(default="")
    bob_why: str = Field(default="")
    bob_pose: str = Field(default="")
    rob_cursor: int = Field(default=0)
    rob_line: str = Field(default="")
    rob_why: str = Field(default="")
    rob_quiet: bool = Field(default=False)
    teacher_mode: str = Field(default="relaxed")
    game_id: str = Field(default="")
    deck_json: str = Field(default="")
    game_state_json: str = Field(default="")
    wren_note: str = Field(default="")
    target_languages_json: str = Field(default="[]")


class TeacherNoteRow(SQLModel, table=True):
    __tablename__ = "teacher_note"

    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    sentence_id: str = Field(index=True)
    correction: str = ""
    why: str = ""
    explanation: str = ""
    pcm: bytes = b""


class UserRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    display_name: str
    home_country: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class LanguageRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    display_name: str
    recognizer_model: str
    stt_language: str
    male_voice: str
    female_voice: str
    llm_model: str
    phrases_json: str = ""


class TopicRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    title: str
    sort_order: int = 0


class DossierRow(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("language_id", "topic_id"),)
    id: str = Field(primary_key=True)
    language_id: str = Field(index=True)
    topic_id: str = Field(index=True)
    body_json: str


class PairConfigRow(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("user_id", "language_id", "topic_id"),)
    id: str = Field(primary_key=True)
    user_id: str = Field(default="", index=True)
    language_id: str = Field(default="", index=True)
    topic_id: str = Field(index=True)
    settings_json: str


class TurnRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    user_text: str
    assessment_json: str
    created_at: datetime = Field(default_factory=_utcnow)


class ActorStateRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    turn_id: str
    actor_id: str
    last_emotion: str
    last_text: str


class ErrorRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    turn_id: str
    tag: str
    detail: str


class VocabularyRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    session_id: str = Field(index=True)
    word: str
    source_turn_id: str


class LogosCatMaterialRow(SQLModel, table=True):
    """One downloaded workspace session. The text is not a file in the repo."""

    id: str = Field(primary_key=True)
    logoscat_user_id: int = Field(index=True)
    workspace_session_id: int = Field(index=True)
    language: str = Field(index=True)
    title: str
    text: str


class OwnMaterialRow(SQLModel, table=True):
    """A raw material the user wrote on this hub. It never leaves the hub."""

    id: str = Field(primary_key=True)
    language: str = Field(index=True)
    title: str
    text: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def _wal(dbapi_conn, _connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(self.engine)
        _migrate_session(self.engine)
        _migrate_language(self.engine)
        from logoskittens.catalog import seed_store

        seed_store(self)

    def open(self) -> Session:
        return Session(self.engine)

    def create_session(
        self,
        session_id: str,
        task_id: str,
        situation: dict,
        *,
        user_id: str = "user-local",
        language_id: str = "en",
        topic_id: str = "free_speech",
        config_id: str = "",
        material_id: str = "",
        subject_json: str = "",
        sentences_json: str = "[]",
        personality_id: str = "peter",
        teacher_mode: str = "relaxed",
        game_id: str = "",
        deck_json: str = "",
        game_state_json: str = "",
        wren_note: str = "",
        target_languages_json: str = "[]",
    ) -> None:
        with self.open() as db:
            db.add(
                SessionRow(
                    id=session_id,
                    task_id=task_id,
                    situation_json=json.dumps(situation),
                    user_id=user_id,
                    language_id=language_id,
                    topic_id=topic_id,
                    config_id=config_id,
                    material_id=material_id,
                    subject_json=subject_json,
                    sentences_json=sentences_json,
                    personality_id=personality_id or "peter",
                    teacher_mode=teacher_mode if teacher_mode in {"relaxed", "pedantic"} else "relaxed",
                    game_id=game_id,
                    deck_json=deck_json,
                    game_state_json=game_state_json,
                    wren_note=wren_note,
                    target_languages_json=target_languages_json or "[]",
                )
            )
            db.commit()

    def session_exists(self, session_id: str) -> bool:
        with self.open() as db:
            return db.get(SessionRow, session_id) is not None

    def add_turn(
        self,
        *,
        turn_id: str,
        session_id: str,
        user_text: str,
        assessment: dict,
        actor_states: list[tuple[str, str, str, str]],
        errors: list[tuple[str, str, str]],
        words: list[tuple[str, str]],
    ) -> None:
        with self.open() as db:
            db.add(
                TurnRow(
                    id=turn_id,
                    session_id=session_id,
                    user_text=user_text,
                    assessment_json=json.dumps(assessment),
                )
            )
            for state_id, actor_id, emotion, text in actor_states:
                db.add(
                    ActorStateRow(
                        id=state_id,
                        session_id=session_id,
                        turn_id=turn_id,
                        actor_id=actor_id,
                        last_emotion=emotion,
                        last_text=text,
                    )
                )
            for error_id, tag, detail in errors:
                db.add(
                    ErrorRow(
                        id=error_id,
                        session_id=session_id,
                        turn_id=turn_id,
                        tag=tag,
                        detail=detail,
                    )
                )
            for word_id, word in words:
                db.add(
                    VocabularyRow(
                        id=word_id,
                        session_id=session_id,
                        word=word,
                        source_turn_id=turn_id,
                    )
                )
            db.commit()

    def add_lesson(
        self,
        *,
        turn_id: str,
        session_id: str,
        user_text: str,
        assessment: dict,
        state_id: str,
        actor_id: str,
        emotion: str,
        text: str,
        errors: list[tuple[str, str, str]],
        words: list[tuple[str, str]],
    ) -> None:
        """Teacher judgment and her line. The sibling row is a later write."""
        with self.open() as db:
            db.add(
                TurnRow(
                    id=turn_id,
                    session_id=session_id,
                    user_text=user_text,
                    assessment_json=json.dumps(assessment),
                )
            )
            db.add(
                ActorStateRow(
                    id=state_id,
                    session_id=session_id,
                    turn_id=turn_id,
                    actor_id=actor_id,
                    last_emotion=emotion,
                    last_text=text,
                )
            )
            for error_id, tag, detail in errors:
                db.add(
                    ErrorRow(
                        id=error_id,
                        session_id=session_id,
                        turn_id=turn_id,
                        tag=tag,
                        detail=detail,
                    )
                )
            for word_id, word in words:
                db.add(
                    VocabularyRow(
                        id=word_id,
                        session_id=session_id,
                        word=word,
                        source_turn_id=turn_id,
                    )
                )
            db.commit()

    def add_actor_state(
        self,
        *,
        state_id: str,
        session_id: str,
        turn_id: str,
        actor_id: str,
        emotion: str,
        text: str,
    ) -> None:
        with self.open() as db:
            db.add(
                ActorStateRow(
                    id=state_id,
                    session_id=session_id,
                    turn_id=turn_id,
                    actor_id=actor_id,
                    last_emotion=emotion,
                    last_text=text,
                )
            )
            db.commit()

    def read_session(self, session_id: str) -> dict | None:
        with self.open() as db:
            session = db.get(SessionRow, session_id)
            if session is None:
                return None
            turns = db.exec(
                select(TurnRow).where(TurnRow.session_id == session_id)
            ).all()
            errors = db.exec(
                select(ErrorRow).where(ErrorRow.session_id == session_id)
            ).all()
            words = db.exec(
                select(VocabularyRow).where(VocabularyRow.session_id == session_id)
            ).all()
            states = db.exec(
                select(ActorStateRow).where(ActorStateRow.session_id == session_id)
            ).all()
        return {
            "session_id": session.id,
            "task_id": session.task_id,
            "user_id": session.user_id,
            "language_id": session.language_id,
            "topic_id": session.topic_id,
            "material_id": session.material_id,
            "subject": json.loads(session.subject_json) if session.subject_json else {},
            "sentences": json.loads(session.sentences_json or "[]"),
            "bob_steer": session.bob_steer or "",
            "bob_why": session.bob_why or "",
            "bob_pose": session.bob_pose or "",
            "config_id": session.config_id,
            "anchor_index": session.anchor_index,
            "next_role": session.next_role,
            "hold_anchor": session.hold_anchor,
            "situation": json.loads(session.situation_json),
            "turns": [
                {
                    "turn_id": turn.id,
                    "user_text": turn.user_text,
                    "assessment": json.loads(turn.assessment_json),
                }
                for turn in turns
            ],
            "errors": [{"tag": row.tag, "detail": row.detail} for row in errors],
            "vocabulary": [row.word for row in words],
            "actor_state": [
                {
                    "actor_id": row.actor_id,
                    "turn_id": row.turn_id,
                    "last_emotion": row.last_emotion,
                    "last_text": row.last_text,
                }
                for row in states
            ],
        }

    def get_session_row(self, session_id: str) -> SessionRow | None:
        with self.open() as db:
            row = db.get(SessionRow, session_id)
            if row is not None:
                db.expunge(row)
            return row

    def latest_session(self, user_id: str, language_id: str, topic_id: str) -> SessionRow | None:
        with self.open() as db:
            row = db.exec(
                select(SessionRow)
                .where(SessionRow.user_id == user_id)
                .where(SessionRow.language_id == language_id)
                .where(SessionRow.topic_id == topic_id)
                .order_by(SessionRow.created_at.desc())
            ).first()
            if row is not None:
                db.expunge(row)
            return row

    def game_rows(self, user_id: str, material_id: str) -> list[SessionRow]:
        """This user's game sessions on one material, newest first. One query."""
        with self.open() as db:
            statement = (
                select(SessionRow)
                .where(SessionRow.user_id == user_id)
                .where(SessionRow.material_id == material_id)
                .where(SessionRow.game_id != "")
                .order_by(SessionRow.created_at.desc())
            )
            return list(db.exec(statement).all())

    def history_rows(self, user_id: str, language_id: str) -> list[SessionRow]:
        """H9 `history`. This user's game sessions with a deck in one language, newest first. One query."""
        with self.open() as db:
            statement = (
                select(SessionRow)
                .where(SessionRow.user_id == user_id)
                .where(SessionRow.language_id == language_id)
                .where(SessionRow.game_id != "")
                .where(SessionRow.deck_json != "")
                .order_by(SessionRow.created_at.desc())
            )
            return list(db.exec(statement).all())

    def get_logoscat_material(self, material_id: str) -> LogosCatMaterialRow | None:
        with self.open() as db:
            row = db.get(LogosCatMaterialRow, material_id)
            if row is not None:
                db.expunge(row)
            return row

    def list_logoscat_materials(self, language: str) -> list[LogosCatMaterialRow]:
        with self.open() as db:
            rows = list(
                db.exec(
                    select(LogosCatMaterialRow)
                    .where(LogosCatMaterialRow.language == language)
                    .order_by(LogosCatMaterialRow.title)
                ).all()
            )
            for row in rows:
                db.expunge(row)
            return rows

    def delete_logoscat_material(self, material_id: str) -> bool:
        """Remove one imported workspace session. Sessions that used it keep their own rows."""
        with self.open() as db:
            row = db.get(LogosCatMaterialRow, material_id)
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True

    def list_own_materials(self, language: str) -> list[OwnMaterialRow]:
        with self.open() as db:
            rows = list(
                db.exec(
                    select(OwnMaterialRow).where(OwnMaterialRow.language == language).order_by(OwnMaterialRow.title)
                ).all()
            )
            for row in rows:
                db.expunge(row)
            return rows

    def get_own_material(self, material_id: str) -> OwnMaterialRow | None:
        with self.open() as db:
            row = db.get(OwnMaterialRow, material_id)
            if row is not None:
                db.expunge(row)
            return row

    def save_own_material(self, material_id: str, *, language: str, title: str, text: str) -> None:
        """Insert, or replace the title and text. The language stays the one it was created in."""
        with self.open() as db:
            row = db.get(OwnMaterialRow, material_id)
            if row is None:
                db.add(OwnMaterialRow(id=material_id, language=language, title=title, text=text))
            else:
                row.title = title
                row.text = text
                row.updated_at = _utcnow()
            db.commit()

    def delete_own_material(self, material_id: str) -> bool:
        """Sessions that used it keep their own subject card and deck."""
        with self.open() as db:
            row = db.get(OwnMaterialRow, material_id)
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True

    def save_logoscat_material(
        self,
        material_id: str,
        *,
        logoscat_user_id: int,
        workspace_session_id: int,
        language: str,
        title: str,
        text: str,
    ) -> None:
        with self.open() as db:
            row = db.get(LogosCatMaterialRow, material_id)
            if row is None:
                db.add(
                    LogosCatMaterialRow(
                        id=material_id,
                        logoscat_user_id=logoscat_user_id,
                        workspace_session_id=workspace_session_id,
                        language=language,
                        title=title,
                        text=text,
                    )
                )
            else:
                row.logoscat_user_id = logoscat_user_id
                row.workspace_session_id = workspace_session_id
                row.language = language
                row.title = title
                row.text = text
            db.commit()

    def save_talk(
        self,
        session_id: str,
        *,
        material_id: str,
        subject_json: str,
        sentences_json: str,
    ) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(SessionRow)
                .where(SessionRow.id == session_id)
                .values(
                    material_id=material_id,
                    subject_json=subject_json,
                    sentences_json=sentences_json,
                )
            )

    def save_game(self, session_id: str, deck_json: str, game_state_json: str, wren_note: str) -> None:
        """Write the deck. A sentence save does not clear these columns."""
        with self.engine.begin() as conn:
            conn.execute(
                update(SessionRow)
                .where(SessionRow.id == session_id)
                .values(
                    deck_json=deck_json,
                    game_state_json=game_state_json,
                    wren_note=wren_note,
                )
            )

    def save_bob(self, session_id: str, steer: str, why: str, pose: str = "") -> None:
        """Write the suggestion only. A sentence save does not clear these columns."""
        with self.engine.begin() as conn:
            conn.execute(
                update(SessionRow)
                .where(SessionRow.id == session_id)
                .values(bob_steer=steer, bob_why=why, bob_pose=pose)
            )

    def save_rob_cursor(self, session_id: str, cursor: int) -> None:
        """How many stored lines Rob has already taken. A sentence save does not move this."""
        with self.engine.begin() as conn:
            conn.execute(
                update(SessionRow)
                .where(SessionRow.id == session_id)
                .values(rob_cursor=max(0, cursor))
            )

    def save_teacher_mode(self, session_id: str, mode: str) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                update(SessionRow)
                .where(SessionRow.id == session_id)
                .values(teacher_mode=mode)
            )

    def save_teacher_note(
        self,
        *,
        note_id: str,
        session_id: str,
        sentence_id: str,
        correction: str,
        why: str,
        explanation: str,
        pcm: bytes,
    ) -> None:
        with self.open() as db:
            db.add(
                TeacherNoteRow(
                    id=note_id,
                    session_id=session_id,
                    sentence_id=sentence_id,
                    correction=correction,
                    why=why,
                    explanation=explanation,
                    pcm=pcm,
                )
            )
            db.commit()

    def get_teacher_note(self, note_id: str) -> TeacherNoteRow | None:
        with self.open() as db:
            row = db.get(TeacherNoteRow, note_id)
            if row is not None:
                db.expunge(row)
            return row

    def teacher_note_ids(self, session_id: str) -> dict[str, str]:
        with self.open() as db:
            rows = db.exec(select(TeacherNoteRow).where(TeacherNoteRow.session_id == session_id)).all()
            return {row.sentence_id: row.id for row in rows}

    def save_rob(self, session_id: str, line: str, why: str, *, quiet: bool) -> None:
        """The sentence Savelij will say, or silence with a reason. The cursor stays."""
        with self.engine.begin() as conn:
            conn.execute(
                update(SessionRow)
                .where(SessionRow.id == session_id)
                .values(rob_line=line, rob_why=why, rob_quiet=quiet)
            )

    def append_sentence(self, session_id: str, sentence: dict) -> None:
        """Add one line to the talk log without touching the subject card."""
        with self.open() as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                return
            try:
                data = json.loads(row.sentences_json or "[]")
            except json.JSONDecodeError:
                data = []
            if not isinstance(data, list):
                data = []
            data.append(sentence)
            row.sentences_json = json.dumps(data, ensure_ascii=False)
            db.add(row)
            db.commit()

    def consume_bob_pose(self, session_id: str) -> None:
        """The mimic ran once with the reply that accepted this steer."""
        with self.engine.begin() as conn:
            conn.execute(
                update(SessionRow)
                .where(SessionRow.id == session_id)
                .values(bob_pose="")
            )

    def update_progress(
        self,
        session_id: str,
        *,
        anchor_index: int,
        next_role: str,
        hold_anchor: bool,
        config_id: str,
    ) -> None:
        with self.open() as db:
            row = db.get(SessionRow, session_id)
            if row is None:
                return
            row.anchor_index = anchor_index
            row.next_role = next_role
            row.hold_anchor = hold_anchor
            row.config_id = config_id
            db.add(row)
            db.commit()

    def list_users(self) -> list[UserRow]:
        with self.open() as db:
            rows = list(db.exec(select(UserRow)).all())
            for row in rows:
                db.expunge(row)
            return rows

    def get_user(self, user_id: str) -> UserRow | None:
        with self.open() as db:
            row = db.get(UserRow, user_id)
            if row is not None:
                db.expunge(row)
            return row

    def save_user(self, user_id: str, display_name: str, home_country: str) -> None:
        with self.open() as db:
            row = db.get(UserRow, user_id)
            if row is None:
                db.add(UserRow(id=user_id, display_name=display_name, home_country=home_country))
            else:
                row.display_name = display_name
                row.home_country = home_country
                db.add(row)
            db.commit()

    def list_languages(self) -> list[LanguageRow]:
        with self.open() as db:
            rows = list(db.exec(select(LanguageRow)).all())
            for row in rows:
                db.expunge(row)
            return rows

    def get_language(self, language_id: str) -> LanguageRow | None:
        with self.open() as db:
            row = db.get(LanguageRow, language_id)
            if row is not None:
                db.expunge(row)
            return row

    def save_language(self, row: LanguageRow) -> None:
        with self.open() as db:
            db.merge(row)
            db.commit()

    def save_topic(self, row: TopicRow) -> None:
        with self.open() as db:
            db.merge(row)
            db.commit()

    def list_topics(self) -> list[TopicRow]:
        with self.open() as db:
            rows = list(db.exec(select(TopicRow).order_by(TopicRow.sort_order)).all())
            for row in rows:
                db.expunge(row)
            return rows

    def get_dossier(self, dossier_id: str) -> DossierRow | None:
        with self.open() as db:
            row = db.get(DossierRow, dossier_id)
            if row is not None:
                db.expunge(row)
            return row

    def dossier_for(self, language_id: str, topic_id: str) -> DossierRow | None:
        with self.open() as db:
            row = db.exec(
                select(DossierRow)
                .where(DossierRow.language_id == language_id)
                .where(DossierRow.topic_id == topic_id)
            ).first()
            if row is not None:
                db.expunge(row)
            return row

    def save_dossier(self, row: DossierRow) -> None:
        with self.open() as db:
            db.merge(row)
            db.commit()

    def list_pairs(self) -> list[PairConfigRow]:
        with self.open() as db:
            rows = list(db.exec(select(PairConfigRow)).all())
            for row in rows:
                db.expunge(row)
            return rows

    def find_pair(self, user_id: str, language_id: str, topic_id: str) -> PairConfigRow | None:
        with self.open() as db:
            row = db.exec(
                select(PairConfigRow)
                .where(PairConfigRow.user_id == user_id)
                .where(PairConfigRow.language_id == language_id)
                .where(PairConfigRow.topic_id == topic_id)
            ).first()
            if row is not None:
                db.expunge(row)
            return row

    def save_pair(self, row: PairConfigRow) -> None:
        with self.open() as db:
            db.merge(row)
            db.commit()

    def journal_mode(self) -> str:
        with self.engine.connect() as conn:
            row = conn.exec_driver_sql("PRAGMA journal_mode").one()
        return str(row[0]).lower()
