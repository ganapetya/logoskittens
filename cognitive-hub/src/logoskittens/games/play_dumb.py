"""PlayDumbGame. Each of her lines gets one fact of the passage wrong. The user corrects her with the text's chunk.

Every line is a deck string. Wren judges a correction the contains check missed, and its `why` asks for the
text's words (manifest `show_why: miss`).
"""

from logoskittens.games.deck_game import DeckGame
from logoskittens.games.models import TurnExit


class PlayDumbPlugin(DeckGame):
    id = "play_dumb"
    fields = ()

    def exit(self) -> TurnExit:
        return TurnExit(source="deck", local_check="contains", match="active", judge=True)
