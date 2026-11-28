"""Training models from `.env_training`. Practice keeps using `.env`."""

import os
from dataclasses import dataclass
from pathlib import Path

FILE_NAME = ".env_training"

SIM_TALK_DEFAULTS = ("local", "http://127.0.0.1:11434/v1", "qwen3:8b")
JUDGE_DEFAULTS = ("grok", "https://api.x.ai/v1", "grok-4.7")


@dataclass(frozen=True)
class Role:
    backend: str
    base_url: str
    model: str
    api_key: str
    think: str = ""


@dataclass(frozen=True)
class TrainingModels:
    sim_talk: Role
    judge: Role


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_training(repo: Path) -> TrainingModels:
    path = repo / FILE_NAME
    values = parse_env(path.read_text(encoding="utf-8")) if path.is_file() else {}
    return TrainingModels(
        sim_talk=_role(
            values,
            backend_key="BACKEND_SIM_TALK",
            prefix="SIM_TALK",
            defaults=SIM_TALK_DEFAULTS,
        ),
        judge=_role(
            values,
            backend_key="BACKEND_JUDGE_PROPOSER",
            prefix="JUDGE_PROPOSER",
            defaults=JUDGE_DEFAULTS,
        ),
    )


def talk_label(repo: Path) -> str:
    path = repo / FILE_NAME
    values = parse_env(path.read_text(encoding="utf-8")) if path.is_file() else {}
    role = _role(values, backend_key="BACKEND_SIM_TALK", prefix="SIM_TALK", defaults=SIM_TALK_DEFAULTS)
    return f"{role.backend} model {role.model}"


def apply_sim_talk(role: Role) -> None:
    """Point this process at the simulated-talk model. Practice `.env` is left on disk."""
    os.environ["LLM_BACKEND"] = role.backend
    if role.think:
        os.environ["LLM_THINK"] = role.think
    if role.backend == "local":
        os.environ["LLM_BASE_URL"] = role.base_url
        os.environ["LLM_MODEL"] = role.model
        return
    from logoskittens.llm import REMOTE

    spec = REMOTE[role.backend]
    os.environ[spec.key_env] = role.api_key
    os.environ[spec.base_env] = role.base_url
    os.environ[spec.model_env] = role.model


def complete_for(role: Role):
    """Call the judge and the proposer on this role, ignoring the practice backend."""
    from logoskittens.llm import complete

    def bound(user: str, *, system: str, **kwargs):
        kwargs["backend"] = role.backend
        kwargs["base_url"] = role.base_url
        kwargs["model"] = role.model
        if role.api_key:
            kwargs["api_key"] = role.api_key
        if role.think:
            kwargs["think"] = role.think
        return complete(user, system=system, **kwargs)

    return bound


def _think(values: dict[str, str], prefix: str) -> str:
    return (values.get(f"{prefix}_THINK") or "").strip().lower()


def _role(values: dict[str, str], *, backend_key: str, prefix: str, defaults: tuple[str, str, str]) -> Role:
    backend = (values.get(backend_key) or defaults[0]).strip().lower()
    if backend not in {"local", "grok", "openai"}:
        raise ValueError(f"{backend_key} must be local, grok, or openai")
    base_url = (values.get(f"{prefix}_BASE_URL") or "").strip().rstrip("/")
    model = (values.get(f"{prefix}_MODEL") or "").strip()
    api_key = (values.get(f"{prefix}_API_KEY") or "").strip()
    if backend == "local":
        base_url = base_url or defaults[1]
        model = model or defaults[2]
        if not base_url or not model:
            raise ValueError(f"{prefix}_BASE_URL and {prefix}_MODEL are required when {backend_key}=local")
        return Role(backend, base_url, model, api_key, _think(values, prefix))
    if backend == "openai":
        from logoskittens.llm import remote_defaults

        env_base, env_model, env_key = remote_defaults("openai")
        base_url = base_url or env_base
        model = model or env_model
        api_key = api_key or env_key
    else:
        base_url = base_url or defaults[1]
        model = model or defaults[2]
        api_key = api_key or os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(f"{prefix}_API_KEY is required when {backend_key}={backend}")
    return Role(backend, base_url, model, api_key, _think(values, prefix))
