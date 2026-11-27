"""Shared fixtures for the phase 2 deck games (Stage G). The local partner is never called."""

import json

from logoskittens.persistence import Store
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete

SOURCE = (
    "Vi reiste til Norge i juli. "
    "Veien gikk gjennom lange tunneler. "
    "Om morgenen stoppet vi over en fjord. "
    "Vannet så nesten svart ut i skyggen. "
    "Jeg husker fortsatt den kalde luften. "
    "Om kvelden var vi helt utslitt."
)


class Wren:
    """Answers prepare with `deck`, and each judge call with the next verdict. No verdict left: the call fails."""

    def __init__(self, deck: dict, verdicts=None, why="Kort grunn."):
        self.deck = deck
        self.verdicts = list(verdicts or [])
        self.why = why
        self.calls: list[tuple[str, str]] = []

    def __call__(self, user: str, *, system: str = "", purpose: str = "", game_id: str = ""):
        del system, game_id
        self.calls.append((purpose, user))
        if purpose == "prepare":
            return json.dumps(self.deck)
        if purpose == "judge":
            if not self.verdicts:
                raise ValueError("judge down")
            return json.dumps({"hit": self.verdicts.pop(0), "why": self.why})
        raise AssertionError(f"unexpected Wren call {purpose}")

    def judged(self) -> list[str]:
        return [user for purpose, user in self.calls if purpose == "judge"]


def start(tmp_path, game_id: str, wren: Wren, targets=None):
    service = SessionService(Store(tmp_path / f"{game_id}.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.store.save_logoscat_material(
        "logoscat-41", logoscat_user_id=1, workspace_session_id=41, language="nb", title="Norgesferie", text=SOURCE
    )
    service.wren_fn = wren

    def complete(user, *, system, **kwargs):
        raise AssertionError("a phase 2 deck game does not call the local partner")

    service.complete_fn = complete
    session_id = service.select(
        "user-local", "nb", "logoscat-41", "lucas", game_id=game_id, target_languages=targets or []
    )
    return service, session_id


def turn(service, session_id, text):
    emitted: list[dict] = []
    service.perform_text(session_id, text, emitted.append)
    game = [item for item in emitted if item["type"] == "game"][0]
    actors = [item for item in emitted if item["type"] == "actor"]
    return game, actors


def stored(service, session_id, speaker):
    rows = json.loads(service.store.get_session_row(session_id).sentences_json)
    return [item for item in rows if item["speaker"] == speaker]


def deck_of(service, session_id) -> dict:
    return json.loads(service.store.get_session_row(session_id).deck_json)


def prompts_differ(game_id: str, roles=("wren",)) -> None:
    from pathlib import Path

    from logoskittens.games.host import load_game_prompt

    folder = Path(__file__).resolve().parents[1] / "config" / "prompts" / "games"
    for role in roles:
        english = (folder / f"{game_id}_{role}_en.md").read_text(encoding="utf-8")
        norsk = (folder / f"{game_id}_{role}_nb.md").read_text(encoding="utf-8")
        assert english.strip() != norsk.strip()
        assert load_game_prompt(game_id, role, "nb") == norsk
    if "partner" not in roles:
        assert not (folder / f"{game_id}_partner_nb.md").exists()
