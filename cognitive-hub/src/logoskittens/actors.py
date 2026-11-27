"""Load actor definitions from JSON."""

import json
from pathlib import Path

from pydantic import ValidationError

from logoskittens.content import config_root
from logoskittens.primitives import Actor


class ActorLoadError(ValueError):
    pass


def load_actors(directory: Path | None = None) -> dict[str, Actor]:
    """Actor files live in ``config/actors``. A passed directory is for tests.

    A language overlay that has no actors directory keeps the repo actors.
    Actors are not part of a language pack.
    """
    folder = directory or _actor_dir()
    paths = sorted(folder.glob("*.json"))
    if not paths:
        raise ActorLoadError(f"no actor JSON files in {folder}")
    actors: dict[str, Actor] = {}
    for path in paths:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            actor = Actor.model_validate(raw)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ActorLoadError(f"{path.name}: {exc}") from exc
        actors[actor.actor_id] = actor
    return actors


def _actor_dir() -> Path:
    configured = config_root() / "actors"
    if configured.is_dir() and any(configured.glob("*.json")):
        return configured
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / "actors"
        if candidate.is_dir() and any(candidate.glob("*.json")):
            return candidate
    return configured
