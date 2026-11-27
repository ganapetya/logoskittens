"""A Wren-prepared deck game with a fixed turn decision. The phase 2 deck games are thin subclasses.

The subclass names its id, its `TurnExit`, and which card fields Wren may fill. Grounding, forms, the
phrase-free stem and retry checks, and the hint rule happen in the host (`_ground`).
"""

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from logoskittens.content import config_root
from logoskittens.games.host import contains_phrase, forms_of, gloss_of, prepare_user
from logoskittens.games.models import CursorState, GameDeck, GameManifest, TurnExit


class _Prepare(TypedDict, total=False):
    language_id: str
    material_id: str
    raw_text: str
    history: list
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


class DeckGame:
    id = ""
    # Card fields Wren writes for this game. The others are stored empty.
    fields: tuple[str, ...] = ()

    def exit(self) -> TurnExit:
        raise NotImplementedError

    def keep(self, target: dict) -> dict | None:
        """A game's own check on one parsed target. None drops it."""
        return target

    def user_message(self, state: dict, languages: list[str]) -> str:
        """What Wren reads. The passage, the glosses paragraph, and a rejection."""
        return prepare_user(state.get("raw_text") or "", state.get("rejection") or "", languages)

    def adjust(self, targets: list[dict], state: dict) -> list[dict]:
        """The whole list after `keep`. ReviewGame names each chunk's source here."""
        del state
        return targets

    def load_manifest(self) -> GameManifest:
        path = config_root() / "games" / f"{self.id}.json"
        if not path.is_file():
            raise ValueError(path.name)
        return GameManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def state_type(self) -> type[BaseModel]:
        return CursorState

    def build_prepare_graph(self, wren):
        def prepare(state: _Prepare) -> dict:
            languages = list(state.get("target_languages") or [])
            raw = wren(self.user_message(dict(state), languages), system=state.get("wren_system") or "")
            targets = [kept for item in deck_rows(raw, languages, self.fields) if (kept := self.keep(item))]
            targets = self.adjust(targets, dict(state))
            active = targets[0]["id"] if targets and targets[0]["id"] else "t1"
            return {
                "deck": {
                    "deck_version": 1,
                    "game_id": self.id,
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
        decision = self.exit().model_dump()

        def decide(state: _Turn) -> dict:
            del state
            return {"exit": dict(decision)}

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


LIMITS = {"instruction": 300, "hint": 200}


def deck_rows(raw: str, languages: list[str], fields: tuple[str, ...]) -> list[dict]:
    """Parse Wren's list into deck targets. A row needs a phrase, a stem, and a retry line."""
    payload = _object(raw)
    rows = payload.get("targets") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return []
    targets = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        text_fields = [key for key in ("phrase", "stem", "retry_line", *fields) if key not in {"banned", "lead"}]
        values = {key: item.get(key) or "" for key in text_fields}
        if not all(isinstance(value, str) for value in values.values()):
            continue
        values = {key: " ".join(value.split()) for key, value in values.items()}
        phrase = values["phrase"]
        if not phrase or len(phrase) > 120 or not values["stem"] or not values["retry_line"]:
            continue
        banned = item.get("banned") if "banned" in fields else []
        ident = item.get("id") or ""
        targets.append(
            {
                "id": ident.strip() if isinstance(ident, str) else "",
                "phrase": phrase,
                "instruction": values.get("instruction", "")[: LIMITS["instruction"]],
                "hint": values.get("hint", "")[: LIMITS["hint"]],
                "stem": values["stem"][:400],
                "retry_line": values["retry_line"][:200],
                "prompt_to_partner": "",
                "banned": [" ".join(word.split()) for word in banned if isinstance(word, str) and word.strip()]
                if isinstance(banned, list)
                else [],
                "status": "pending",
                "gloss": gloss_of(item, languages),
                "forms": forms_of(item, phrase),
                "lead": lead_of(item) if "lead" in fields else [],
                "emotion": values.get("emotion", "")[:40],
                "mimic": values.get("mimic", "")[:40],
            }
        )
    return targets


def lead_of(item: dict) -> list[dict]:
    """H8. Up to 4 `{speaker, line}` rows, `buddy` or `teacher`. A malformed row is skipped."""
    rows = item.get("lead")
    if not isinstance(rows, list):
        return []
    lead = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        speaker, line = row.get("speaker"), row.get("line")
        if speaker not in {"buddy", "teacher"} or not isinstance(line, str) or not line.strip():
            continue
        lead.append({"speaker": speaker, "line": " ".join(line.split())[:400]})
    return lead[:4]


def says_answer(text: str, target: dict) -> bool:
    """The phrase or one of its forms is in this card text."""
    return any(contains_phrase(text, item) for item in [target["phrase"], *target.get("forms", [])] if item)


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
