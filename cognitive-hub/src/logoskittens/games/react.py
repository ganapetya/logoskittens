"""ReactGame. She says something with feeling. The user answers with a fitting reaction chunk from the text.

The stem carries an emotion for the avatar and a mimic token for the body (H8). The token passes the catalog
when it is delivered; one the catalog does not name is dropped and the line still plays.
"""

from logoskittens.games.deck_game import DeckGame, says_answer
from logoskittens.games.models import TurnExit


class ReactPlugin(DeckGame):
    id = "react"
    fields = ("instruction", "emotion", "mimic")

    def exit(self) -> TurnExit:
        return TurnExit(source="deck", local_check="contains", match="active", judge=True)

    def keep(self, target: dict) -> dict | None:
        if not target["instruction"] or says_answer(target["instruction"], target):
            return None
        return target
