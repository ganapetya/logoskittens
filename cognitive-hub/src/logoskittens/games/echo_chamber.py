"""EchoChamberGame. Wren picks the lines at prepare. The turn match is local."""

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from logoskittens.content import config_root
from logoskittens.games.host import forms_of, gloss_of, prepare_user
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


class EchoPlugin:
    """Also registered under other manifest ids (H11). Each reads and stamps the id it was registered with."""

    def __init__(self, manifest_id: str = "echo_chamber"):
        self.id = manifest_id

    def load_manifest(self) -> GameManifest:
        path = config_root() / "games" / f"{self.id}.json"
        if not path.is_file():
            raise ValueError(path.name)
        return GameManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def state_type(self) -> type[BaseModel]:
        return CursorState

    def build_prepare_graph(self, wren):
        game_id = self.id

        def prepare(state: _Prepare) -> dict:
            languages = list(state.get("target_languages") or [])
            raw = wren(
                prepare_user(state.get("raw_text") or "", state.get("rejection") or "", languages),
                system=state.get("wren_system") or "",
            )
            targets = _targets(raw, languages)
            active = targets[0]["id"] if targets and targets[0]["id"] else "t1"
            deck = {
                "deck_version": 1,
                "game_id": game_id,
                "language": state.get("language_id") or "",
                "material_id": state.get("material_id") or "",
                "targets": targets,
            }
            return {
                "deck": deck,
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
            # Every line she says is a deck string: the next phrase, the same phrase again, or the closing.
            decision = TurnExit(source="deck", local_check="exact", match="active")
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
    text = (raw or "").strip()
    start = text.find("{")
    if start < 0:
        return []
    try:
        payload, _end = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError:
        return []
    rows = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    targets = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        phrase = item.get("phrase") or ""
        if not isinstance(phrase, str):
            continue
        phrase = " ".join(phrase.split())
        if not phrase or len(phrase) > 120:
            continue
        instruction = item.get("instruction") or ""
        if not isinstance(instruction, str):
            instruction = ""
        instruction = " ".join(instruction.split())[:300]
        ident = item.get("id") or ""
        if not isinstance(ident, str):
            ident = ""
        targets.append(
            {
                "id": ident.strip(),
                "phrase": phrase,
                "instruction": instruction,
                "hint": "",
                "stem": "",
                "retry_line": "",
                "prompt_to_partner": "",
                "banned": [],
                "status": "pending",
                "gloss": gloss_of(item, languages),
                "forms": forms_of(item),
            }
        )
    return targets
