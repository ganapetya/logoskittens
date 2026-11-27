"""ReviewGame. Chunks missed in earlier rounds, then hits older than 3 days, come back as cue cards (H9 `history`).

The host reads the history and hands it to prepare. Wren writes a cue for each chunk. The panel's material is not
read. Each target keeps the title of its source as `origin`, for the card.
"""

from logoskittens.games.deck_game import DeckGame, says_answer
from logoskittens.games.host import fold, prepare_user
from logoskittens.games.models import TurnExit


class ReviewPlugin(DeckGame):
    id = "review"
    fields = ("instruction", "hint")

    def exit(self) -> TurnExit:
        return TurnExit(source="deck", local_check="contains", match="active")

    def keep(self, target: dict) -> dict | None:
        if not target["instruction"] or says_answer(target["instruction"], target):
            return None
        return target

    def user_message(self, state: dict, languages: list[str]) -> str:
        return prepare_user(review_listing(state.get("history") or []), state.get("rejection") or "", languages)

    def adjust(self, targets: list[dict], state: dict) -> list[dict]:
        """Keep only chunks from the history, in its order, each named with its source."""
        history = {fold(item["phrase"]): item for item in state.get("history") or []}
        order = list(history)
        kept = []
        for target in targets:
            entry = history.get(fold(target["phrase"]))
            if entry is None:
                continue
            forms = list(dict.fromkeys([*target.get("forms", []), *entry.get("forms", [])]))[:6]
            kept.append(target | {"phrase": entry["phrase"], "origin": entry["origin"], "forms": forms})
        kept.sort(key=lambda target: order.index(fold(target["phrase"])))
        return kept


def review_listing(history: list[dict]) -> str:
    """The chunks, each with its status and source, then each source passage once."""
    lines = ["chunks:"]
    for index, item in enumerate(history, start=1):
        lines.append(f"{index}. phrase: {item['phrase']}")
        lines.append(f"   status: {item['status']}")
        lines.append(f"   source: {item['origin']}")
    lines.append("")
    lines.append("passages:")
    shown: list[str] = []
    for item in history:
        if item["origin"] in shown:
            continue
        shown.append(item["origin"])
        lines.append(f"[{item['origin']}]")
        lines.append(item["passage"].strip())
        lines.append("")
    return "\n".join(lines).strip()
