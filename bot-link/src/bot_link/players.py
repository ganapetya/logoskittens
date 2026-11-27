"""Who may attach. The token value stays in the environment named by token_env."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

_FIELDS = ("body_id", "display_name", "role", "actor", "steerer", "token_env")


@dataclass(frozen=True)
class Player:
    body_id: str
    display_name: str
    role: str
    actor: str
    steerer: str
    enabled: bool
    token_env: str
    # Optional loudness per language for this body only, as (language, factor) pairs. 0.7 is 30% quieter.
    volume: tuple[tuple[str, float], ...] = ()

    def gain(self, language: str) -> float:
        """The factor for that language's PCM on this body. 1.0 when the file names none."""
        return dict(self.volume).get((language or "").strip().lower(), 1.0)


def config_dir() -> Path:
    env = os.environ.get("LOGOSKITTENS_CONFIG", "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "config" / "players.json"
        if candidate.is_file():
            return parent / "config"
    raise FileNotFoundError("config/players.json was not found. Set LOGOSKITTENS_CONFIG.")


def load_open_pairs(path: Path | None = None) -> frozenset[tuple[str, str]]:
    """Role and steerer pairs a body may attach with. The file is the allow-list."""
    file = path or (config_dir() / "roles.json")
    raw = json.loads(file.read_text(encoding="utf-8"))
    rows = raw.get("open") if isinstance(raw, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError("roles.json must contain an open list")
    pairs: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each open role must be an object")
        pairs.add((_text(row.get("role"), "role"), _text(row.get("steerer"), "steerer")))
    return frozenset(pairs)


def load_players(path: Path | None = None) -> list[Player]:
    file = path or (config_dir() / "players.json")
    raw = json.loads(file.read_text(encoding="utf-8"))
    rows = raw.get("players") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        raise ValueError("players.json must contain a players list")
    return [_player(row) for row in rows]


def _player(raw: object) -> Player:
    if not isinstance(raw, dict):
        raise ValueError("each player must be an object")
    missing = [key for key in _FIELDS if key not in raw]
    if missing:
        raise ValueError(f"player is missing {', '.join(missing)}")
    enabled = raw.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")
    body_id = _text(raw["body_id"], "body_id")
    return Player(
        body_id=body_id,
        display_name=_text(raw["display_name"], "display_name"),
        role=_text(raw["role"], "role"),
        actor=_text(raw["actor"], "actor"),
        steerer=_text(raw["steerer"], "steerer"),
        enabled=enabled,
        token_env=_text(raw["token_env"], "token_env"),
        volume=_volume(raw.get("volume")),
    )


def _volume(value: object) -> tuple[tuple[str, float], ...]:
    """`{"de": 0.7}`: a factor above 0 and at most 2 for each language code. Absent means none."""
    if value is None:
        return ()
    if not isinstance(value, dict):
        raise ValueError("volume must be an object of language to factor")
    rows = []
    for language, factor in value.items():
        if not isinstance(language, str) or not language.strip():
            raise ValueError("volume keys must be language codes")
        if isinstance(factor, bool) or not isinstance(factor, (int, float)) or not 0 < factor <= 2:
            raise ValueError("volume factors must be numbers above 0 and at most 2")
        rows.append((language.strip().lower(), float(factor)))
    return tuple(sorted(rows))


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value
