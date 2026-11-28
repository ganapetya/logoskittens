"""Teacher out-brain. One correction, or silence.

Rob is a Background_Expert. He does not speak. The sentence he returns is
the sentence Savelij says. Settings are config/rob.json. He does not read
LLM_BACKEND. The gap counts human sentences and is 2, 3, or 4.
"""

import json
import os
import re

from logoskittens.content import config_root
from logoskittens.expert import ExpertSkipped, expert_prompt
from logoskittens.llm import LLMError, complete_remote
from logoskittens.talk import split_sentences
from logoskittens.teachers import TeacherProfile

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}
_GAPS = {2, 3, 4}


class RobSkipped(RuntimeError):
    """The call was not started. Savelij stays quiet."""


class RobSettings:
    def __init__(
        self,
        *,
        enabled: bool,
        backend: str,
        base_url: str,
        model: str,
        think: str,
        timeout_s: float,
        line_max_chars: int,
        explanation_max_chars: int,
        every_n: int,
        pedantic_every_responses: int,
        api_key: str,
    ):
        self.enabled = enabled
        self.backend = backend
        self.base_url = base_url
        self.model = model
        self.think = think
        self.timeout_s = timeout_s
        self.line_max_chars = line_max_chars
        self.explanation_max_chars = explanation_max_chars
        self.every_n = every_n
        self.pedantic_every_responses = pedantic_every_responses
        self.api_key = api_key


def load_settings() -> RobSettings:
    """Json defaults, then any non-empty ROB_* variable. The key is never in the file."""
    path = config_root() / "rob.json"
    raw: dict = {}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError("rob.json must be an object")
        raw = loaded
    # The element's own key counts only while its provider is the environment's. Then the page key, then XAI/OPENAI.
    key = os.environ.get("ROB_API_KEY", "").strip()
    settings = RobSettings(
        enabled=_as_bool(_pick("ROB_ENABLED", "enabled", raw, True)),
        backend=str(_pick("ROB_BACKEND", "backend", raw, "xai")).strip().lower(),
        base_url=str(_pick("ROB_BASE_URL", "base_url", raw, "https://api.x.ai/v1")).strip().rstrip("/"),
        model=str(_pick("ROB_MODEL", "model", raw, "grok-4.7")).strip(),
        think=str(_pick("ROB_THINK", "think", raw, "low")).strip().lower(),
        timeout_s=float(_pick("ROB_TIMEOUT", "timeout_s", raw, 60)),
        line_max_chars=int(_pick("ROB_LINE_MAX_CHARS", "line_max_chars", raw, 240)),
        explanation_max_chars=int(_pick("ROB_EXPLANATION_MAX_CHARS", "explanation_max_chars", raw, 600)),
        every_n=_every_n(_pick("ROB_EVERY", "every_n", raw, 3)),
        pedantic_every_responses=_pedantic_every(
            _pick("ROB_PEDANTIC_EVERY", "pedantic_every_responses", raw, 2)
        ),
        api_key=key,
    )
    return _with_page(settings, "rob")


def speaker_of(item) -> str:
    if isinstance(item, dict):
        return str(item.get("speaker") or "")
    return str(getattr(item, "speaker", "") or "")


def text_of(item) -> str:
    if isinstance(item, dict):
        return str(item.get("text") or "")
    return str(getattr(item, "text", "") or "")


def id_of(item) -> str:
    if isinstance(item, dict):
        return str(item.get("id") or "")
    return str(getattr(item, "id", "") or "")


def response_index_of(item) -> int:
    raw = item.get("response_index") if isinstance(item, dict) else getattr(item, "response_index", 0)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def human_count(sentences) -> int:
    return sum(1 for item in sentences if speaker_of(item) == "human")


def unassessed(sentences, cursor: int) -> list:
    """Lines at and after the cursor. The cursor is how many lines Rob already took."""
    start = cursor if cursor > 0 else 0
    if start >= len(sentences):
        return []
    return list(sentences[start:])


def rob_due(pending_humans: int, every_n: int) -> bool:
    """True once at least every_n new human sentences are waiting."""
    step = every_n if every_n in _GAPS else 3
    return pending_humans >= step


