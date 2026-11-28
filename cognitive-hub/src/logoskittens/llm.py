"""One chat call for local Ollama, Grok, and OpenAI.

LiteLLM is not used. Grok uses the OpenAI-compatible /v1/chat/completions
endpoint. Local Ollama uses /api/chat: the OpenAI shim ignores think=false
for Qwen3 and also keeps a 32k context, so a short greeting spent most of
its time on a discarded reasoning trace. Grok's model id is grok-4.7
(https://docs.x.ai/developers/models, October 2026). OpenAI uses the same
/v1/chat/completions shape, without temperature (reasoning models refuse it)
and with a JSON response format. The Settings page may override the buddy's
backend, model, and think level (`logoskittens.models`).
"""

import json
import os
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

GROK_BASE_URL = "https://api.x.ai/v1"
DEFAULT_GROK_MODEL = "grok-4.7"
OPENAI_BASE_URL = "https://api.openai.com/v1"
# Model ids change often. The Settings page lists the account's real ids (GET /v1/models).
DEFAULT_OPENAI_MODEL = "gpt-5-mini"


@dataclass(frozen=True)
class Remote:
    key_env: str
    base_env: str
    model_env: str
    base_url: str
    model: str


REMOTE = {
    "grok": Remote("XAI_API_KEY", "GROK_BASE_URL", "GROK_MODEL", GROK_BASE_URL, DEFAULT_GROK_MODEL),
    "openai": Remote("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL", OPENAI_BASE_URL, DEFAULT_OPENAI_MODEL),
}
# The element configs (bob, rob, wren) call Grok "xai".
ALIASES = {"xai": "grok"}


def backend_name(value: str) -> str:
    token = (value or "").strip().lower()
    return ALIASES.get(token, token)


def remote_defaults(backend: str) -> tuple[str, str, str]:
    """Base URL, model, and key from the environment for one remote backend."""
    spec = REMOTE[backend_name(backend)]
    base = (os.environ.get(spec.base_env, "").strip() or spec.base_url).rstrip("/")
    model = os.environ.get(spec.model_env, "").strip() or spec.model
    return base, model, os.environ.get(spec.key_env, "").strip()


class LLMError(RuntimeError):
    pass


@dataclass
class ComparisonRecord:
    backend: str
    model: str
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None


def env_target() -> tuple[str, str, str, str, str]:
    """The buddy from the environment: backend, base URL, model, key, think. Nothing is checked here."""
    backend = backend_name(os.environ.get("LLM_BACKEND", "local"))
    think = os.environ.get("LLM_THINK", "")
    if backend in REMOTE:
        base, model, key = remote_defaults(backend)
        return backend, base, model, key, think
    base = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/")
    model = os.environ.get("LLM_MODEL", "").strip()
    key = os.environ.get("LLM_API_KEY", "local").strip() or "local"
    return backend, base, model, key, think


def _settings() -> tuple[str, str, str, str | None, str]:
    """The buddy: backend, base URL, model, key, and think. A Settings-page choice wins over the environment."""
    from logoskittens import models

    backend, base, model, key, think = models.buddy_target()
    return _checked(backend, base, model, key) + (think,)


def _checked(backend: str, base: str, model: str, key: str) -> tuple[str, str, str, str | None]:
    if backend in REMOTE:
        if not key:
            raise LLMError(f"{REMOTE[backend].key_env} is required when LLM_BACKEND={backend}")
        return backend, base.rstrip("/"), model, key
    if backend == "local":
        if not base or not model:
            raise LLMError("LLM_BASE_URL and LLM_MODEL are required when LLM_BACKEND=local")
        return backend, base.rstrip("/"), model, key or "local"
    raise LLMError(f"Unknown LLM_BACKEND: {backend}")


# Local context. A Cyrillic turn is about 2–3 tokens per word; at 2048 Ollama cut the
# system prompt off the front of a Ukrainian turn and the reply came back as broken JSON.
MAX_NUM_CTX = 4096


