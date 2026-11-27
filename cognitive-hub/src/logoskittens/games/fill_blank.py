"""FillInGame. Wren writes the unfinished lead-ins at prepare. Every line is a deck string. The turn calls no model."""

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from logoskittens.content import config_root
from logoskittens.games.host import gloss_of, prepare_user
from logoskittens.games.models import CursorState, GameDeck, GameManifest, TurnExit


class _Prepare(TypedDict, total=False):
    language_id: str
    material_id: str
    raw_text: str
    game_id: str
    rejection: str
    target_languages: list
    wren_system: str
    partner_system: str
    deck: dict
    state: dict


class _Turn(TypedDict, total=False):
    heard: str
    deck: dict
    state: dict
    exit: dict


class FillInPlugin:
    id = "fill_blank"

    def load_manifest(self) -> GameManifest:
        path = config_root() / "games" / "fill_blank.json"
        if not path.is_file():
            raise ValueError(path.name)
        return GameManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def state_type(self) -> type[BaseModel]:
        return CursorState

    def build_prepare_graph(self, wren):
        def prepare(state: _Prepare) -> dict:
            languages = list(state.get("target_languages") or [])
            raw = wren(
                prepare_user(state.get("raw_text") or "", state.get("rejection") or "", languages),
                system=state.get("wren_system") or "",
            )
            targets = _targets(raw, languages)
            active = targets[0]["id"] if targets and targets[0]["id"] else "t1"
            return {
                "deck": {
                    "deck_version": 1,
                    "game_id": "fill_blank",
                    "language": state.get("language_id") or "",
                    "material_id": state.get("material_id") or "",
                    "targets": targets,
                },
                "state": CursorState(active_id=active).model_dump(),
            }

        graph = StateGraph(_Prepare)
        graph.add_node("prepare", prepare)
        graph.set_entry_point("prepare")
        graph.add_edge("prepare", END)
        return graph.compile()

    def build_turn_graph(self):
        def decide(state: _Turn) -> dict:
            del state
            # apply_local checks the completion and picks the deck line: the next stem, or the retry line.
            decision = TurnExit(source="deck", local_check="contains", match="active")
            return {"exit": decision.model_dump()}

        graph = StateGraph(_Turn)
        graph.add_node("decide", decide)
        graph.set_entry_point("decide")
        graph.add_edge("decide", END)
        return graph.compile()

    def apply_wren(self, deck: GameDeck, state: BaseModel, payload: dict):
        del payload
        return deck, state, ""

    def finish(self, deck: GameDeck, state: BaseModel, wren, transcript=()):
        del wren, transcript
        return deck, state, "", None


def _targets(raw: str, languages: list[str]) -> list[dict]:
    """Parse Wren's list. Grounding and the phrase-free stem and retry checks happen in the host."""
    payload = _object(raw)
    rows = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    targets = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        phrase, stem, retry, hint = (item.get(key) or "" for key in ("phrase", "stem", "retry_line", "hint"))
        if not all(isinstance(value, str) for value in (phrase, stem, retry, hint)):
            continue
        phrase = " ".join(phrase.split())
        stem = " ".join(stem.split())[:400]
        retry = " ".join(retry.split())[:200]
        hint = " ".join(hint.split())[:200]
        if not phrase or len(phrase) > 120 or not stem or not retry:
            continue
        ident = item.get("id") or ""
        if not isinstance(ident, str):
            ident = ""
        targets.append(
            {
                "id": ident.strip(),
                "phrase": phrase,
                "instruction": "",
                "hint": hint,
                "stem": stem,
                "retry_line": retry,
                "prompt_to_partner": "",
                "banned": [],
                "status": "pending",
                "gloss": gloss_of(item, languages),
            }
        )
    return targets


def _object(raw: str) -> dict:
    text = (raw or "").strip()
    start = text.find("{")
    if start < 0:
        return {}
    try:
        payload, _end = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
