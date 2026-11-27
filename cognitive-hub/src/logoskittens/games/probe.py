"""Unlisted host probe. Instruction only. It does not call Wren or the partner."""

from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel, ConfigDict

from logoskittens.content import config_root
from logoskittens.games.models import GameDeck, GameManifest, TurnExit


class ProbeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_version: int = 1


class _Prepare(TypedDict, total=False):
    language_id: str
    material_id: str
    deck: dict
    state: dict


class _Turn(TypedDict, total=False):
    deck: dict
    exit: dict


class ProbePlugin:
    id = "probe"

    def load_manifest(self) -> GameManifest:
        path = config_root() / "games" / "probe.json"
        if not path.is_file():
            raise ValueError(path.name)
        return GameManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def state_type(self) -> type[BaseModel]:
        return ProbeState

    def build_prepare_graph(self, wren):
        del wren

        def prepare(state: _Prepare) -> dict:
            deck = GameDeck(
                game_id="probe",
                language=state.get("language_id") or "en",
                material_id=state.get("material_id") or "",
                targets=[
                    {
                        "id": "t1",
                        "phrase": "probe",
                        "instruction": "Probe.",
                        "status": "pending",
                    }
                ],
            )
            return {"deck": deck.model_dump(), "state": ProbeState().model_dump()}

        graph = StateGraph(_Prepare)
        graph.add_node("prepare", prepare)
        graph.set_entry_point("prepare")
        graph.add_edge("prepare", END)
        return graph.compile()

    def build_turn_graph(self):
        def decide(state: _Turn) -> dict:
            del state
            return {"exit": TurnExit(source="none").model_dump()}

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
