"""Stage X. The per-turn timing line, the deck-line PCM cache, and the prefetched next round.

Free speech does not use this module.
"""

import hashlib
import json
import sys
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass

# Tests replace this with a fake clock. Read through the module so the swap is seen.
clock = time.perf_counter

SLOTS = ("stt", "check", "judge", "partner", "tts", "first_audio")


class TurnTiming:
    """One game turn. A slot that did not run prints `-`."""

    def __init__(self, game_id: str, stt_ms: float | None = None):
        self.game_id = game_id
        self.ms: dict[str, float] = {}
        self.tts_via = ""
        self.started = clock()
        if stt_ms is not None:
            self.ms["stt"] = stt_ms
            # The turn began when the recording arrived, before recognition.
            self.started -= stt_ms / 1000

    def add(self, slot: str, ms: float) -> None:
        self.ms[slot] = self.ms.get(slot, 0.0) + ms

    @contextmanager
    def slot(self, name: str):
        began = clock()
        try:
            yield
        finally:
            self.add(name, (clock() - began) * 1000)

    def first_audio(self) -> None:
        if "first_audio" not in self.ms:
            self.ms["first_audio"] = (clock() - self.started) * 1000

    def line(self) -> str:
        parts = [f"{slot}={self.ms[slot]:.0f}" if slot in self.ms else f"{slot}=-" for slot in SLOTS]
        from logoskittens.speech import settings as speech_settings

        current = speech_settings.current()
        if current.google_tts or current.google_stt:
            # Only while Google is on, so the local line keeps its shape.
            parts.append(f"stt_via={'google' if current.google_stt else 'whisper'}")
            parts.append(f"tts_via={self.tts_via or 'cache'}")
        return f"game timing id={self.game_id} " + " ".join(parts)

    def emit(self) -> None:
        print(self.line(), file=sys.stderr, flush=True)


def prepare_timing(game_id: str, wren_ms: float | None) -> None:
    shown = "-" if wren_ms is None else f"{wren_ms:.0f}"
    print(f"game timing prepare id={game_id} wren={shown}", file=sys.stderr, flush=True)


MAX_ENTRIES = 64
MAX_BYTES = 20 * 1024 * 1024


class PcmCache:
    """Per session. Keyed by voice, language, and text. At most 64 entries or 20 MB, least recent out first."""

    def __init__(self, max_entries: int = MAX_ENTRIES, max_bytes: int = MAX_BYTES):
        self.max_entries = max_entries
        self.max_bytes = max_bytes
        self._items: OrderedDict[tuple[str, str, str], bytes] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, key: tuple[str, str, str]) -> bytes | None:
        with self._lock:
            pcm = self._items.get(key)
            if pcm is not None:
                self._items.move_to_end(key)
            return pcm

    def __contains__(self, key) -> bool:
        with self._lock:
            return key in self._items

    def put(self, key: tuple[str, str, str], pcm: bytes) -> None:
        if not pcm or len(pcm) > self.max_bytes:
            return
        with self._lock:
            old = self._items.pop(key, None)
            if old is not None:
                self._bytes -= len(old)
            self._items[key] = pcm
            self._bytes += len(pcm)
            while len(self._items) > self.max_entries or self._bytes > self.max_bytes:
                _key, dropped = self._items.popitem(last=False)
                self._bytes -= len(dropped)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    @property
    def size(self) -> int:
        with self._lock:
            return self._bytes


PREFETCH_TTL_S = 30 * 60


@dataclass
class Prefetched:
    prepared: object
    at: float


def round_key(
    *,
    user_id: str,
    game_id: str,
    material_id: str,
    material_text: str,
    language_id: str,
    targets: list[str],
    options: dict,
    personality_id: str,
) -> tuple:
    """Every setting a New round keeps. A prefetched deck is used only when all of them match."""
    digest = hashlib.sha256((material_text or "").encode("utf-8")).hexdigest()[:16]
    return (
        user_id,
        game_id,
        material_id,
        digest,
        language_id,
        tuple(targets),
        json.dumps(options or {}, sort_keys=True),
        personality_id,
    )


def wall() -> float:
    return time.monotonic()
