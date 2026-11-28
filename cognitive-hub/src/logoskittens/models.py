"""Which model each element uses: the buddy, Bob, Rob, and Wren.

The environment and `config/{bob,rob,wren}.json` give the defaults. The Settings
page (Models tab) may override any of them and may hold the xAI and OpenAI keys.
A page value wins; a page reset brings the element back to the environment.
The choices live in the hub SQLite file (`ModelSettingsRow`) and are cached here,
so a turn never reads the database. Keys stay on the hub.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass

from pydantic import BaseModel, Field

from logoskittens.llm import REMOTE, backend_name, env_target, remote_defaults

ELEMENTS = ("buddy", "bob", "rob", "wren")
# The page's names. `xai` is Grok; the LLM client calls it `grok`.
PROVIDERS = {"buddy": ("local", "xai", "openai"), "bob": ("xai", "openai"), "rob": ("xai", "openai"), "wren": ("xai", "openai")}
KEY_PROVIDERS = ("xai", "openai")
# The think level an element gets when the page moves it to another provider and names none.
# The buddy speaks every turn, so it gets low too: OpenAI's default (medium) took 45 s for one subject card.
SWITCH_THINK = {"buddy": "low", "bob": "low", "rob": "low", "wren": "low"}


class ElementChoice(BaseModel):
    provider: str = ""
    model: str = ""
    think: str = ""

    @property
    def empty(self) -> bool:
        return not (self.provider or self.model or self.think)


class ModelSettings(BaseModel):
    keys: dict[str, str] = Field(default_factory=dict)
    elements: dict[str, ElementChoice] = Field(default_factory=dict)

    def key(self, provider: str) -> str:
        return (self.keys.get(page_name(provider)) or "").strip()

    def choice(self, element: str) -> ElementChoice:
        return self.elements.get(element) or ElementChoice()


@dataclass(frozen=True)
class Target:
    provider: str  # page name: local, xai, openai
    base_url: str
    model: str
    think: str
    api_key: str
    source: str  # page or env
    key_source: str  # page, env, or empty


def page_name(provider: str) -> str:
    token = backend_name(provider)
    return "xai" if token == "grok" else token


def client_name(provider: str) -> str:
    return backend_name(provider)


_lock = threading.Lock()
_current = ModelSettings()


def current() -> ModelSettings:
    return _current


def replace(settings: ModelSettings) -> None:
    global _current
    with _lock:
        _current = settings


def reset() -> None:
    """Back to the environment. Tests start here."""
    replace(ModelSettings())


def resolve(element: str, *, provider: str, base_url: str, model: str, think: str, key: str) -> Target:
    """Apply the page's choice for `element` on top of its environment values.

    `key` is the element's own key from the environment (BOB_API_KEY, or the buddy's key),
    which only counts while the provider is the environment's.
    """
    settings = current()
    page = settings.choice(element)
    env_provider = page_name(provider)
    chosen = page_name(page.provider) or env_provider
    same = chosen == env_provider
    if chosen == "local" and element == "buddy":
        if same:
            base, model_id, own_key = base_url, model, key
        else:
            base = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/")
            model_id = os.environ.get("LLM_MODEL", "").strip()
            own_key = os.environ.get("LLM_API_KEY", "local").strip() or "local"
        return Target(
            provider="local",
            base_url=base,
            model=page.model or model_id,
            think=page.think or (think if same else ""),
            api_key=own_key or "local",
            source="env" if page.empty else "page",
            key_source="",
        )
    if client_name(chosen) not in REMOTE or chosen not in PROVIDERS.get(element, ()):
        # The caller refuses it at call time, as it refused an unknown backend before.
        fallback = key or os.environ.get("XAI_API_KEY", "").strip()
        return Target(chosen, base_url, page.model or model, page.think or think, fallback, "env" if page.empty else "page", "")
    env_base, env_model, env_key = remote_defaults(chosen)
    # A json default for another provider (bob.json ships xAI's URL and grok-4.7) does not carry over.
    others = [spec for name, spec in REMOTE.items() if name != client_name(chosen)]
    if base_url and base_url.rstrip("/") in {spec.base_url for spec in others}:
        base_url = ""
    if model and model in {spec.model for spec in others}:
        model = ""
    base = (base_url if same and base_url else env_base).rstrip("/")
    model_id = page.model or (model if same and model else env_model)
    level = page.think or (think if same else SWITCH_THINK.get(element, ""))
    page_key = settings.key(chosen)
    own = key if same else ""
    api_key = page_key or own or env_key
    key_source = "page" if page_key else ("env" if (own or env_key) else "")
    return Target(
        provider=chosen,
        base_url=base,
        model=model_id,
        think=level,
        api_key=api_key,
        source="env" if page.empty else "page",
        key_source=key_source,
    )


def buddy_target() -> tuple[str, str, str, str, str]:
    """The practice buddy as the LLM client wants it: backend, base URL, model, key, think."""
    backend, base, model, key, think = env_target()
    target = resolve("buddy", provider=backend, base_url=base, model=model, think=think, key=key)
    return client_name(target.provider), target.base_url, target.model, target.api_key, target.think


def buddy() -> Target:
    backend, base, model, key, think = env_target()
    return resolve("buddy", provider=backend, base_url=base, model=model, think=think, key=key)


def element(name: str) -> Target:
    """The effective target for one element, as the Settings page shows it."""
    if name == "buddy":
        return buddy()
    loader = _loaders()[name]
    settings = loader()
    return Target(
        provider=settings.backend,
        base_url=settings.base_url,
        model=settings.model,
        think=settings.think,
        api_key=settings.api_key,
        source=settings.source,
        key_source=settings.key_source,
    )


def _loaders():
    from logoskittens import bob, rob
    from logoskittens.games import wren

    return {"bob": bob.load_settings, "rob": rob.load_settings, "wren": wren.load_settings}


def key_hint(value: str) -> str:
    key = value.strip()
    if not key:
        return ""
    return f"…{key[-4:]}" if len(key) > 4 else "…"


def load(store) -> ModelSettings:
    """Read the row into the cache. No row is the environment."""
    row = store.get_model_settings()
    if row is None:
        settings = ModelSettings()
    else:
        settings = ModelSettings(
            keys={name: value for name, value in (("xai", row.xai_key), ("openai", row.openai_key)) if value},
            elements=_elements(row.elements_json),
        )
    replace(settings)
    return settings


def save(store, settings: ModelSettings) -> None:
    store.save_model_settings(
        xai_key=settings.keys.get("xai", ""),
        openai_key=settings.keys.get("openai", ""),
        elements_json=json.dumps(
            {name: choice.model_dump() for name, choice in settings.elements.items() if not choice.empty},
            ensure_ascii=False,
        ),
    )
    replace(settings)


def _elements(text: str) -> dict[str, ElementChoice]:
    try:
        doc = json.loads(text or "{}")
    except ValueError:
        return {}
    if not isinstance(doc, dict):
        return {}
    found: dict[str, ElementChoice] = {}
    for name, value in doc.items():
        if name in ELEMENTS and isinstance(value, dict):
            found[name] = ElementChoice(**{k: str(v) for k, v in value.items() if k in ("provider", "model", "think")})
    return found
