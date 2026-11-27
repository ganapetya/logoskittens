"""TabooGame. She asks about the text. The plain words on the card are banned; the user says the text's chunk.

A banned word buzzes with no attempt (`local_check: "banned"`). A clean line goes on to the contains check (H6).
"""

from logoskittens.games.deck_game import DeckGame, says_answer
from logoskittens.games.host import contains_phrase
from logoskittens.games.models import TurnExit

MAX_BANNED = 4


class TabooPlugin(DeckGame):
    id = "taboo"
    fields = ("instruction", "hint", "banned")

    def exit(self) -> TurnExit:
        return TurnExit(source="deck", local_check="banned", match="active")

    def keep(self, target: dict) -> dict | None:
        # A banned word inside the chunk would buzz the right answer. It is dropped, not the target.
        answers = [target["phrase"], *target.get("forms", [])]
        banned = [
            word
            for word in target["banned"]
            if len(word) <= 40 and not any(contains_phrase(answer, word) for answer in answers)
        ][:MAX_BANNED]
        instruction = target["instruction"]
        # The ban is on the card, in Wren's words. A card without it, or one that says the answer, is no card.
        if not banned or not instruction or says_answer(instruction, target):
            return None
        return target | {"banned": banned}
