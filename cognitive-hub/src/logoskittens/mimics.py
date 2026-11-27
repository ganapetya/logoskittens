"""Tokens the hub may ask a body to play. The body maps a token to its own action."""

import json

from logoskittens.content import config_root


def allowed_tokens() -> set[str]:
    path = config_root() / "mimic_tokens.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = raw.get("tokens") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return set()
    return {item.strip() for item in rows if isinstance(item, str) and item.strip()}


def keep_tokens(tokens: list[str]) -> list[str]:
    """Drop a pose the catalog does not name. The body still drops ones it did not register."""
    allowed = allowed_tokens()
    kept: list[str] = []
    for token in tokens:
        name = (token or "").strip()
        if name and name in allowed and name not in kept:
            kept.append(name)
    return kept
