"""WordOrderGame. The deck is built here from the passage, with no Wren call (H9 `local`).

The card shows the words of a sentence, folded and shuffled. She reads the sentence before it. The user says
the sentence in order. The match is exact.
"""

import random
from typing import TypedDict

from langgraph.graph import END, StateGraph
from pydantic import BaseModel

from logoskittens.content import config_root
from logoskittens.games.host import contains_phrase, fold
from logoskittens.games.models import CursorState, GameDeck, GameManifest, TurnExit
from logoskittens.talk import split_sentences

MIN_WORDS = 5
MAX_WORDS = 12
MAX_TARGETS = 6


class _Prepare(TypedDict, total=False):
    language_id: str
    material_id: str
    material_title: str
    raw_text: str
    seed: str
    deck: dict
    state: dict


class _Turn(TypedDict, total=False):
    heard: str
    deck: dict
    state: dict
    exit: dict


class WordOrderPlugin:
    id = "word_order"

    def load_manifest(self) -> GameManifest:
        path = config_root() / "games" / "word_order.json"
        if not path.is_file():
            raise ValueError(path.name)
        return GameManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def state_type(self) -> type[BaseModel]:
        return CursorState

    def build_prepare_graph(self, wren):
        del wren  # A local deck. The host hands this plugin a Wren function that refuses.

        def prepare(state: _Prepare) -> dict:
            targets = sentence_targets(
                state.get("raw_text") or "", state.get("material_title") or "", state.get("seed") or ""
            )
            return {
                "deck": {
                    "deck_version": 1,
                    "game_id": "word_order",
                    "language": state.get("language_id") or "",
                    "material_id": state.get("material_id") or "",
                    "targets": targets,
                },
                "state": CursorState(active_id=targets[0]["id"] if targets else "t1").model_dump(),
            }

        graph = StateGraph(_Prepare)
        graph.add_node("prepare", prepare)
        graph.set_entry_point("prepare")
        graph.add_edge("prepare", END)
        return graph.compile()

    def build_turn_graph(self):
        def decide(state: _Turn) -> dict:
            del state
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


def _words(sentence: str) -> list[str]:
    return [word for word in fold(sentence).split() if word]


def shuffled(sentence: str, seed: str) -> str:
    """The sentence's folded words in an order that is not the sentence's own, when that is possible."""
    words = _words(sentence)
    order = list(words)
    chooser = random.Random(seed)
    for _attempt in range(8):
        chooser.shuffle(order)
        if order != words:
            break
    return " / ".join(order)


def sentence_targets(raw_text: str, title: str, seed: str) -> list[dict]:
    """Sentences of 5 to 12 words, in text order, up to 6. The stem is the sentence before, or the title."""
    sentences = [part.strip() for part in split_sentences(raw_text or "") if part.strip()]
    targets: list[dict] = []
    for index, sentence in enumerate(sentences):
        count = len(_words(sentence))
        if not (MIN_WORDS <= count <= MAX_WORDS) or len(sentence) > 120:
            continue
        before = sentences[index - 1] if index > 0 else (title or "").strip()
        stem = " ".join(before.split())
        # The lead-in is spoken whole, as the stem and as the retry line, so it is never cut.
        if not stem or len(stem) > 200 or contains_phrase(stem, sentence):
            continue
        ident = f"t{len(targets) + 1}"
        targets.append(
            {
                "id": ident,
                "phrase": sentence,
                "instruction": shuffled(sentence, f"{seed}:{ident}")[:300],
                "hint": "",
                "stem": stem,
                "retry_line": stem,
                "prompt_to_partner": "",
                "banned": [],
                "status": "pending",
            }
        )
        if len(targets) == MAX_TARGETS:
            break
    return targets
