"""RoleplayGame. A scene from the text's theme. The partner stays in character; the user weaves the quest chunks in.

The first game that calls the local partner. It proves H1 (the partner sees the last 8 lines), H4 (a closed round
and the turn count), H5 (Finish with a score), and H7 (the partner sees the passage; the card does not).
"""

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from logoskittens.content import config_root
from logoskittens.games.host import forms_of, gloss_of, prepare_user
from logoskittens.games.models import GameDeck, GameManifest, RoleplayState, TurnExit


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
    turn: int
    exit: dict


class RoleplayPlugin:
    id = "roleplay"

    def load_manifest(self) -> GameManifest:
        path = config_root() / "games" / "roleplay.json"
        if not path.is_file():
            raise ValueError(path.name)
        return GameManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def state_type(self) -> type[BaseModel]:
        return RoleplayState

    def build_prepare_graph(self, wren):
        def prepare(state: _Prepare) -> dict:
            languages = list(state.get("target_languages") or [])
            raw = wren(
                prepare_user(state.get("raw_text") or "", state.get("rejection") or "", languages),
                system=state.get("wren_system") or "",
            )
            targets = scene_targets(raw, languages)
            return {
                "deck": {
                    "deck_version": 1,
                    "game_id": "roleplay",
                    "language": state.get("language_id") or "",
                    "material_id": state.get("material_id") or "",
                    "targets": targets,
                },
                "state": RoleplayState(active_id=targets[0]["id"] if targets else "t1").model_dump(),
            }

        graph = StateGraph(_Prepare)
        graph.add_node("prepare", prepare)
        graph.set_entry_point("prepare")
        graph.add_edge("prepare", END)
        return graph.compile()

    def build_turn_graph(self):
        def decide(state: _Turn) -> dict:
            cap = RoleplayState.model_validate(state.get("state") or {"active_id": "t1"}).turn_cap
            # The turn at the cap still speaks once, then the round is closed.
            finished = int(state.get("turn") or 0) >= cap
            decision = TurnExit(source="partner", local_check="contains", match="any", finished=finished)
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
        """No Wren. The score is the quest rows the user hit."""
        del wren, transcript
        hits = sum(1 for target in deck.targets if target.status == "hit")
        return deck, state, "", {"kind": "hits", "hit": hits, "total": len(deck.targets)}


def scene_targets(raw: str, languages: list[str]) -> list[dict]:
    """Wren's scene sentence goes onto every target's instruction, so the card keeps it whatever is active."""
    payload = _object(raw)
    scene = payload.get("scene") if isinstance(payload, dict) else ""
    rows = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(scene, str) or not scene.strip() or not isinstance(rows, list):
        return []
    scene = " ".join(scene.split())[:300]
    targets = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        phrase, steer = item.get("phrase") or "", item.get("prompt_to_partner") or ""
        if not isinstance(phrase, str) or not isinstance(steer, str):
            continue
        phrase = " ".join(phrase.split())
        steer = " ".join(steer.split())[:400]
        if not phrase or len(phrase) > 120 or not steer:
            continue
        ident = item.get("id") or ""
        targets.append(
            {
                "id": ident.strip() if isinstance(ident, str) else "",
                "phrase": phrase,
                "instruction": scene,
                "hint": "",
                "stem": "",
                "retry_line": "",
                "prompt_to_partner": steer,
                "banned": [],
                "status": "pending",
                "gloss": gloss_of(item, languages),
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
