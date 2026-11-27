"""Language packs, prompt files, and the config root.

A language id selects the recognizer, the buddy voice, and the prompt files
whose names end in that id. Prompt text is read from disk on each call.
"""

import json
import os
from pathlib import Path

_REQUIRED = (
    "id",
    "display_name",
    "recognizer_model",
    "stt_language",
    "llm_model",
    "buddy_voice",
    "whisper",
)

_loaded = False
_root: Path | None = None
_languages: dict[str, dict] = {}


def reset() -> None:
    """Drop the cached language pack. The next read uses the current config root."""
    global _loaded, _root, _languages
    _loaded = False
    _root = None
    _languages = {}


def reload() -> None:
    """Read language files again. A pack added on disk shows up on the next call."""
    global _loaded
    _loaded = False
    _load()


def config_root() -> Path:
    env = os.environ.get("LOGOSKITTENS_CONFIG", "").strip()
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "config" / "languages").is_dir():
            return parent / "config"
    raise FileNotFoundError("config/languages was not found. Set LOGOSKITTENS_CONFIG.")


def languages() -> dict[str, dict]:
    _load()
    return _languages


def default_language_id() -> str:
    _load()
    for language_id, doc in _languages.items():
        if doc.get("default"):
            return language_id
    if _languages:
        return next(iter(_languages))
    return "en"


def language(language_id: str) -> dict:
    _load()
    if language_id not in _languages:
        raise KeyError(language_id)
    return _languages[language_id]


def has_recognizer(language_id: str) -> bool:
    _load()
    doc = _languages.get(language_id)
    if not doc:
        return False
    whisper = doc.get("whisper") or {}
    return bool(whisper.get("flag") and (whisper.get("model") or doc.get("recognizer_model")))


def buddy_voice(language_id: str) -> str:
    return str(language(language_id)["buddy_voice"])


# Prompts the live talk and the experts call. A new language ships each of these.
LIVE_PROMPTS = (
    "prompt-of-subject-creation",
    "ongoing_instruction_prompt",
    "bob",
    "rob",
)


def language_gaps(language_id: str) -> list[str]:
    """Missing pieces for a live pack. Empty when the language can run a talk."""
    gaps: list[str] = []
    try:
        doc = language(language_id)
    except KeyError:
        return [f"languages/{language_id}.json"]
    if not str(doc.get("buddy_voice") or "").strip():
        gaps.append(f"languages/{language_id}.json buddy_voice")
    if not has_recognizer(language_id):
        gaps.append(f"languages/{language_id}.json whisper")
    root = config_root()
    buddy_dir = root / "buddies" / language_id
    if not buddy_dir.is_dir() or not any(buddy_dir.glob("*.json")):
        gaps.append(f"buddies/{language_id}/")
    for name in LIVE_PROMPTS:
        path = root / "prompts" / f"{name}_{language_id}.md"
        if not path.is_file():
            gaps.append(f"prompts/{name}_{language_id}.md")
    return gaps


def prompt_text(name: str, language_id: str) -> str:
    """Load ``{name}_{language}.md``. ``name`` has no language suffix."""
    path = config_root() / "prompts" / f"{name}_{language_id}.md"
    if not path.is_file():
        raise FileNotFoundError(f"missing prompt {path.name}")
    return path.read_text(encoding="utf-8").strip()


def _load() -> None:
    global _loaded, _root, _languages
    root = config_root()
    if _loaded and _root == root:
        return
    found: dict[str, dict] = {}
    folder = root / "languages"
    if not folder.is_dir():
        raise FileNotFoundError(f"{folder} is not a directory")
    for path in sorted(folder.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        _check_language(path, doc)
        found[str(doc["id"])] = doc
    if not found:
        raise FileNotFoundError(f"no language files in {folder}")
    _languages = found
    _root = root
    _loaded = True


def _check_language(path: Path, doc: dict) -> None:
    if not isinstance(doc, dict):
        raise ValueError(f"{path.name} must be an object")
    missing = [key for key in _REQUIRED if key not in doc]
    if missing:
        raise ValueError(f"{path.name} misses {', '.join(missing)}")
    whisper = doc["whisper"]
    if not isinstance(whisper, dict) or not whisper.get("flag") or not whisper.get("model"):
        raise ValueError(f"{path.name} whisper needs flag and model")
