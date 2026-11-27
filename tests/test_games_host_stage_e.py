"""Stage E: host changes for the remaining deck games. H2, H6, H9 local, H11, H12, H13."""

import json

import pytest

from logoskittens.games import echo_chamber
from logoskittens.games.echo_chamber import EchoPlugin
from logoskittens.games.host import check_exit, forms_of, game_message, listed_games
from logoskittens.games.models import CursorState, GameCapabilities, GameDeck, GameManifest, TurnExit
from logoskittens.games.registry import get_plugin, register
from logoskittens.persistence import Store
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete

from test_games_host import Scripted, _manifest, _target


MATERIAL = "norway_vacation_tunnels_fjords"


@pytest.fixture(autouse=True)
def _prompts(monkeypatch):
    monkeypatch.setattr(
        "logoskittens.games.host.load_game_prompt",
        lambda game_id, role, language_id: f"{game_id} {role} {language_id}",
    )


class Judge:
    def __init__(self, verdicts=()):
        self.verdicts = list(verdicts)
        self.calls: list[tuple[str, str]] = []

    def __call__(self, user: str, *, system: str = "", purpose: str = "", game_id: str = ""):
        del system, game_id
        self.calls.append((purpose, user))
        if purpose != "judge":
            return "{}"
        if not self.verdicts:
            raise ValueError("no verdict")
        return json.dumps({"hit": self.verdicts.pop(0), "why": "kort"})

    def judged(self) -> int:
        return sum(1 for purpose, _user in self.calls if purpose == "judge")


