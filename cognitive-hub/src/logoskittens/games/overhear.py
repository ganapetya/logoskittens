"""OverhearGame. Savelij and the buddy talk about the text, two to four lines. Then she asks what you heard.

The lead lines are voiced before each stem (H8), Savelij's through role `teacher`. The answer must be heard:
the phrase is in one lead line. A retry replays that line, then asks again.
"""

from logoskittens.games.deck_game import DeckGame
from logoskittens.games.host import contains_phrase
from logoskittens.games.models import TurnExit


class OverhearPlugin(DeckGame):
    id = "overhear"
    fields = ("lead",)

    def exit(self) -> TurnExit:
        return TurnExit(source="deck", local_check="contains", match="active", judge=True)

    def keep(self, target: dict) -> dict | None:
        lead = target["lead"]
        if not (2 <= len(lead) <= 4):
            return None
        if not any(item["speaker"] == "teacher" for item in lead):
            return None
        if not any(contains_phrase(item["line"], target["phrase"]) for item in lead):
            return None
        return target
