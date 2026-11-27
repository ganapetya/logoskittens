"""AskBackGame. She says an answer from the text. The user asks the question the text answers with it.

The contains check cannot score a question, so Wren judges every turn (H13, `local_check: "judge"`). The
stem holds the answer on purpose. The miss that closes a target shows the judge's model question.
"""

from logoskittens.games.deck_game import DeckGame
from logoskittens.games.models import TurnExit


class AskBackPlugin(DeckGame):
    id = "ask_back"
    fields = ()

    def exit(self) -> TurnExit:
        return TurnExit(source="deck", local_check="judge", match="active")
