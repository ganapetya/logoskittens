"""Remote orchestrator for a talking game. Free speech does not call it."""

import json
import os
import sys

from logoskittens.content import config_root
from logoskittens.llm import complete_remote

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


class WrenSkipped(RuntimeError):
    """The call was not started."""


class WrenSettings:
    def __init__(
        self,
        *,
        enabled: bool,
        backend: str,
        base_url: str,
        model: str,
        think: str,
        timeout_s: float,
        api_key: str,
        prefetch: bool = True,
    ):
        self.enabled = enabled
        self.backend = backend
        self.base_url = base_url
        self.model = model
        self.think = think
        self.timeout_s = timeout_s
        self.api_key = api_key
        self.prefetch = prefetch


def load_settings() -> WrenSettings:
    """Json defaults, then any non-empty WREN_* variable. The key is never in the file."""
    path = config_root() / "wren.json"
    raw: dict = {}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("wren.json must be an object")
        raw = loaded
    # The element's own key counts only while its provider is the environment's. Then the page key, then XAI/OPENAI.
    key = os.environ.get("WREN_API_KEY", "").strip()
    settings = WrenSettings(
        enabled=_as_bool(_pick("WREN_ENABLED", "enabled", raw, True)),
        backend=str(_pick("WREN_BACKEND", "backend", raw, "xai")).strip().lower(),
        base_url=str(_pick("WREN_BASE_URL", "base_url", raw, "https://api.x.ai/v1")).strip().rstrip("/"),
        model=str(_pick("WREN_MODEL", "model", raw, "grok-4.7")).strip(),
        think=str(_pick("WREN_THINK", "think", raw, "low")).strip().lower(),
        timeout_s=float(_pick("WREN_TIMEOUT", "timeout_s", raw, 60)),
        api_key=key,
        prefetch=_as_bool(_pick("WREN_PREFETCH", "prefetch", raw, True)),
    )
    return _with_page(settings, "wren")


def call(*, game_id: str, purpose: str, system: str, user: str) -> str:
    """One xAI call. A missing key or a disabled flag raises WrenSkipped before the POST."""
    settings = load_settings()
    if not settings.enabled or not settings.api_key:
        print("game wren skipped", file=sys.stderr, flush=True)
        raise WrenSkipped("Wren is not available")
    if settings.backend not in ("xai", "openai"):
        raise ValueError(f"Unknown Wren backend: {settings.backend}")
    text, record = complete_remote(
        user,
        system=system,
        provider=settings.backend,
        base_url=settings.base_url,
        model=settings.model,
        api_key=settings.api_key,
        think=settings.think,
        timeout=settings.timeout_s,
    )
    print(
        f"game wren id={game_id} purpose={purpose} HTTP 200 ms={record.latency_ms:.0f}",
        file=sys.stderr,
        flush=True,
    )
    return text


def _pick(env_name: str, key: str, raw: dict, default):
    if env_name in os.environ and os.environ[env_name].strip() != "":
        return os.environ[env_name].strip()
    if key in raw and raw[key] is not None and raw[key] != "":
        return raw[key]
    return default


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    raise ValueError(f"Wren flag must be on or off, not {value!r}")


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
