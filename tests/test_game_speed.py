"""Stage X: the timing line, pre-synthesized deck lines, the prefetched next round, and the bias policy (H17)."""

import base64
import json
import re

import pytest
from sqlmodel import select

from logoskittens.games import speed
from logoskittens.games.host import deck_strings, stt_prompt
from logoskittens.games.models import GameDeck
from logoskittens.games.registry import get_plugin
from logoskittens.persistence import SessionRow, Store
from logoskittens.session import SessionService
from logoskittens.wire import decode

from fakes import fake_complete

from test_game_echo import LINES, SOURCE, _deck
from test_game_fill import SOURCE as FILL_SOURCE, _deck as fill_deck


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self) -> float:
        return self.now

    def advance(self, ms: float) -> None:
        self.now += ms / 1000


class SlowAudio:
    """Recognition takes 250 ms and Piper 400 ms on the fake clock. The PCM depends on the text."""

    def __init__(self, clock: Clock):
        self.clock = clock
        self.synthesized: list[str] = []
        self.prompts: list[str] = []

    def transcribe(self, audio, content_type="application/octet-stream", language="en", prompt=""):
        del audio, content_type, language
        self.prompts.append(prompt)
        self.clock.advance(250)
        return "Jeg er sliten."

    def synthesize(self, text: str, language_code: str, voice_id: str) -> bytes:
        self.synthesized.append(text)
        self.clock.advance(400)
        return f"{voice_id}|{language_code}|{text}".encode("utf-8")