def complete(
    user: str,
    *,
    system: str,
    timeout: float = 180,
    model: str = "",
    num_ctx: int | None = None,
    num_predict: int | None = None,
    temperature: float | None = None,
    backend: str = "",
    base_url: str = "",
    api_key: str = "",
    think: str | None = None,
) -> tuple[str, ComparisonRecord]:
    """One chat call. Empty overrides keep the environment. num_ctx cannot rise above MAX_NUM_CTX."""
    backend_name, base, model_id, key, page_think = _resolve_target(backend, base_url, model, api_key)
    if think is not None and backend_name != "local" and think.strip().lower() in ("off", "false"):
        # The buddy's retries ask for think off, which only Ollama has. Grok and OpenAI get low, the lowest
        # level both accept. A user's LLM_THINK=off on Grok is still refused below.
        think = "low"
    think_value = resolve_think(backend_name, think if think is not None else page_think)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if backend_name == "local":
        url = _ollama_chat_url(base)
        ctx = int(os.environ.get("LLM_NUM_CTX", str(MAX_NUM_CTX)) if num_ctx is None else num_ctx)
        predict = int(os.environ.get("LLM_NUM_PREDICT", "256") if num_predict is None else num_predict)
        ctx = min(ctx, MAX_NUM_CTX)
        temp = 0 if temperature is None else temperature
        body = {
            "model": model_id,
            "stream": False,
            "think": think_value,
            "format": "json",
            "keep_alive": os.environ.get("LLM_KEEP_ALIVE", "30m"),
            "messages": messages,
            "options": {"temperature": temp, "num_ctx": ctx, "num_predict": predict},
        }
        headers = {"Content-Type": "application/json"}
    elif backend_name == "openai":
        url = f"{base}/chat/completions"
        body = {"model": model_id, "messages": messages, "response_format": {"type": "json_object"}}
        if think_value:
            body["reasoning_effort"] = think_value
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    else:
        url = f"{base}/chat/completions"
        temp = 0 if temperature is None else temperature
        body = {"model": model_id, "temperature": temp, "messages": messages}
        if think_value:
            body["reasoning_effort"] = think_value
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    started = time.perf_counter()
    traced = backend_name != "local"
    _trace_call(f"{backend_name} {model_id} POST {url} timeout={timeout:.0f}s", always=traced)
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        _trace_call(
            f"{backend_name} {model_id} failed after {time.perf_counter() - started:.0f}s: {exc}",
            always=traced,
        )
        raise LLMError(f"LLM request failed: {exc}") from exc
    latency_ms = (time.perf_counter() - started) * 1000
    if response.status_code >= 400:
        _trace_call(
            f"{backend_name} {model_id} HTTP {response.status_code} {latency_ms:.0f}ms",
            always=traced,
        )
        raise LLMError(f"LLM HTTP {response.status_code}: {response.text[:400]}")
    payload = response.json()
    text, prompt_tokens, completion_tokens = _parse_completion(backend_name, payload)
    _trace_call(
        f"{backend_name} {model_id} HTTP {response.status_code} {latency_ms:.0f}ms "
        f"prompt={prompt_tokens} completion={completion_tokens}",
        always=traced,
    )
    record = ComparisonRecord(
        backend=backend_name,
        model=model_id,
        latency_ms=round(latency_ms, 2),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    _write_record(record)
    return text, record


def complete_remote(
    user: str,
    *,
    system: str,
    provider: str,
    base_url: str,
    model: str,
    api_key: str,
    think: str,
    timeout: float,
) -> tuple[str, ComparisonRecord]:
    """One Grok or OpenAI call for Bob, Rob, or Wren. The practice LLM_BACKEND is not read."""
    backend = backend_name(provider)
    if backend not in REMOTE:
        raise LLMError(f"Unknown remote provider: {provider}")
    key = api_key.strip()
    if not key:
        raise LLMError(f"An API key is required for {provider} (Settings, Models, or {REMOTE[backend].key_env})")
    return complete(
        user,
        system=system,
        timeout=timeout,
        model=model,
        backend=backend,
        base_url=base_url,
        api_key=key,
        think=think,
    )


def complete_xai(
    user: str,
    *,
    system: str,
    base_url: str,
    model: str,
    api_key: str,
    think: str,
    timeout: float,
) -> tuple[str, ComparisonRecord]:
    """One xAI chat call. The practice LLM_BACKEND is not read."""
    key = api_key.strip()
    if not key:
        raise LLMError("BOB_API_KEY or XAI_API_KEY is required for the xAI backend")
    return complete_remote(
        user, system=system, provider="grok", base_url=base_url, model=model, api_key=key, think=think, timeout=timeout
    )


def _resolve_target(
    backend: str, base_url: str, model: str, api_key: str = ""
) -> tuple[str, str, str, str | None, str | None]:
    """A pair may name another model. An empty field keeps the buddy's settings (page, then environment).

    The last value is the buddy's think level, or None when a backend was named (LLM_THINK then applies).
    """
    chosen = backend_name(backend)
    explicit_key = api_key.strip()
    if not chosen:
        env_backend, env_base, env_model, key, think = _settings()
        return (
            env_backend,
            (base_url or env_base).strip().rstrip("/"),
            (model or env_model).strip(),
            explicit_key or key,
            think,
        )
    if chosen in REMOTE:
        env_base, env_model, env_key = remote_defaults(chosen)
        target = _checked(chosen, base_url or env_base, (model or env_model).strip(), explicit_key or env_key)
        return target + (None,)
    if chosen == "local":
        base = (base_url or os.environ.get("LLM_BASE_URL", "")).strip()
        model_id = (model or os.environ.get("LLM_MODEL", "")).strip()
        key = explicit_key or os.environ.get("LLM_API_KEY", "local").strip() or "local"
        return _checked(chosen, base, model_id, key) + (None,)
    raise LLMError(f"Unknown LLM_BACKEND: {chosen}")


LOCAL_THINK = {
    "off": False,
    "false": False,
    "on": True,
    "true": True,
    "low": "low",
    "medium": "medium",
    "high": "high",
    "max": "max",
}
GROK_THINK = ("low", "medium", "high", "xhigh")
# Model-dependent: an OpenAI model refuses a level it does not support, and the call fails with that HTTP error.
OPENAI_THINK = ("none", "minimal", "low", "medium", "high", "xhigh")
THINK_LEVELS = {"local": ("off", "on", "low", "medium", "high", "max"), "grok": GROK_THINK, "openai": OPENAI_THINK}


def resolve_think(backend: str, override: str | None = None) -> bool | str | None:
    """Map LLM_THINK onto the backend. An empty local value stays off. An empty Grok value is omitted."""
    raw = override if override is not None else os.environ.get("LLM_THINK", "")
    token = raw.strip().lower()
    if backend == "local":
        if not token:
            return False
        if token not in LOCAL_THINK:
            raise LLMError("LLM_THINK for a local model must be off, on, low, medium, high, or max")
        return LOCAL_THINK[token]
    if not token:
        return None
    if backend == "openai":
        if token not in OPENAI_THINK:
            raise LLMError("The OpenAI think level must be none, minimal, low, medium, high, or xhigh")
        return token
    if token not in GROK_THINK:
        raise LLMError(
            "LLM_THINK for Grok must be low, medium, high, or xhigh. "
            "grok-4.7 cannot turn reasoning off."
        )
    return token


def _ollama_chat_url(base: str) -> str:
    root = base.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    return f"{root}/api/chat"


def _parse_completion(backend: str, payload: dict) -> tuple[str, int | None, int | None]:
    try:
        if backend == "local":
            text = payload["message"]["content"]
            return text, payload.get("prompt_eval_count"), payload.get("eval_count")
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError("LLM response did not include a message") from exc
    usage = payload.get("usage") or {}
    return text, usage.get("prompt_tokens"), usage.get("completion_tokens")


def call_note(message: str) -> None:
    """One flushed line on stderr, and on LOGOSKITTENS_CALL_LOG when that path is set."""
    line = f"{time.strftime('%H:%M:%S')} {message}\n"
    sys.stderr.write(line)
    sys.stderr.flush()
    path = os.environ.get("LOGOSKITTENS_CALL_LOG", "").strip()
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _trace_call(message: str, *, always: bool) -> None:
    """Grok calls are always traced. A local lesson call is traced only inside the improver."""
    if always or os.environ.get("LOGOSKITTENS_CALL_LOG", "").strip():
        call_note(message)


def _write_record(record: ComparisonRecord) -> None:
    path = os.environ.get("COMPARISON_LOG", "").strip()
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record)) + "\n")
