"""`/models/*`: the Settings page's Models tab. A key goes in and never comes back out."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from logoskittens import models
from logoskittens.llm import REMOTE, THINK_LEVELS, remote_defaults

LABELS = {"buddy": "Buddy", "bob": "Bob", "rob": "Rob", "wren": "Wren"}
ROLES = {
    "buddy": "Speaks every reply in the talk.",
    "bob": "Suggests the buddy's next subject.",
    "rob": "Finds the correction Savelij says.",
    "wren": "Runs the talking games.",
}
PROVIDER_LABELS = {"local": "Local (Ollama)", "xai": "Grok (xAI)", "openai": "OpenAI"}


class ChoiceBody(BaseModel):
    provider: str = ""
    model: str = ""
    think: str = ""


class SettingsBody(BaseModel):
    # A new key per provider. Empty or missing keeps the stored one.
    keys: dict[str, str] | None = None
    elements: dict[str, ChoiceBody] | None = None


class TestBody(BaseModel):
    provider: str
    # A key typed but not saved yet. Empty uses the effective key.
    key: str = ""


def public() -> dict:
    """What the page sees. Never a key."""
    settings = models.current()
    keys = []
    for provider in models.KEY_PROVIDERS:
        _base, _model, env_key = remote_defaults(provider)
        page_key = settings.key(provider)
        keys.append(
            {
                "provider": provider,
                "label": PROVIDER_LABELS[provider],
                "set": bool(page_key or env_key),
                "source": "page" if page_key else ("env" if env_key else ""),
                "hint": models.key_hint(page_key or env_key),
                "env_name": REMOTE[models.client_name(provider)].key_env,
            }
        )
    elements = []
    for name in models.ELEMENTS:
        try:
            target = models.element(name)
            error = ""
        except (OSError, ValueError) as exc:
            target, error = None, str(exc)
        elements.append(
            {
                "id": name,
                "label": LABELS[name],
                "role": ROLES[name],
                "providers": [{"id": p, "label": PROVIDER_LABELS[p]} for p in models.PROVIDERS[name]],
                "provider": target.provider if target else "",
                "model": target.model if target else "",
                "think": target.think if target else "",
                "base_url": target.base_url if target else "",
                "key_set": bool(target and target.api_key and target.provider != "local"),
                "source": target.source if target else "",
                "error": error,
            }
        )
    think = {p: list(THINK_LEVELS[models.client_name(p)]) for p in ("local", "xai", "openai")}
    return {"keys": keys, "elements": elements, "think_levels": think}


def mount(app: FastAPI, store_of) -> None:
    """`store_of()` is the hub's `Store`."""

    @app.get("/models/settings")
    def read_settings():
        return public()

    @app.put("/models/settings")
    def write_settings(body: SettingsBody):
        current = models.current()
        keys = dict(current.keys)
        for provider, value in (body.keys or {}).items():
            if provider not in models.KEY_PROVIDERS:
                raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
            if value.strip():
                keys[provider] = value.strip()
        elements = dict(current.elements)
        for name, choice in (body.elements or {}).items():
            if name not in models.ELEMENTS:
                raise HTTPException(status_code=400, detail=f"Unknown element: {name}")
            provider = models.page_name(choice.provider)
            if provider and provider not in models.PROVIDERS[name]:
                raise HTTPException(status_code=400, detail=f"{LABELS[name]} cannot use {provider}")
            think = choice.think.strip().lower()
            levels = THINK_LEVELS[models.client_name(provider or models.element(name).provider)]
            if think and think not in levels:
                raise HTTPException(status_code=400, detail=f"Think level {think} is not one of {', '.join(levels)}")
            elements[name] = models.ElementChoice(provider=provider, model=choice.model.strip(), think=think)
        models.save(store_of(), models.ModelSettings(keys=keys, elements=elements))
        return public()

    @app.delete("/models/key/{provider}")
    def forget_key(provider: str):
        if provider not in models.KEY_PROVIDERS:
            raise HTTPException(status_code=404, detail="Unknown provider")
        current = models.current()
        keys = {name: value for name, value in current.keys.items() if name != provider}
        models.save(store_of(), models.ModelSettings(keys=keys, elements=dict(current.elements)))
        return public()

    @app.delete("/models/element/{name}")
    def reset_element(name: str):
        """Back to the environment and the json file for this element."""
        if name not in models.ELEMENTS:
            raise HTTPException(status_code=404, detail="Unknown element")
        current = models.current()
        elements = {key: value for key, value in current.elements.items() if key != name}
        models.save(store_of(), models.ModelSettings(keys=dict(current.keys), elements=elements))
        return public()

    @app.post("/models/test")
    def test_key(body: TestBody):
        """List the account's chat models. It checks the key without spending tokens."""
        provider = models.page_name(body.provider)
        if provider not in models.KEY_PROVIDERS:
            raise HTTPException(status_code=400, detail="Unknown provider")
        base, _model, env_key = remote_defaults(provider)
        key = body.key.strip() or models.current().key(provider) or env_key
        if not key:
            return {"ok": False, "error": "No key is set.", "models": []}
        try:
            response = httpx.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"}, timeout=15)
        except httpx.HTTPError as exc:
            return {"ok": False, "error": f"Not reachable: {exc}", "models": []}
        if response.status_code >= 400:
            return {"ok": False, "error": f"HTTP {response.status_code}: {response.text[:200]}", "models": []}
        try:
            ids = sorted({str(item.get("id")) for item in response.json().get("data", []) if item.get("id")})
        except (ValueError, AttributeError):
            ids = []
        return {"ok": True, "error": "", "models": chat_models(provider, ids)}


def chat_models(provider: str, ids: list[str]) -> list[str]:
    """Drop the ids that cannot chat (embeddings, images, speech, moderation)."""
    skip = ("embed", "whisper", "tts", "dall-e", "image", "moderation", "audio", "realtime", "transcribe", "search")
    if provider == "xai":
        return [i for i in ids if not any(word in i for word in ("image", "imagine", "video", "embed"))]
    return [i for i in ids if not any(word in i for word in skip)]
