"""Buddy out-brain. One suggestion for the next local turn.

The spoken line stays on the practice backend. This call uses its own
settings in config/bob.json and does not read LLM_BACKEND.
"""

import json
import os
import re

from logoskittens.content import config_root
from logoskittens.expert import ExpertSkipped, expert_prompt
from logoskittens.llm import LLMError, complete_remote

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class BobSkipped(RuntimeError):
    """The call was not started. The talk continues with the current steer."""


class BobSettings:
    def __init__(
        self,
        *,
        enabled: bool,
        backend: str,
        base_url: str,
        model: str,
        think: str,
        timeout_s: float,
        steer_max_chars: int,
        every_n: int,
        qa: bool,
        api_key: str,
    ):
        self.enabled = enabled
        self.backend = backend
        self.base_url = base_url
        self.model = model
        self.think = think
        self.timeout_s = timeout_s
        self.steer_max_chars = steer_max_chars
        self.every_n = every_n
        self.qa = qa
        self.api_key = api_key


def load_settings() -> BobSettings:
    """Json defaults, then any non-empty BOB_* variable. The key is never in the file."""
    path = config_root() / "bob.json"
    raw: dict = {}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("bob.json must be an object")
        raw = loaded
    # The element's own key counts only while its provider is the environment's. Then the page key, then XAI/OPENAI.
    key = os.environ.get("BOB_API_KEY", "").strip()
    settings = BobSettings(
        enabled=_as_bool(_pick("BOB_ENABLED", "enabled", raw, True)),
        backend=str(_pick("BOB_BACKEND", "backend", raw, "xai")).strip().lower(),
        base_url=str(_pick("BOB_BASE_URL", "base_url", raw, "https://api.x.ai/v1")).strip().rstrip("/"),
        model=str(_pick("BOB_MODEL", "model", raw, "grok-4.7")).strip(),
        think=str(_pick("BOB_THINK", "think", raw, "low")).strip().lower(),
        timeout_s=float(_pick("BOB_TIMEOUT", "timeout_s", raw, 60)),
        steer_max_chars=int(_pick("BOB_STEER_MAX_CHARS", "steer_max_chars", raw, 200)),
        every_n=_every_n(_pick("BOB_EVERY", "every_n", raw, 3)),
        qa=_as_bool(_pick("BOB_QA", "qa", raw, False)),
        api_key=key,
    )
    return _with_page(settings, "bob")


def steer_block(steer: str) -> str:
    """The block appended to the buddy system prompt. Empty when there is no steer."""
    text = " ".join(steer.split())
    if not text:
        return ""
    return (
        "\nbob_steer:\n"
        f"{text}\n"
        "This private hint replaces the theme detail for this turn.\n"
        "Answer what the human just said in your own words. Do not copy their sentence.\n"
        "Then use the hint. If it is a question, ask it. If it is not, use its last sentence.\n"
        "A word already in the theme does not count. "
        "Do not replace what they said with the hint alone.\n"
    )


def watch_text(
    *,
    theme: str,
    name: str,
    gender: str,
    mood: str,
    stance: str,
    likes: str,
    summary: str,
    steer: str,
    recent: list[tuple[str, str]],
) -> str:
    lines = "\n".join(f"- {speaker}: {text}" for speaker, text in recent) or "- (none yet)"
    current = " ".join(steer.split()) or "(none)"
    return (
        f"theme: {theme}\n"
        f"buddy: {name}\n"
        f"gender: {gender}\n"
        f"mood: {mood}\n"
        f"stance: {stance}\n"
        f"likes: {likes}\n"
        f"summary: {summary}\n"
        f"current_steer: {current}\n"
        f"recent:\n{lines}\n"
    )


def buddy_turns(speakers: list[str]) -> int:
    """How many buddy replies have been sent. Consecutive sentences are one reply."""
    count = 0
    previous = ""
    for speaker in speakers:
        if speaker == "buddy" and previous != "buddy":
            count += 1
        previous = speaker
    return count


def bob_due(turn_count: int, every_n: int) -> bool:
    """True on reply 3, 6, 9, and so on, when every_n is 3."""
    step = every_n if every_n >= 1 else 1
    return turn_count > 0 and turn_count % step == 0


POSES = frozenset({"agreement", "disagreement", "frustration", "curiosity"})


def one_pose(steer: str, given: object) -> str:
    """At most one mimic. A question is curiosity. Anything else must be one of the four."""
    if not steer.strip():
        return ""
    if "?" in steer:
        return "curiosity"
    chosen = ""
    items = given if isinstance(given, list) else [given]
    for item in items:
        if isinstance(item, str) and item.strip().lower() in POSES:
            chosen = item.strip().lower()
            break
    return chosen


def parse_suggestion(raw: str, max_chars: int) -> tuple[str, str, str]:
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    start = text.find("{")
    if start == -1:
        raise LLMError("bob suggestion was not JSON")
    try:
        payload, _end = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError as exc:
        raise LLMError("bob suggestion was not JSON") from exc
    if not isinstance(payload, dict):
        raise LLMError("bob suggestion was not JSON")
    steer = payload.get("steer") or ""
    why = payload.get("why") or ""
    if not isinstance(steer, str) or not isinstance(why, str):
        raise LLMError("bob suggestion was not JSON")
    steer = " ".join(steer.split())
    why = " ".join(why.split())
    limit = max(0, max_chars)
    if len(steer) > limit:
        steer = steer[:limit].rstrip()
    if len(why) > 240:
        why = why[:240].rstrip()
    return steer, why, one_pose(steer, payload.get("pose"))


def suggest(user: str, *, language_id: str = "en") -> tuple[str, str]:
    """One xAI call. A skip or a bad reply raises. The caller keeps the current steer."""
    settings = load_settings()
    if not settings.enabled:
        raise BobSkipped("disabled")
    if not settings.api_key:
        raise BobSkipped("no API key")
    if settings.backend not in ("xai", "openai"):
        raise LLMError(f"Unknown BOB backend: {settings.backend}")
    try:
        system = expert_prompt("bob", language_id)
    except ExpertSkipped:
        raise
    except FileNotFoundError as exc:
        raise BobSkipped(str(exc)) from exc
    raw, _record = complete_remote(
        user,
        system=system,
        provider=settings.backend,
        base_url=settings.base_url,
        model=settings.model,
        api_key=settings.api_key,
        think=settings.think,
        timeout=settings.timeout_s,
    )
    return parse_suggestion(raw, settings.steer_max_chars)


def _pick(env_name: str, key: str, raw: dict, default):
    if env_name in os.environ and os.environ[env_name].strip() != "":
        return os.environ[env_name].strip()
    if key in raw and raw[key] is not None and raw[key] != "":
        return raw[key]
    return default


def _every_n(value) -> int:
    try:
        step = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"BOB every_n must be a positive integer, not {value!r}") from exc
    if step < 1:
        raise ValueError(f"BOB every_n must be a positive integer, not {value!r}")
    return step


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    raise ValueError(f"BOB flag must be on or off, not {value!r}")


def _with_page(settings, element: str):
    """Apply the Settings page (Models tab) on top of the json and the environment."""
    from logoskittens import models

    target = models.resolve(
        element,
        provider=settings.backend,
        base_url=settings.base_url,
        model=settings.model,
        think=settings.think,
        key=settings.api_key,
    )
    settings.backend = target.provider
    settings.base_url = target.base_url
    settings.model = target.model
    settings.think = target.think
    settings.api_key = target.api_key
    settings.source = target.source
    settings.key_source = target.key_source
    return settings
