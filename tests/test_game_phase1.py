"""Stage F: ListenGame, WordOrderGame, and CueCardGame. Phase 1 then holds six games, linked by `next`."""

import json
from pathlib import Path

import pytest

from logoskittens.games.cue_card import cue_mode
from logoskittens.games.host import listed_games, load_game_prompt
from logoskittens.games.word_order import sentence_targets, shuffled
from logoskittens.persistence import Store
from logoskittens.session import SessionService

from fakes import FakeAudio, fake_complete

ROOT = Path(__file__).resolve().parents[1]

SOURCE = (
    "Vi reiste til Norge i juli. "
    "Veien gikk gjennom mange lange tunneler. "
    "Om morgenen stoppet vi over en fjord. "
    "Jeg husker fortsatt den kalde luften der. "
    "Etterpå var vi helt utslitt etter turen."
)

LISTEN_LINES = [
    "Veien gikk gjennom mange lange tunneler.",
    "Om morgenen stoppet vi over en fjord.",
    "Jeg husker fortsatt den kalde luften der.",
    "Etterpå var vi helt utslitt etter turen.",
]

# phrase, forms, instruction, stem, retry_line, hint, gloss
CUES = [
    ("lange tunneler", ["lang tunnel", "den lange tunnelen"], "Veier inne i fjellet som ikke tar slutt.",
     "Hvordan sier teksten «veier inne i fjellet»?", "Prøv igjen: l… t…", "lange", "long tunnels"),
    ("den kalde luften", ["kald luft"], "Det du puster inn når det er vinter.",
     "Hvordan sier teksten «vinterpust»?", "Prøv igjen: d… k… l…", "den", "the cold air"),
    ("helt utslitt", [], "Veldig, veldig trøtt.",
     "Hvordan sier teksten «veldig trøtt»?", "Prøv igjen: h… u…", "helt", "completely worn out"),
    ("over en fjord", [], "Høyt over vannet mellom fjellene.",
     "Hvor stoppet vi?", "Prøv igjen: o… e… f…", "over", "above a fjord"),
]


class Wren:
    def __init__(self, payload: str):
        self.payload = payload
        self.calls: list[tuple[str, str]] = []

    def __call__(self, user: str, *, system: str = "", purpose: str = "", game_id: str = ""):
        del system, game_id
        self.calls.append((purpose, user))
        return self.payload


def _listen_deck() -> str:
    return json.dumps(
        {
            "targets": [
                {"id": f"t{index}", "phrase": line, "instruction": "Si det hun sa."}
                for index, line in enumerate(LISTEN_LINES, start=1)
            ]
        }
    )


def _cue_deck() -> str:
    return json.dumps(
        {
            "targets": [
                {
                    "id": f"t{index}",
                    "phrase": phrase,
                    "forms": forms,
                    "instruction": instruction,
                    "stem": stem,
                    "retry_line": retry,
                    "hint": hint,
                    "gloss": {"en": gloss},
                }
                for index, (phrase, forms, instruction, stem, retry, hint, gloss) in enumerate(CUES, start=1)
            ]
        }
    )


def _service(tmp_path, wren=None, name="phase1.db") -> SessionService:
    service = SessionService(Store(tmp_path / name), FakeAudio(), fake_complete)  # type: ignore[arg-type]
    service.store.save_logoscat_material(
        "logoscat-31", logoscat_user_id=1, workspace_session_id=31, language="nb", title="Norgesferie", text=SOURCE
    )
    service.wren_fn = wren

    def complete(user, *, system, **kwargs):
        raise AssertionError("phase 1 deck games do not call the local partner")

    service.complete_fn = complete
    return service


def _turn(service, session_id, text):
    emitted: list[dict] = []
    service.perform_text(session_id, text, emitted.append)
    return [item for item in emitted if item["type"] == "game"][0]


def _stored(service, session_id, speaker):
    rows = json.loads(service.store.get_session_row(session_id).sentences_json)
    return [item for item in rows if item["speaker"] == speaker]