def _service(tmp_path, wren=None) -> SessionService:
    service = SessionService(Store(tmp_path / "stage_e.db"), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.wren_fn = wren
    return service


def _deck_game(manifest_id: str, caps: GameCapabilities, targets: list[dict], decision: TurnExit, **kwargs):
    manifest = _manifest(caps, id=manifest_id, max_attempts=kwargs.pop("max_attempts", 2), **kwargs)
    manifest = manifest.model_copy(update={"partner": False})
    plugin = Scripted(manifest, targets, decision)
    register(plugin)
    return plugin


def _turn(service, session_id, text):
    emitted: list[dict] = []
    service.perform_text(session_id, text, emitted.append)
    return [item for item in emitted if item["type"] == "game"][0], [item for item in emitted if item["type"] == "actor"]


def _deck(service, session_id) -> GameDeck:
    return GameDeck.model_validate_json(service.store.get_session_row(session_id).deck_json)


def test_a_form_hits_with_no_wren_call_and_the_judge_hears_the_forms(tmp_path):
    caps = GameCapabilities(contains_match=True, deck_line=True, judge=True)
    targets = [
        _target("tunneler", stem="Hva kjørte vi gjennom?", retry_line="Under fjellet?") | {"forms": ["tunnelene", "tunnel"]},
        _target("fjord", id="t2", stem="Hva så vi?", retry_line="Vann mellom fjell?"),
    ]
    _deck_game("forms_game", caps, targets, TurnExit(source="deck", local_check="contains", judge=True))
    judge = Judge(verdicts=[False])
    service = _service(tmp_path, judge)
    session_id = service.select("user-local", "en", MATERIAL, "peter", game_id="forms_game")
    game, actors = _turn(service, session_id, "Vi kjørte gjennom tunnelene.")
    assert game["feedback"] == "match"
    assert judge.judged() == 0
    assert _deck(service, session_id).targets[0].status == "hit"
    assert len(actors) == 1
    # A miss goes to the judge, which is told the forms too.
    _turn(service, session_id, "en innsjø")
    purpose, user = judge.calls[-1]
    assert purpose == "judge"
    assert "expected: fjord" in user


def test_forms_are_cleaned_and_a_stem_that_says_a_form_is_refused(tmp_path):
    assert forms_of({"forms": ["Tunnelene", "tunnelene!", "tunneler", "", 3, "x" * 121]}, "tunneler") == ["Tunnelene"]
    assert len(forms_of({"forms": [f"form {index}" for index in range(10)]})) == 6
    caps = GameCapabilities(contains_match=True, deck_line=True)
    targets = [
        _target("tunneler", stem="Vi kjørte gjennom tunnelene", retry_line="Igjen?") | {"forms": ["tunnelene"]},
        _target("fjord", id="t2", stem="Hva så vi?", retry_line="Vann?"),
    ]
    _deck_game("form_stem", caps, targets, TurnExit(source="deck", local_check="contains"), min_targets=1)
    service = _service(tmp_path, Judge())
    session_id = service.select("user-local", "en", MATERIAL, "peter", game_id="form_stem")
    assert [target.phrase for target in _deck(service, session_id).targets] == ["fjord"]
    # A deck stored before forms existed still validates, with no forms.
    old = GameDeck.model_validate(
        {"game_id": "x", "language": "nb", "material_id": "m", "targets": [{"id": "t1", "phrase": "fjord"}]}
    )
    assert old.targets[0].forms == []


def test_a_banned_word_buzzes_and_a_clean_line_with_the_phrase_is_a_hit(tmp_path):
    caps = GameCapabilities(contains_match=True, deck_line=True, buzzer=True, withhold=True, hint=True)
    targets = [
        _target("den kalde luften", stem="Hva kjente vi?", retry_line="Fra isbreen?", banned=["kald"], hint="Den ..."),
        _target("fjord", id="t2", stem="Hva så vi så?", retry_line="Vann?"),
    ]
    _deck_game("taboo_like", caps, targets, TurnExit(source="deck", local_check="banned"))
    service = _service(tmp_path, Judge())
    session_id = service.select("user-local", "en", MATERIAL, "peter", game_id="taboo_like")
    game, actors = _turn(service, session_id, "Det var kald vind")
    assert game["buzzer"] is True and game["feedback"] == "buzzer" and game["withheld"] is True
    assert actors == []
    state = CursorState.model_validate_json(service.store.get_session_row(session_id).game_state_json)
    assert state.attempts == {}
    game, actors = _turn(service, session_id, "Vi kjente bare noe frisk")
    assert game["feedback"] == "miss" and game["hint"] == "Den ..."
    assert len(actors) == 1
    game, actors = _turn(service, session_id, "Vi kjente den kalde luften")
    assert game["feedback"] == "match"
    rows = json.loads(service.store.get_session_row(session_id).sentences_json)
    assert rows[-1] == {**rows[-1], "speaker": "buddy", "text": "Hva så vi så?"}


def test_a_local_game_lists_and_starts_with_wren_off_and_a_wren_game_refuses(tmp_path):
    caps = GameCapabilities(exact_match=True, deck_line=True)
    targets = [_target("fjord", stem="Si det.", retry_line="Igjen.")]
    local = _deck_game("local_game", caps, targets, TurnExit(source="deck", local_check="exact"))
    local.manifest = local.manifest.model_copy(update={"prepare": "local", "listed": True})
    remote = _deck_game("remote_game", caps, targets, TurnExit(source="deck", local_check="exact"))
    remote.manifest = remote.manifest.model_copy(update={"listed": True})
    # A Wren-prepared plugin asks Wren for its deck. With Wren off that call is skipped and select refuses.
    remote.calls_wren = True
    service = _service(tmp_path, wren=None)
    rows = {item["id"]: item for item in listed_games("en", ready=False)}
    assert rows["local_game"]["available"] is True
    assert rows["remote_game"]["available"] is False and rows["remote_game"]["reason"] == "Wren is off"
    session_id = service.select("user-local", "en", MATERIAL, "peter", game_id="local_game")
    assert _deck(service, session_id).game_id == "local_game"
    with pytest.raises(ValueError, match="Wren is not available"):
        service.select("user-local", "en", MATERIAL, "peter", game_id="remote_game")
    # A local plugin that reached for Wren anyway is stopped before any call.
    local.calls_wren = True
    with pytest.raises(ValueError, match="Wren is not available"):
        service.select("user-local", "en", MATERIAL, "peter", game_id="local_game")


def test_a_second_manifest_id_on_echo_stores_decks_under_that_id(tmp_path, monkeypatch):
    root = tmp_path / "config"
    (root / "games").mkdir(parents=True)
    shipped = json.loads(EchoPlugin().load_manifest().model_dump_json())
    (root / "games" / "echo_variant.json").write_text(
        json.dumps({**shipped, "id": "echo_variant", "listed": False}), encoding="utf-8"
    )
    monkeypatch.setattr(echo_chamber, "config_root", lambda: root)
    register(EchoPlugin, "echo_variant")
    with pytest.raises(ValueError):
        register(EchoPlugin(), "another_id")
    assert get_plugin("echo_variant").id == "echo_variant"
    assert get_plugin("echo_variant").load_manifest().id == "echo_variant"
    lines = ["The fjords were deep.", "The tunnels were long.", "The ferries were slow.", "The goats were loud."]
    service = _service(
        tmp_path,
        lambda user, *, system="", purpose="", game_id="": json.dumps(
            {"targets": [{"phrase": line} for line in lines]}
        ),
    )
    service.store.save_logoscat_material(
        "logoscat-3", logoscat_user_id=1, workspace_session_id=3, language="en", title="Lines", text=" ".join(lines)
    )
    session_id = service.select("user-local", "en", "logoscat-3", "peter", game_id="echo_variant")
    row = service.store.get_session_row(session_id)
    assert row.game_id == "echo_variant"
    assert json.loads(row.deck_json)["game_id"] == "echo_variant"
    game, _actors = _turn(service, session_id, "The fjords were deep.")
    assert game["game_id"] == "echo_variant" and game["feedback"] == "match"


def test_a_judge_only_exit_calls_the_judge_on_every_turn(tmp_path):
    caps = GameCapabilities(deck_line=True, judge_only=True)
    targets = [
        _target("fjord", stem="Spør meg om fjord.", retry_line="Still et spørsmål.") ,
        _target("ferje", id="t2", stem="Spør meg om ferja.", retry_line="Et spørsmål til?"),
    ]
    _deck_game("ask_like", caps, targets, TurnExit(source="deck", local_check="judge"))
    judge = Judge(verdicts=[False, True])
    service = _service(tmp_path, judge)
    session_id = service.select("user-local", "en", MATERIAL, "peter", game_id="ask_like")
    # The stem holds the phrase, and grounding kept it for this check.
    assert _deck(service, session_id).targets[0].stem == "Spør meg om fjord."
    game, _actors = _turn(service, session_id, "fjord")
    assert judge.judged() == 1 and game["feedback"] == "miss"
    game, _actors = _turn(service, session_id, "Hvor dyp er fjorden?")
    assert judge.judged() == 2 and game["feedback"] == "match"
    # A failed judge call is a miss.
    game, _actors = _turn(service, session_id, "Hvor går ferja?")
    assert judge.judged() == 3 and game["feedback"] == "miss"
    with pytest.raises(ValueError, match="game flag judge_only"):
        check_exit(TurnExit(local_check="judge"), _manifest(GameCapabilities(judge=True)))
    check_exit(TurnExit(local_check="judge"), _manifest(GameCapabilities(judge_only=True)))


def test_card_options_ride_on_the_game_message():
    deck = GameDeck(
        game_id="listen_like",
        language="nb",
        material_id="m",
        targets=[
            {"id": "t1", "phrase": "Jeg er sliten.", "instruction": "Si det du hørte.", "status": "hit"},
            {"id": "t2", "phrase": "Veien var lang.", "instruction": "Si det du hørte.", "status": "active"},
            {"id": "t3", "phrase": "Vannet var kaldt.", "instruction": "Si det du hørte.", "status": "pending"},
        ],
    )
    manifest = GameManifest.model_validate(
        {
            **_manifest(GameCapabilities(quest=True, deck_line=True)).model_dump(),
            "deck_text": "phrase",
            "quest_text": "instruction",
            "mask_lines": True,
            "next": "word_order",
        }
    )
    message = game_message(
        session_id="s", manifest=manifest, deck=deck, decision=TurnExit(), qa=False, steer="", finished=False
    )
    assert [row["text"] for row in message["quest"]] == ["Jeg er sliten.", "Si det du hørte.", "Si det du hørte."]
    assert message["mask_lines"] is True
    assert message["masked_lines"] == ["Veien var lang."]
    assert message["next"] == "word_order"
    plain = game_message(
        session_id="s",
        manifest=_manifest(GameCapabilities(quest=True)),
        deck=deck,
        decision=TurnExit(),
        qa=False,
        steer="",
        finished=False,
    )
    assert plain["mask_lines"] is False and plain["masked_lines"] == []
    assert [row["text"] for row in plain["quest"]] == ["Jeg er sliten.", "Veien var lang.", "Vannet var kaldt."]


@pytest.mark.parametrize(
    "game_id,heard,deck",
    [
        ("echo_chamber", "Jeg er sliten.", {"phrase": "Jeg er sliten.", "instruction": "Si det."}),
        ("interviewer", "Italia", {"phrase": "Italia", "stem": "Hvor?", "retry_line": "Hvilket land?"}),
        ("fill_blank", "lange tunneler", {"phrase": "lange tunneler", "stem": "Vi kjørte gjennom", "retry_line": "Igjen?", "hint": "lange"}),
    ],
)
def test_decks_stored_before_this_stage_still_load_and_play(tmp_path, game_id, heard, deck):
    service = _service(tmp_path, Judge())
    old = {
        "deck_version": 1,
        "game_id": game_id,
        "language": "nb",
        "material_id": MATERIAL,
        "targets": [
            {"id": "t1", "status": "active", **deck},
            {"id": "t2", "phrase": "fjord", "stem": "Hva?", "retry_line": "Igjen?", "status": "pending"},
        ],
    }
    service.store.create_session(
        "sess-old",
        "talking_game",
        {},
        language_id="nb",
        topic_id="talking_game",
        material_id=MATERIAL,
        personality_id="lucas",
        game_id=game_id,
        deck_json=json.dumps(old),
        game_state_json=json.dumps({"state_version": 1, "active_id": "t1"}),
    )
    game, actors = _turn(service, "sess-old", heard)
    assert game["feedback"] == "match"
    assert len(actors) == 1
