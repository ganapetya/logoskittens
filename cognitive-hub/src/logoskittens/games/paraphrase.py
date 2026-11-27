"""ParaphraseChallengerGame. She says something plain. The user agrees in the text's own words.

The check is local with forms. Wren judges only a line the contains check missed.
"""

from logoskittens.games.deck_game import DeckGame, says_answer
from logoskittens.games.models import TurnExit


class ParaphrasePlugin(DeckGame):
    id = "paraphrase"
    fields = ("instruction", "hint")

    def exit(self) -> TurnExit:
        return TurnExit(source="deck", local_check="contains", match="active", judge=True)

    def keep(self, target: dict) -> dict | None:
        if not target["instruction"] or says_answer(target["instruction"], target):
            return None
        return target