def test_phase_one_lists_six_games_in_the_progression_order():
    for language in ("en", "nb"):
        rows = {item["id"]: item for item in listed_games(language) if item["phase"] == 1}
        assert set(rows) == {"listen", "echo_chamber", "word_order", "cue_card", "fill_blank", "interviewer"}
    chain = ["listen", "echo_chamber", "word_order", "cue_card", "fill_blank", "interviewer"]
    rows = {item["id"]: item for item in listed_games("nb")}
    for here, there in zip(chain, chain[1:]):
        assert rows[here]["next"] == there
    assert {item["id"]: item for item in listed_games("nb")}["word_order"]["title"] == "OrdstillingGame"


@pytest.mark.parametrize("game_id", ["listen", "cue_card"])
def test_wren_prompts_are_written_per_language(game_id):
    games = ROOT / "config" / "prompts" / "games"
    english = (games / f"{game_id}_wren_en.md").read_text(encoding="utf-8")
    norsk = (games / f"{game_id}_wren_nb.md").read_text(encoding="utf-8")
    assert english.strip() != norsk.strip()
    assert load_game_prompt(game_id, "wren", "nb") == norsk
    assert not (games / f"{game_id}_partner_nb.md").exists()
    assert not (games / "word_order_wren_nb.md").exists()


def test_listen_masks_the_open_line_and_a_miss_carries_the_expected_line(tmp_path):
    wren = Wren(_listen_deck())
    service = _service(tmp_path, wren)
    session_id = service.select("user-local", "nb", "logoscat-31", "lucas", game_id="listen")
    described = service.describe(session_id)["game"]
    # The line was spoken, and is hidden on the page until the target closes.
    assert described["masked_lines"] == [LISTEN_LINES[0]]
    assert described["phrase"] == ""
    assert described["instruction"] == "Si det hun sa."
    game = _turn(service, session_id, "Veien gikk gjennom mange tunneler.")
    assert game["feedback"] == "miss"
    # reveal_on_miss each: the first miss names the line, so the page draws the word diff.
    assert game["miss_note"]["expected"] == LISTEN_LINES[0]
    assert _stored(service, session_id, "human")[-1]["expected"] == LISTEN_LINES[0]
    game = _turn(service, session_id, LISTEN_LINES[0])
    assert game["feedback"] == "match"
    assert game["masked_lines"] == [LISTEN_LINES[1]]
    assert [purpose for purpose, _user in wren.calls] == ["prepare"]
    # Listen stores its deck under its own id, on Echo's plugin.
    assert json.loads(service.store.get_session_row(session_id).deck_json)["game_id"] == "listen"


def test_word_order_builds_its_deck_locally_and_starts_with_wren_off(tmp_path):
    service = _service(tmp_path, wren=None)
    rows = {item["id"]: item for item in service.catalog("user-local", "nb")["games"]}
    assert rows["word_order"]["available"] is True
    assert rows["cue_card"]["available"] is False
    session_id = service.select("user-local", "nb", "logoscat-31", "lucas", game_id="word_order")
    deck = json.loads(service.store.get_session_row(session_id).deck_json)
    phrases = [target["phrase"] for target in deck["targets"]]
    assert phrases == ["Vi reiste til Norge i juli.", *LISTEN_LINES]
    # The stem is the sentence before, or the title for the first. The opening is the first stem.
    assert deck["targets"][0]["stem"] == "Norgesferie"
    assert deck["targets"][1]["stem"] == "Vi reiste til Norge i juli."
    assert _stored(service, session_id, "buddy")[0]["text"] == "Norgesferie"
    chips = service.describe(session_id)["game"]["instruction"].split(" / ")
    assert sorted(chips) == sorted("vi reiste til norge i juli".split())
    assert chips != "vi reiste til norge i juli".split()


