"""Lab notes for the simulation loop. This file is not the lesson database."""

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import MetaData, event
from sqlmodel import Field, Session, SQLModel, create_engine, select

from logoskittens.sim.schema import SCORES, parse_verdict


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SimSQLModel(SQLModel):
    metadata = MetaData()


class ExperimentRow(SimSQLModel, table=True):
    id: str = Field(primary_key=True)
    created_at: str = Field(default_factory=_utcnow)
    hypothesis: str = ""
    proposal_path: str = ""
    status: str = "proposed"


class RunRow(SimSQLModel, table=True):
    id: str = Field(primary_key=True)
    created_at: str = Field(default_factory=_utcnow)
    experiment_id: str = ""
    scenario_id: str = ""
    trace_path: str = ""


class ScoreRow(SimSQLModel, table=True):
    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    dimension: str
    score: int
    flags_json: str = ""
    critique: str = ""


class NoteRow(SimSQLModel, table=True):
    id: str = Field(primary_key=True)
    created_at: str = Field(default_factory=_utcnow)
    kind: str = Field(index=True)
    persona: str = Field(default="", index=True)
    cefr: str = Field(default="", index=True)
    error_tag: str = ""
    body: str
    source_run_id: str = ""


class LabMemory:
    """SQLite notes the CLI agents read at the start of a loop."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.engine = create_engine(
            f"sqlite:///{path}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(self.engine, "connect")
        def _wal(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        SimSQLModel.metadata.create_all(self.engine)

    def open(self) -> Session:
        return Session(self.engine)

    def add_note(
        self,
        *,
        note_id: str,
        kind: str,
        body: str,
        persona: str = "",
        cefr: str = "",
        error_tag: str = "",
        source_run_id: str = "",
    ) -> None:
        with self.open() as session:
            session.add(
                NoteRow(
                    id=note_id,
                    kind=kind,
                    body=body,
                    persona=persona,
                    cefr=cefr,
                    error_tag=error_tag,
                    source_run_id=source_run_id,
                )
            )
            session.commit()

    def add_verdict(self, payload: dict, *, persona: str = "", cefr: str = "") -> str:
        verdict = parse_verdict(payload)
        with self.open() as session:
            session.add(RunRow(id=verdict.dialogue_id, scenario_id=verdict.scenario_id))
            for name in SCORES:
                session.add(
                    ScoreRow(
                        id=f"{verdict.dialogue_id}-{name}",
                        run_id=verdict.dialogue_id,
                        dimension=name,
                        score=getattr(verdict.scores, name),
                        flags_json=json.dumps(verdict.flags.model_dump()),
                    )
                )
            session.add(
                NoteRow(
                    id=f"{verdict.dialogue_id}-summary",
                    kind="summary",
                    persona=persona,
                    cefr=cefr,
                    body=verdict.summary,
                    source_run_id=verdict.dialogue_id,
                )
            )
            for index, critique in enumerate(verdict.critiques):
                session.add(
                    NoteRow(
                        id=f"{verdict.dialogue_id}-c{index}",
                        kind="critique",
                        persona=persona,
                        cefr=cefr,
                        body=critique.text,
                        source_run_id=verdict.dialogue_id,
                    )
                )
            session.commit()
        return verdict.dialogue_id

    def query(self, *, persona: str = "", cefr: str = "", limit: int = 8) -> list[dict]:
        with self.open() as session:
            statement = select(NoteRow).order_by(NoteRow.created_at.desc())
            if persona:
                statement = statement.where(NoteRow.persona == persona)
            if cefr:
                statement = statement.where(NoteRow.cefr == cefr)
            rows = session.exec(statement.limit(limit)).all()
        return [
            {
                "id": row.id,
                "kind": row.kind,
                "persona": row.persona,
                "cefr": row.cefr,
                "error_tag": row.error_tag,
                "body": row.body,
                "source_run_id": row.source_run_id,
                "created_at": row.created_at,
            }
            for row in rows
        ]