@pytest.fixture
def clock(monkeypatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(speed, "clock", fake)
    return fake


def _service(tmp_path, clock, wren_log=None, name="speed.db") -> SessionService:
    service = SessionService(Store(tmp_path / name), SlowAudio(clock), fake_complete)  # type: ignore[arg-type]
    service._launch = lambda fn: fn()
    service.store.save_logoscat_material(
        "logoscat-77", logoscat_user_id=1, workspace_session_id=77, language="nb", title="Echo", text=SOURCE
    )

    def wren(user, *, system="", purpose="", game_id=""):
        del system
        if wren_log is not None:
            wren_log.append((purpose, game_id, user))
        return _deck(LINES[:4])

    service.wren_fn = wren
    return service


def _start(service, targets=None, game_id="echo_chamber"):
    session_id = service.select(
        "user-local", "nb", "logoscat-77", "lucas", game_id=game_id, target_languages=targets or []
    )
    service.voice_opening(session_id, lambda _payload: None)
    return session_id


def _timing_lines(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        if line.startswith("game timing id="):
            rows.append(dict(item.split("=", 1) for item in line.split()[2:]) | {"id": line.split()[2][3:]})
    return rows


def test_every_game_turn_prints_one_timing_line(tmp_path, clock, capfd):
    service = _service(tmp_path, clock)
    session_id = _start(service)
    capfd.readouterr()
    service.perform_text(session_id, "Jeg er sliten.", lambda _payload: None)
    service.perform_audio(session_id, b"pcm", "audio/wav", lambda _payload: None)
    lines = _timing_lines(capfd.readouterr().err)
    assert len(lines) == 2
    typed, spoken = lines
    assert typed["id"] == "echo_chamber"
    assert typed["stt"] == "-" and typed["judge"] == "-" and typed["partner"] == "-"
    assert re.fullmatch(r"\d+", typed["check"]) and re.fullmatch(r"\d+", typed["tts"])
    assert spoken["stt"] == "250"
    # The spoken turn's first audio counts from the recording, through recognition.
    assert int(spoken["first_audio"]) >= 250
    # A turn on a finished round still prints its line, with nothing run.
    for line in LINES[1:4]:
        service.perform_text(session_id, line, lambda _payload: None)
    capfd.readouterr()
    service.perform_text(session_id, "hei", lambda _payload: None)
    (refused,) = _timing_lines(capfd.readouterr().err)
    assert refused["check"] == "-" and refused["tts"] == "-" and refused["first_audio"] == "-"


def test_a_prepare_prints_its_wren_time(tmp_path, clock, capfd):
    service = _service(tmp_path, clock)

    def slow_wren(user, *, system="", purpose="", game_id=""):
        clock.advance(1200)
        return _deck(LINES[:4])

    service.wren_fn = slow_wren
    _start(service)
    assert "game timing prepare id=echo_chamber wren=1200" in capfd.readouterr().err


def test_a_cached_deck_line_is_fast_and_the_same_pcm(tmp_path, clock, capfd):
    service = _service(tmp_path, clock)
    session_id = _start(service)
    audio = service.audio
    # The opening was voiced live. Every other deck string was voiced in the background, once.
    row = service.store.get_session_row(session_id)
    manifest = get_plugin("echo_chamber").load_manifest()
    strings = deck_strings(manifest, GameDeck.model_validate_json(row.deck_json), "nb")
    assert set(strings) <= set(audio.synthesized)
    assert len(strings) == len(set(strings))
    before = list(audio.synthesized)
    emitted: list[dict] = []
    capfd.readouterr()
    service.perform_text(session_id, "Jeg er sliten.", emitted.append)
    (timing,) = _timing_lines(capfd.readouterr().err)
    assert int(timing["tts"]) < 10
    assert audio.synthesized == before
    actor = [item for item in emitted if item["type"] == "actor"][0]
    spoken = decode(base64.b64decode(actor["solutions"][0]))
    fresh = SlowAudio(Clock()).synthesize(
        spoken.speech.text, spoken.speech.language_code, spoken.speech.voice_model_id
    )
    assert spoken.speech.precomputed_audio_pcm == fresh
    # The closing is cached too, with the tally it will be spoken with.
    assert "Det var siste linje. Du klarte 4 av 4." in strings
    # The next select drops the cache. Free speech does not read it.
    service.select("user-local", "nb", "logoscat-77", "lucas")
    assert service._pcm == {}


def test_the_cache_keeps_at_most_64_entries_and_20_megabytes():
    cache = speed.PcmCache()
    for index in range(70):
        cache.put(("v", "nb", f"line {index}"), b"x" * 10)
    assert len(cache) == 64
    assert cache.get(("v", "nb", "line 0")) is None
    big = speed.PcmCache()
    for index in range(3):
        big.put(("v", "nb", f"big {index}"), b"x" * (8 * 1024 * 1024))
    assert big.size <= speed.MAX_BYTES and len(big) == 2


def _rows(service) -> int:
    with service.store.open() as db:
        return len(db.exec(select(SessionRow)).all())


def test_a_new_round_uses_the_prefetched_deck_without_wren(tmp_path, clock, monkeypatch):
    monkeypatch.setenv("WREN_PREFETCH", "on")
    calls: list = []
    service = _service(tmp_path, clock, calls)
    session_id = _start(service, targets=["en"])
    assert [purpose for purpose, _game, _user in calls] == ["prepare"]
    for line in LINES[:2]:
        service.perform_text(session_id, line, lambda _payload: None)
    assert len(calls) == 1
    rows = _rows(service)
    # The third hit makes the last target active. The next round is prepared then, and is not a session yet.
    service.perform_text(session_id, LINES[2], lambda _payload: None)
    assert [purpose for purpose, _game, _user in calls] == ["prepare", "prepare"]
    assert _rows(service) == rows
    service.perform_text(session_id, LINES[3], lambda _payload: None)
    assert len(calls) == 2
    fresh = service.select("user-local", "nb", "logoscat-77", "lucas", game_id="echo_chamber", target_languages=["en"])
    assert len(calls) == 2
    assert json.loads(service.store.get_session_row(fresh).deck_json)["targets"][0]["status"] == "active"
    # Used once. Another New round prepares as today.
    service.select("user-local", "nb", "logoscat-77", "lucas", game_id="echo_chamber", target_languages=["en"])
    assert len(calls) == 3


def test_a_changed_target_list_or_an_old_prefetch_is_not_used(tmp_path, clock, monkeypatch):
    monkeypatch.setenv("WREN_PREFETCH", "on")
    calls: list = []
    service = _service(tmp_path, clock, calls)
    session_id = _start(service, targets=["en"])
    for line in LINES[:3]:
        service.perform_text(session_id, line, lambda _payload: None)
    assert len(calls) == 2
    service.select("user-local", "nb", "logoscat-77", "lucas", game_id="echo_chamber", target_languages=["en", "he"])
    assert len(calls) == 3
    assert calls[-1][2].endswith("glosses: en, he")

    later: list = []
    stale = _service(tmp_path, clock, later, name="stale.db")
    session_id = _start(stale, targets=["en"])
    for line in LINES[:3]:
        stale.perform_text(session_id, line, lambda _payload: None)
    assert len(later) == 2
    now = speed.wall()
    monkeypatch.setattr(speed, "wall", lambda: now + speed.PREFETCH_TTL_S + 1)
    stale.select("user-local", "nb", "logoscat-77", "lucas", game_id="echo_chamber", target_languages=["en"])
    assert len(later) == 3


def test_prefetch_off_prepares_nothing_ahead(tmp_path, clock):
    calls: list = []
    service = _service(tmp_path, clock, calls)
    session_id = _start(service)
    for line in LINES[:3]:
        service.perform_text(session_id, line, lambda _payload: None)
    assert len(calls) == 1


def test_bias_off_sends_no_prompt_and_deck_never_names_only_the_active_phrase(tmp_path, clock, monkeypatch):
    service = _service(tmp_path, clock)
    service.store.save_logoscat_material(
        "logoscat-21", logoscat_user_id=1, workspace_session_id=21, language="nb", title="Fjorden", text=FILL_SOURCE
    )
    service.wren_fn = lambda user, *, system="", purpose="", game_id="": fill_deck()
    session_id = service.select("user-local", "nb", "logoscat-21", "lucas", game_id="fill_blank")
    prompt = service._stt_prompt(session_id)
    assert prompt
    words = {word.casefold() for word in prompt.split(", ")}
    assert "lange" not in words and "tunneler" not in words
    # Words of the stems and of the other phrases are there, with no preference for the active one.
    assert {"kjørte", "gjennom", "kalde", "luften"} <= words
    service.perform_audio(session_id, b"pcm", "audio/wav", lambda _payload: None)
    assert service.audio.prompts[-1] == prompt

    manifest = get_plugin("fill_blank").load_manifest()
    deck = GameDeck.model_validate_json(service.store.get_session_row(session_id).deck_json)
    assert stt_prompt(manifest.model_copy(update={"stt_bias": "off"}), deck, FILL_SOURCE) == ""
    off = manifest.model_copy(update={"stt_bias": "off"})
    monkeypatch.setattr(type(get_plugin("fill_blank")), "load_manifest", lambda self: off)
    service.perform_audio(session_id, b"pcm", "audio/wav", lambda _payload: None)
    assert service.audio.prompts[-1] == ""
    # Echo and Interviewer keep today's bias: the passage sentence that holds the answer.
    echo = _service(tmp_path, clock, name="echo.db")
    echo_id = _start(echo)
    assert echo._stt_prompt(echo_id) == "Jeg er sliten."