def test_word_order_wrong_order_is_a_miss_with_the_expected_sentence(tmp_path):
    service = _service(tmp_path, wren=None)
    session_id = service.select("user-local", "nb", "logoscat-31", "lucas", game_id="word_order")
    # Every word is there, in the wrong order.
    game = _turn(service, session_id, "Vi reiste i juli til Norge.")
    assert game["feedback"] == "miss"
    assert game["miss_note"]["expected"] == "Vi reiste til Norge i juli."
    game = _turn(service, session_id, "Vi reiste til Norge i juli")
    assert game["feedback"] == "match"
    _turn(service, session_id, LISTEN_LINES[0])
    # Verb-second: "Om morgenen vi stoppet" has every word and breaks V2.
    game = _turn(service, session_id, "Om morgenen vi stoppet over en fjord.")
    assert game["feedback"] == "miss"
    assert game["miss_note"]["expected"] == LISTEN_LINES[1]


def test_word_order_sentences_are_bounded_and_the_shuffle_is_stable():
    long = "Dette er en setning med altfor mange ord til at den kan brukes i spillet i dag."
    text = f"Kort. {long} Vi spiste middag sammen ved vannet."
    targets = sentence_targets(text, "Tittel", "seed")
    assert [target["phrase"] for target in targets] == ["Vi spiste middag sammen ved vannet."]
    assert shuffled("Vi spiste middag sammen ved vannet.", "a") == shuffled("Vi spiste middag sammen ved vannet.", "a")
    assert "/" not in targets[0]["phrase"]
    # A text whose first sentence fits takes the title as its lead-in.
    first = sentence_targets("Vi spiste middag sammen ved vannet.", "Ferien", "s")
    assert first[0]["stem"] == "Ferien"


def test_cue_card_hits_a_form_with_no_wren_call_and_a_synonym_misses(tmp_path):
    wren = Wren(_cue_deck())
    service = _service(tmp_path, wren)
    session_id = service.select("user-local", "nb", "logoscat-31", "lucas", game_id="cue_card")
    described = service.describe(session_id)["game"]
    assert described["instruction"] == "Veier inne i fjellet som ikke tar slutt."
    assert "lange tunneler" not in json.dumps(described)
    game = _turn(service, session_id, "Vi kjørte gjennom den lange tunnelen.")
    assert game["feedback"] == "match"
    game = _turn(service, session_id, "den kjølige luften")
    assert game["feedback"] == "miss"
    # reveal_on_miss final: the first miss keeps the chunk hidden.
    assert "den kalde luften" not in json.dumps(game["miss_note"] or {})
    assert [purpose for purpose, _user in wren.calls] == ["prepare"]
    assert "cue_mode: meaning" in wren.calls[0][1]


def test_cue_card_translation_mode_cues_with_the_gloss_only_when_a_target_is_chosen(tmp_path):
    assert cue_mode({"cue_mode": "translation"}, []) == "meaning"
    assert cue_mode({"cue_mode": "translation"}, ["en"]) == "translation"
    offered = {item["id"]: item for item in listed_games("nb")}["cue_card"]["options"][0]["values"]
    assert offered == ["meaning"]
    with_target = {item["id"]: item for item in listed_games("nb", targets=["en"])}["cue_card"]
    assert with_target["options"][0]["values"] == ["meaning", "translation"]

    wren = Wren(_cue_deck())
    service = _service(tmp_path, wren)
    session_id = service.select(
        "user-local",
        "nb",
        "logoscat-31",
        "lucas",
        game_id="cue_card",
        target_languages=["en"],
        game_options={"cue_mode": "translation"},
    )
    assert "cue_mode: translation" in wren.calls[0][1]
    assert service.describe(session_id)["game"]["instruction"] == "long tunnels"

    # Without a target the same request falls back to meaning.
    plain = Wren(_cue_deck())
    other = _service(tmp_path, plain, name="plain.db")
    session_id = other.select(
        "user-local", "nb", "logoscat-31", "lucas", game_id="cue_card", game_options={"cue_mode": "translation"}
    )
    assert "cue_mode: meaning" in plain.calls[0][1]
    assert other.describe(session_id)["game"]["instruction"] == "Veier inne i fjellet som ikke tar slutt."
