"""One chat call for local Ollama and Grok.

LiteLLM is not used. Grok uses the OpenAI-compatible /v1/chat/completions
endpoint. Local Ollama uses /api/chat: the OpenAI shim ignores think=false
for Qwen3 and also keeps a 32k context, so a short greeting spent most of
its time on a discarded reasoning trace. Grok's model id is grok-4.7
(https://docs.x.ai/developers/models, October 2026).
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


class LLMError(RuntimeError):
    pass


@dataclass
class ComparisonRecord:
    backend: str
    model: str
    latency_ms: float
    prompt_tokens: int | None
    completion_tokens: int | None


def _settings() -> tuple[str, str, str, str | None]:
    """Return backend, base URL, model, and optional API key. Key is not required to import."""
    backend = os.environ.get("LLM_BACKEND", "local").strip().lower()
    if backend == "grok":
        key = os.environ.get("XAI_API_KEY", "").strip()
        if not key:
            raise LLMError("XAI_API_KEY is required when LLM_BACKEND=grok")
        base = os.environ.get("GROK_BASE_URL", GROK_BASE_URL).rstrip("/")
        model = os.environ.get("GROK_MODEL", DEFAULT_GROK_MODEL).strip() or DEFAULT_GROK_MODEL
        return backend, base, model, key
    if backend == "local":
        base = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/")
        model = os.environ.get("LLM_MODEL", "").strip()
        if not base or not model:
            raise LLMError("LLM_BASE_URL and LLM_MODEL are required when LLM_BACKEND=local")
        key = os.environ.get("LLM_API_KEY", "local").strip() or "local"
        return backend, base, model, key
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
    backend_name, base, model_id, key = _resolve_target(backend, base_url, model, api_key)
    think_value = resolve_think(backend_name, think)
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
    else:
        url = f"{base}/chat/completions"
        temp = 0 if temperature is None else temperature
        body = {"model": model_id, "temperature": temp, "messages": messages}
        if think_value:
            body["reasoning_effort"] = think_value
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    started = time.perf_counter()
    traced = backend_name == "grok"
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
    return complete(
        user,
        system=system,
        timeout=timeout,
        model=model,
        backend="grok",
        base_url=base_url,
        api_key=key,
        think=think,
    )


def _resolve_target(backend: str, base_url: str, model: str, api_key: str = "") -> tuple[str, str, str, str | None]:
    """A pair may name another model. An empty field keeps the process environment."""
    chosen = backend.strip().lower()
    explicit_key = api_key.strip()
    if not chosen:
        env_backend, env_base, env_model, key = _settings()
        return (
            env_backend,
            (base_url or env_base).strip().rstrip("/"),
            (model or env_model).strip(),
            explicit_key or key,
        )
    if chosen == "grok":
        key = explicit_key or os.environ.get("XAI_API_KEY", "").strip()
        if not key:
            raise LLMError("XAI_API_KEY is required when LLM_BACKEND=grok")
        base = (base_url or os.environ.get("GROK_BASE_URL", GROK_BASE_URL)).rstrip("/")
        model_id = (model or os.environ.get("GROK_MODEL", DEFAULT_GROK_MODEL)).strip() or DEFAULT_GROK_MODEL
        return chosen, base, model_id, key
    if chosen == "local":
        base = (base_url or os.environ.get("LLM_BASE_URL", "")).strip().rstrip("/")
        model_id = (model or os.environ.get("LLM_MODEL", "")).strip()
        if not base or not model_id:
            raise LLMError("LLM_BASE_URL and LLM_MODEL are required when LLM_BACKEND=local")
        key = explicit_key or os.environ.get("LLM_API_KEY", "local").strip() or "local"
        return chosen, base, model_id, key
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
