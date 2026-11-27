"""CueCardGame. The card and her line give a meaning. The user says the text's chunk. No judge: a synonym is the miss.

`cue_mode` comes from `game_options` at select. `meaning` cues in the source. `translation` cues with the gloss
in the first target (H14), and is offered only when the session has one.
"""

import json
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from logoskittens.content import config_root
from logoskittens.games.host import contains_phrase, forms_of, gloss_of, prepare_user
from logoskittens.games.models import CursorState, GameDeck, GameManifest, TurnExit


class CueState(CursorState):
    cue_mode: Literal["meaning", "translation"] = "meaning"


class _Prepare(TypedDict, total=False):
    language_id: str
    material_id: str
    raw_text: str
    game_id: str
    rejection: str
    target_languages: list
    game_options: dict
    wren_system: str
    partner_system: str
    deck: dict
    state: dict


class _Turn(TypedDict, total=False):
    heard: str
    deck: dict
    state: dict
    exit: dict


class CueCardPlugin:
    id = "cue_card"

    def load_manifest(self) -> GameManifest:
        path = config_root() / "games" / "cue_card.json"
        if not path.is_file():
            raise ValueError(path.name)
        return GameManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def state_type(self) -> type[BaseModel]:
        return CueState

    def build_prepare_graph(self, wren):
        def prepare(state: _Prepare) -> dict:
            languages = list(state.get("target_languages") or [])
            mode = cue_mode(state.get("game_options") or {}, languages)
            user = prepare_user(state.get("raw_text") or "", "", languages)
            user = f"{user}\n\ncue_mode: {mode}"
            if (state.get("rejection") or "").strip():
                user = f"{user}\n\n{state['rejection'].strip()}"
            raw = wren(user, system=state.get("wren_system") or "")
            targets = _targets(raw, languages, mode)
            return {
                "deck": {
                    "deck_version": 1,
                    "game_id": "cue_card",
                    "language": state.get("language_id") or "",
                    "material_id": state.get("material_id") or "",
                    "targets": targets,
                },
                "state": CueState(active_id=targets[0]["id"] if targets else "t1", cue_mode=mode).model_dump(),
            }

        graph = StateGraph(_Prepare)
        graph.add_node("prepare", prepare)
        graph.set_entry_point("prepare")
        graph.add_edge("prepare", END)
        return graph.compile()

    def build_turn_graph(self):
        def decide(state: _Turn) -> dict:
            del state
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


def cue_mode(options: dict, languages: list[str]) -> str:
    mode = options.get("cue_mode") if isinstance(options, dict) else ""
    if mode == "translation" and languages:
        return "translation"
    return "meaning"


def _targets(raw: str, languages: list[str], mode: str) -> list[dict]:
    """Parse Wren's list. In translation mode the card cue is the gloss in the first target."""
    payload = _object(raw)
    rows = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    targets = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        fields = [item.get(key) or "" for key in ("phrase", "instruction", "stem", "retry_line", "hint")]
        if not all(isinstance(value, str) for value in fields):
            continue
        phrase, instruction, stem, retry, hint = (" ".join(value.split()) for value in fields)
        if not phrase or len(phrase) > 120 or not stem or not retry:
            continue
        gloss = gloss_of(item, languages)
        if mode == "translation":
            instruction = gloss.get(languages[0], "")
        if not instruction or contains_phrase(instruction, phrase):
            # The card cue must be there, and must not be the answer.
            continue
        ident = item.get("id") or ""
        targets.append(
            {
                "id": ident.strip() if isinstance(ident, str) else "",
                "phrase": phrase,
                "instruction": instruction[:300],
                "hint": hint[:200],
                "stem": stem[:400],
                "retry_line": retry[:200],
                "prompt_to_partner": "",
                "banned": [],
                "status": "pending",
                "gloss": gloss,
                "forms": forms_of(item, phrase),
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
