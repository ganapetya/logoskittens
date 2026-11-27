"""Deck, manifest, and the turn decision. The turn graph does not write status."""

from typing import Annotated, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GameCapabilities(BaseModel):
    instruction: bool = False
    hint: bool = False
    exact_match: bool = False
    contains_match: bool = False
    hidden_steer: bool = False
    deck_line: bool = False
    async_score: bool = False
    remote_gate: bool = False
    withhold: bool = False
    buzzer: bool = False
    mimic: bool = False
    quest: bool = False
    end_score: bool = False
    finish: bool = False
    # Wren judges an answer the local check missed, before the line is chosen.
    judge: bool = False
    # H13. `local_check: "judge"`: Wren judges every turn, with no local short-circuit. A stem may hold the phrase.
    judge_only: bool = False


class GameOption(BaseModel):
    """One choice a game declares (H16), sent as `game_options` on select. CueCardGame's `cue_mode`."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=40)
    values: list[str] = Field(min_length=1, max_length=8)
    default: str
    # language id -> value -> label
    labels: dict[str, dict[str, str]] = Field(default_factory=dict)
    # Values offered only when the session has a target language (CueCardGame's `translation`).
    needs_targets: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _default_is_a_value(self) -> "GameOption":
        if self.default not in self.values:
            raise ValueError("option default is not one of its values")
        return self


class GameManifest(BaseModel):
    id: str
    phase: int
    listed: bool = True
    titles: dict[str, str]
    # H16. One line per source language for the game picker.
    summary: dict[str, str] = Field(default_factory=dict)
    # H16. What the game needs before it can start. Tags and the disabled reason come from this.
    requires: list[Literal["wren", "targets", "teacher_voice", "partner"]] = Field(default_factory=list)
    options: list[GameOption] = Field(default_factory=list)
    # H7. The partner's system prompt carries the passage whatever the card shows. `show_source` is the card only.
    partner_passage: bool = False
    # The game the Round over card suggests next (H12). Empty for none.
    next: str = ""
    # When the card offers the Read the text window. `play`: the whole round, for games whose answers are the
    # text's own words. `between`: only once the round is over, for games where hearing or rebuilding the text is
    # the exercise. The Raw material section offers it before Start for every game.
    read_text: Literal["play", "between"] = "between"
    # H9. Where the deck comes from. `local` builds it in the plugin with no remote call and no Wren prompt.
    # `history` gives the prepare graph this user's earlier targets in this language, each with its passage.
    prepare: Literal["wren", "local", "history"] = "wren"
    # H12. What a quest row shows before its target closes.
    quest_text: Literal["phrase", "instruction"] = "phrase"
    # H12. The page shows this game's buddy lines as `…` until their target closes.
    mask_lines: bool = False
    min_targets: int = Field(ge=1, le=12)
    max_targets: int = Field(ge=1, le=12)
    max_attempts: int = 0
    reveal_phrase: bool = False
    show_source: bool = False
    # H3. What a miss reveals. `each`: the phrase on every miss (Echo). `final`: only once the target
    # turns missed, the passage sentence when show_source is true, otherwise the phrase. `never`: nothing.
    reveal_on_miss: Literal["each", "final", "never"] = "final"
    # Where the judge's `why` reaches the miss note. `never`: the fixed notes (InterviewerGame). `miss`: every
    # judged miss (PlayDumbGame asks for the text's words). `final`: only the miss that closes the target
    # (AskBackGame's model question). The judge is told `last_try`, so it reveals only then.
    show_why: Literal["never", "miss", "final"] = "never"
    # H17. What speech recognition is biased toward. `expected`: the passage sentence that holds the
    # answer. `deck`: words from every target and stem, none only in the active phrase. `off`: no prompt.
    stt_bias: Literal["expected", "deck", "off"] = "expected"
    phrase_grounding: Literal["substring", "unchecked"] = "substring"
    # False: the game never calls the local partner model and ships no partner prompt.
    partner: bool = True
    opening: Literal["none", "partner", "stem", "phrase"] = "none"
    # The deck string a `source: "deck"` line speaks. `phrase` speaks the target itself (Echo).
    deck_text: Literal["stem", "phrase"] = "stem"
    # Spoken once when a deck-line turn retires the last target. {hits} and {total} are filled in.
    closing: dict[str, str] = Field(default_factory=dict)
    # The select error when grounding leaves too few targets twice, in place of the count (ReactGame).
    too_few: str = Field(default="", max_length=200)
    capabilities: GameCapabilities

    @model_validator(mode="after")
    def _range(self) -> "GameManifest":
        if self.min_targets > self.max_targets:
            raise ValueError("min_targets is above max_targets")
        if self.opening == "partner" and not self.partner:
            raise ValueError("a partner opening needs partner")
        return self


class TurnExit(BaseModel):
    """A decision. The turn graph does not call a model and does not write status."""

    line: str = ""
    emotion: str = "neutral"
    source: Literal["partner", "deck", "none"] = "none"
    withhold: bool = False
    buzzer: bool = False
    feedback: Literal["", "match", "miss", "hint", "buzzer", "score", "quiet"] = ""
    show_hint: bool = False
    schedule_wren: bool = False
    wren_user: str = ""
    remote_gate: bool = False
    local_check: Literal["", "exact", "contains", "banned", "judge"] = ""
    judge: bool = False
    match: Literal["active", "any"] = "active"
    prompt_suffix: str = ""
    mimic: str = ""
    finished: bool = False
    state: dict = Field(default_factory=dict)


class LeadLine(BaseModel):
    """H8. One line voiced before a target's stem. A `teacher` line is Savelij's, with role `teacher`."""

    model_config = ConfigDict(extra="forbid")

    speaker: Literal["buddy", "teacher"]
    line: str = Field(min_length=1, max_length=400)


class DeckTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    phrase: str = Field(min_length=1, max_length=120)
    instruction: str = Field(default="", max_length=300)
    hint: str = Field(default="", max_length=200)
    stem: str = Field(default="", max_length=400)
    retry_line: str = Field(default="", max_length=200)
    prompt_to_partner: str = Field(default="", max_length=400)
    banned: list[str] = Field(default_factory=list, max_length=24)
    status: Literal["pending", "active", "hit", "missed"] = "pending"
    # H2. Inflected or tense forms a learner may say. Not grounded. Matched with the same fold as phrase.
    forms: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(default_factory=list, max_length=6)
    # Target language code to a short translation of phrase (H14). Not grounded, not folded.
    gloss: dict[str, Annotated[str, Field(max_length=200)]] = Field(default_factory=dict, max_length=4)
    # H8. Lines voiced in order before the stem. Not grounded; a game may require the phrase in one of them.
    lead: list[LeadLine] = Field(default_factory=list, max_length=4)
    # H8. The stem's emotion and mimic token. The token still passes `keep_tokens` when it is delivered.
    emotion: str = Field(default="", max_length=40)
    mimic: str = Field(default="", max_length=40)
    # H9 `history`. Where an earlier target came from: the title of its source, for the card.
    origin: str = Field(default="", max_length=120)


class GameDeck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deck_version: int = 1
    game_id: str
    language: str
    material_id: str
    targets: list[DeckTarget] = Field(min_length=1, max_length=12)
    # H4. The round is over, by a finished turn or by Finish, even with targets still open.
    closed: bool = False


class CursorState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state_version: int = 1
    active_id: str
    attempts: dict[str, int] = Field(default_factory=dict)
    scoring_sentence_id: str = ""
    hint_on: bool = False
    pending_hint: str = ""


class RoleplayState(CursorState):
    """RoleplayGame. The round closes at this many human responses."""

    turn_cap: int = Field(default=12, ge=1, le=40)


class WrenFn(Protocol):
    def __call__(self, user: str, *, system: str = "") -> str: ...


class GamePlugin(Protocol):
    id: str

    def load_manifest(self) -> GameManifest:
        """Read config/games/{id}.json from disk."""

    def state_type(self) -> type[BaseModel]: ...

    def build_prepare_graph(self, wren: WrenFn): ...

    def build_turn_graph(self): ...

    def apply_wren(
        self, deck: GameDeck, state: BaseModel, payload: dict
    ) -> tuple[GameDeck, BaseModel, str]:
        """The str is wren_note. Writes status and attempts for a Wren result."""

    def finish(
        self, deck: GameDeck, state: BaseModel, wren: WrenFn, transcript: tuple = ()
    ) -> tuple[GameDeck, BaseModel, str, dict | None]:
        """H5. The str is wren_note; the dict is the score `finish_game` emits, or None.

        `transcript` is the stored lines as (speaker, text). Games 1–3 ignore it and do not call wren.
        """