def response_count(stretch) -> int:
    """How many human responses are in this stretch. Sentences in one response share an index."""
    found: set[int] = set()
    for item in stretch:
        if speaker_of(item) != "human":
            continue
        index = response_index_of(item)
        if index > 0:
            found.add(index)
    return len(found)


def pedantic_due(stretch, every_responses: int) -> bool:
    """True once at least every_responses new human responses are waiting."""
    step = every_responses if isinstance(every_responses, int) and every_responses >= 1 else 2
    return response_count(stretch) >= step


def human_records(stretch) -> list[dict]:
    """Human sentences in stretch order. The pedantic notes follow this order."""
    records = []
    for item in stretch:
        if speaker_of(item) != "human":
            continue
        records.append({"id": id_of(item), "text": text_of(item)})
    return records


def watch_text(teacher: TeacherProfile, stretch) -> str:
    lines = "\n".join(f"- {speaker_of(item)}: {text_of(item)}" for item in stretch) or "- (none yet)"
    likes = ", ".join(teacher.likes)
    return (
        f"teacher: {teacher.name}\n"
        f"gender: {teacher.gender}\n"
        f"mood: {teacher.mood}\n"
        f"stance: {teacher.stance}\n"
        f"likes: {likes}\n"
        f"summary: {teacher.summary}\n"
        f"unassessed:\n{lines}\n"
    )


def pedantic_watch_text(teacher: TeacherProfile, stretch) -> str:
    """The same card as a relaxed watch, with each human sentence numbered."""
    lines: list[str] = []
    number = 0
    for item in stretch:
        if speaker_of(item) == "human":
            number += 1
            lines.append(f"{number}. human: {text_of(item)}")
        else:
            lines.append(f"- {speaker_of(item)}: {text_of(item)}")
    body = "\n".join(lines) or "- (none yet)"
    likes = ", ".join(teacher.likes)
    return (
        f"teacher: {teacher.name}\n"
        f"gender: {teacher.gender}\n"
        f"mood: {teacher.mood}\n"
        f"stance: {teacher.stance}\n"
        f"likes: {likes}\n"
        f"summary: {teacher.summary}\n"
        f"unassessed:\n{body}\n"
        f"human_sentences: {number}\n"
    )


def parse_suggestion(raw: str, max_chars: int) -> tuple[str, str]:
    """The sentence Savelij will say, or empty, and a short reason."""
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    start = text.find("{")
    if start == -1:
        raise LLMError("rob suggestion was not JSON")
    try:
        payload, _end = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError as exc:
        raise LLMError("rob suggestion was not JSON") from exc
    if not isinstance(payload, dict):
        raise LLMError("rob suggestion was not JSON")
    correction = payload.get("correction") or ""
    why = payload.get("why") or ""
    if not isinstance(correction, str) or not isinstance(why, str):
        raise LLMError("rob suggestion was not JSON")
    correction = " ".join(correction.split())
    why = " ".join(why.split())
    pieces = split_sentences(correction)
    correction = pieces[0] if pieces else ""
    limit = max(0, max_chars)
    if len(correction) > limit:
        correction = correction[:limit].rstrip()
    if len(why) > 240:
        why = why[:240].rstrip()
    if not correction and not why:
        why = "nothing to correct"
    return correction, why


def only_punctuation(heard: str, correction: str) -> bool:
    """True when the two differ only in punctuation, capitals, or spacing."""

    def bare(text: str) -> str:
        return " ".join(re.sub(r"[^\w\s]", " ", text.casefold()).split())

    return bool(bare(heard)) and bare(heard) == bare(correction)


def parse_pedantic(
    raw: str,
    human_lines: list[str],
    *,
    line_max: int,
    explanation_max: int,
    language_id: str,
) -> list[tuple[str, str, str]]:
    """One (correction, why, explanation) per human sentence, in that order.

    An empty correction drops the explanation. A correction with no explanation
    gets one short sentence built from the line, the alternative, and the reason.
    """
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    start = text.find("{")
    if start == -1:
        raise LLMError("rob suggestion was not JSON")
    try:
        payload, _end = json.JSONDecoder().raw_decode(text, start)
    except json.JSONDecodeError as exc:
        raise LLMError("rob suggestion was not JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list):
        raise LLMError("rob suggestion was not JSON")
    notes = payload["notes"]
    parsed: list[tuple[str, str, str]] = []
    for index, sentence in enumerate(human_lines):
        item = notes[index] if index < len(notes) else {}
        if not isinstance(item, dict):
            raise LLMError("rob suggestion was not JSON")
        correction = item.get("correction") or ""
        why = item.get("why") or ""
        explanation = item.get("explanation") or ""
        if not isinstance(correction, str) or not isinstance(why, str) or not isinstance(explanation, str):
            raise LLMError("rob suggestion was not JSON")
        correction = " ".join(correction.split())
        why = " ".join(why.split())
        explanation = " ".join(explanation.split())
        pieces = split_sentences(correction)
        correction = pieces[0] if pieces else ""
        if len(correction) > max(0, line_max):
            correction = correction[:line_max].rstrip()
        if len(why) > 240:
            why = why[:240].rstrip()
        if not correction or only_punctuation(sentence, correction):
            # Speech recognition wrote the commas and capitals. They are never the learner's mistake.
            parsed.append(("", "" if correction else why, ""))
            continue
        if not explanation:
            explanation = _fallback_explanation(sentence, correction, why, language_id)
        if len(explanation) > max(0, explanation_max):
            explanation = explanation[:explanation_max].rstrip()
        parsed.append((correction, why, explanation))
    return parsed


def suggest_pedantic(
    user: str,
    human_lines: list[str],
    *,
    language_id: str = "en",
) -> list[tuple[str, str, str]]:
    """One xAI call. A skip or a bad reply raises. The caller stores no notes."""
    settings = load_settings()
    if not settings.enabled:
        raise RobSkipped("disabled")
    if not settings.api_key:
        raise RobSkipped("no API key")
    if settings.backend not in ("xai", "openai"):
        raise LLMError(f"Unknown ROB backend: {settings.backend}")
    try:
        system = expert_prompt("rob_pedantic", language_id)
    except ExpertSkipped:
        raise
    except FileNotFoundError as exc:
        raise RobSkipped(str(exc)) from exc
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
    return parse_pedantic(
        raw,
        human_lines,
        line_max=settings.line_max_chars,
        explanation_max=settings.explanation_max_chars,
        language_id=language_id,
    )


def suggest(user: str, *, language_id: str = "en") -> tuple[str, str]:
    """One xAI call. A skip or a bad reply raises. The caller leaves Savelij quiet."""
    settings = load_settings()
    if not settings.enabled:
        raise RobSkipped("disabled")
    if not settings.api_key:
        raise RobSkipped("no API key")
    if settings.backend not in ("xai", "openai"):
        raise LLMError(f"Unknown ROB backend: {settings.backend}")
    try:
        system = expert_prompt("rob", language_id)
    except ExpertSkipped:
        raise
    except FileNotFoundError as exc:
        raise RobSkipped(str(exc)) from exc
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
    return parse_suggestion(raw, settings.line_max_chars)


def _pick(env_name: str, key: str, raw: dict, default):
    if env_name in os.environ and os.environ[env_name].strip() != "":
        return os.environ[env_name].strip()
    if key in raw and raw[key] is not None and raw[key] != "":
        return raw[key]
    return default


def _fallback_explanation(sentence: str, correction: str, why: str, language_id: str) -> str:
    heard = " ".join(sentence.split())
    if language_id == "nb":
        text = f"I «{heard}» si «{correction}» i stedet."
    elif language_id == "uk":
        text = f"У «{heard}» кажи «{correction}»."
    elif language_id == "de":
        text = f"Sag in «{heard}» lieber «{correction}»."
    elif language_id == "he":
        text = f"במקום «{heard}» אומרים «{correction}»."
    else:
        text = f'In "{heard}" say "{correction}" instead.'
    if why:
        text = f"{text} {why}"
    return text


def _pedantic_every(value) -> int:
    try:
        step = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"ROB pedantic_every_responses must be at least 1, not {value!r}") from exc
    if step < 1:
        raise ValueError(f"ROB pedantic_every_responses must be at least 1, not {value!r}")
    return step


def _every_n(value) -> int:
    try:
        step = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"ROB every_n must be 2, 3, or 4, not {value!r}") from exc
    if step not in _GAPS:
        raise ValueError(f"ROB every_n must be 2, 3, or 4, not {value!r}")
    return step


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    raise ValueError(f"ROB flag must be on or off, not {value!r}")


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
