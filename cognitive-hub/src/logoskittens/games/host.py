"""Plugin runner. Free speech never enters this module. A game never enters run_buddy_turn."""

import json
import sys
import time
import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from logoskittens.build_id import BUILD
from logoskittens.content import config_root
from logoskittens.games import speed
from logoskittens.games.models import DeckTarget, GameDeck, GameManifest, LeadLine, TurnExit
from logoskittens.games.registry import all_plugins, get_plugin
from logoskittens.games.wren import WrenSkipped
from logoskittens.llm import LLMError
from logoskittens.mimics import keep_tokens
from logoskittens.personalities import get_personality
from logoskittens.primitives import GroupSolution, TurnSlot
from logoskittens.talk import BuddyReply, _language_specifics, active_buddy, solution_for, split_sentences
from logoskittens.teachers import get_teacher

_EMOTIONS = {"neutral", "curiosity", "amusement", "encouragement"}
prompt_opens: list[str] = []


@dataclass
class Prepared:
    deck: GameDeck
    state: BaseModel
    opening_line: str
    task_id: str


def fold(text: str) -> str:
    """NFKC, casefold, drop punctuation and symbols, collapse whitespace."""
    normalized = unicodedata.normalize("NFKC", text or "")
    kept = []
    for char in normalized.casefold():
        if unicodedata.category(char).startswith(("P", "S")):
            continue
        kept.append(char)
    return " ".join("".join(kept).split())


def same_phrase(heard: str, phrase: str) -> bool:
    left = fold(phrase)
    return bool(left) and fold(heard) == left


def contains_phrase(heard: str, phrase: str) -> bool:
    needle = fold(phrase)
    if not needle:
        return False
    return f" {needle} " in f" {fold(heard)} "


def load_game_prompt(game_id: str, role: str, language_id: str) -> str:
    """Open one path. A missing file raises ValueError with the file name."""
    name = f"{game_id}_{role}_{language_id}.md"
    path = config_root() / "prompts" / "games" / name
    prompt_opens.append(str(path))
    if not path.is_file():
        raise ValueError(name)
    return path.read_text(encoding="utf-8")


def session_targets(row) -> list[str]:
    """The session's target languages, in order. A row stored before H14 has none."""
    try:
        values = json.loads(getattr(row, "target_languages_json", "") or "[]")
    except json.JSONDecodeError:
        return []
    return [item for item in values if isinstance(item, str) and item] if isinstance(values, list) else []


def feedback_language(row) -> str:
    """Learner feedback is written in the first target, or in the source when there is none."""
    targets = session_targets(row)
    return targets[0] if targets else (getattr(row, "language_id", "") or "en")


def prepare_user(raw_text: str, rejection: str, targets: list[str]) -> str:
    """The Wren prepare message: the text, then the gloss languages when there are any, then a rejection."""
    parts = [(raw_text or "").strip()]
    if targets:
        parts.append("glosses: " + ", ".join(targets))
    if (rejection or "").strip():
        parts.append(rejection.strip())
    return "\n\n".join(part for part in parts if part)


def gloss_of(item: dict, targets: list[str]) -> dict[str, str]:
    """Wren's gloss map, kept only for the session's targets, each cut to 200 characters."""
    raw = item.get("gloss") if isinstance(item, dict) else None
    if not isinstance(raw, dict) or not targets:
        return {}
    kept: dict[str, str] = {}
    for code in targets:
        value = raw.get(code)
        if isinstance(value, str) and value.strip():
            kept[code] = " ".join(value.split())[:200]
    return kept


def forms_of(item: dict, phrase: str = "") -> list[str]:
    """H2. Wren's accepted forms: distinct folds, not the phrase itself, at most 6, each at most 120 characters."""
    raw = item.get("forms") if isinstance(item, dict) else None
    if not isinstance(raw, list):
        return []
    seen = {fold(phrase)} if phrase else set()
    kept: list[str] = []
    for value in raw:
        if not isinstance(value, str):
            continue
        text = " ".join(value.split())
        key = fold(text)
        if not key or len(text) > 120 or key in seen:
            continue
        seen.add(key)
        kept.append(text)
        if len(kept) == 6:
            break
    return kept


def closed_glosses(deck) -> list[dict]:
    """Glosses of closed targets, in deck order. An open target shows none, so the card does not give it away."""
    rows = []
    for target in getattr(deck, "targets", []) or []:
        if target.status in {"hit", "missed"} and target.gloss:
            rows.append({"id": target.id, "phrase": target.phrase, "status": target.status, "gloss": dict(target.gloss)})
    return rows


def talking_game_group(game_id: str) -> GroupSolution:
    return GroupSolution(
        solution_id=f"group-{game_id}",
        task_id="talking_game",
        protocol="talking_game",
        turn_order=[TurnSlot(actor_id="buddy-one", purpose="practice")],
    )


def wren_ready(service=None) -> bool:
    """Wren's enabled flag and key. No network call. A test's fake Wren counts as ready."""
    if service is not None and getattr(service, "wren_fn", None) is not None:
        return True
    from logoskittens.games.wren import load_settings

    try:
        settings = load_settings()
    except ValueError:
        return False
    return bool(settings.enabled and settings.api_key)


WREN_OFF = "Wren is off"
NEED_TARGET = "Choose a target language"
NO_TEACHER = "No teacher voice for this language"
# H9 `history`. ReviewGame needs this many earlier targets, and takes at most REVIEW_MAX.
NEED_HISTORY = "Play a few rounds first."
HISTORY_MIN = 3
REVIEW_MAX = 8
REVIEW_HIT_AGE_DAYS = 3


def _tags(manifest: GameManifest) -> list[str]:
    tags = []
    if "targets" in manifest.requires:
        tags.append("Translate")
    if "teacher_voice" in manifest.requires:
        tags.append("Two voices")
    if "partner" in manifest.requires or manifest.partner:
        tags.append("Partner")
    if manifest.capabilities.judge or manifest.capabilities.judge_only:
        tags.append("Judge")
    return tags


def _blocked(manifest: GameManifest, targets: list[str], ready: bool, language_id: str = "") -> str:
    if ("wren" in manifest.requires or manifest.prepare != "local") and not ready:
        return WREN_OFF
    if "targets" in manifest.requires and not targets:
        return NEED_TARGET
    if "teacher_voice" in manifest.requires and get_teacher(language_id) is None:
        return NO_TEACHER
    return ""


def _offered(option, targets: list[str] | None) -> list[str]:
    if targets:
        return list(option.values)
    return [value for value in option.values if value not in option.needs_targets]


def game_options(manifest: GameManifest, chosen: dict | None, targets: list[str] | None = None) -> dict[str, str]:
    """Each declared option: the chosen value when it is offered, else the default. Unknown keys drop.

    A value that needs a target is not offered to a session without one.
    """
    picked = chosen if isinstance(chosen, dict) else {}
    values: dict[str, str] = {}
    for option in manifest.options:
        value = picked.get(option.name)
        offered = _offered(option, targets)
        values[option.name] = value if isinstance(value, str) and value in offered else option.default
    return values


def listed_games(
    language_id: str,
    *,
    targets: list[str] | None = None,
    ready: bool = True,
    last: dict[str, dict] | None = None,
) -> list[dict]:
    """Listed games whose prompts exist for this language. A game that cannot start is listed with its reason."""
    chosen = list(targets or [])
    results = last or {}
    rows = []
    for plugin in all_plugins():
        try:
            manifest = plugin.load_manifest()
        except (OSError, ValueError, ValidationError):
            continue
        if not manifest.listed:
            continue
        try:
            if manifest.partner:
                load_game_prompt(manifest.id, "partner", language_id)
            if manifest.prepare == "wren":
                load_game_prompt(manifest.id, "wren", language_id)
        except ValueError:
            continue
        reason = _blocked(manifest, chosen, ready, language_id)
        rows.append(
            {
                "id": manifest.id,
                "phase": manifest.phase,
                "title": manifest.titles.get(language_id) or manifest.id,
                "summary": manifest.summary.get(language_id, ""),
                "tags": _tags(manifest),
                "available": not reason,
                "reason": reason,
                "next": manifest.next,
                "read_text": manifest.read_text,
                "last": results.get(manifest.id),
                "options": [
                    {
                        "name": option.name,
                        "values": _offered(option, chosen),
                        "default": option.default,
                        "labels": {
                            value: (option.labels.get(language_id) or {}).get(value) or value
                            for value in _offered(option, chosen)
                        },
                    }
                    for option in manifest.options
                ],
            }
        )
    rows.sort(key=lambda item: (item["phase"], item["id"]))
    return rows


def last_results(store, user_id: str, material_id: str) -> dict[str, dict]:
    """Per game, the newest closed round of this user on this material: `{hit, total}`."""
    results: dict[str, dict] = {}
    for row in store.game_rows(user_id, material_id):
        if row.game_id in results or not (row.deck_json or "").strip():
            continue
        try:
            deck = GameDeck.model_validate_json(row.deck_json)
        except (ValueError, ValidationError):
            continue
        if not _deck_finished(deck.targets):
            continue
        hits = sum(1 for target in deck.targets if target.status == "hit")
        results[row.game_id] = {"hit": hits, "total": len(deck.targets)}
    return results


def check_exit(decision: TurnExit, manifest: GameManifest) -> None:
    """Refuse a flag the manifest left false. The turn graph does not get a pass."""
    caps = manifest.capabilities
    if decision.show_hint and not caps.hint:
        raise ValueError("game flag hint")
    if decision.local_check == "exact" and not caps.exact_match:
        raise ValueError("game flag exact_match")
    if decision.local_check == "contains" and not caps.contains_match:
        raise ValueError("game flag contains_match")
    if (decision.local_check == "banned" or decision.buzzer) and not caps.buzzer:
        raise ValueError("game flag buzzer")
    if decision.prompt_suffix.strip() and not caps.hidden_steer:
        raise ValueError("game flag hidden_steer")
    if decision.source == "partner" and not manifest.partner:
        raise ValueError("game flag partner")
    if decision.source == "deck" and not caps.deck_line:
        raise ValueError("game flag deck_line")
    if decision.schedule_wren and not caps.async_score:
        raise ValueError("game flag async_score")
    if decision.remote_gate and not caps.remote_gate:
        raise ValueError("game flag remote_gate")
    if decision.withhold and not caps.withhold:
        raise ValueError("game flag withhold")
    if decision.mimic.strip() and not caps.mimic:
        raise ValueError("game flag mimic")
    if decision.judge and not (caps.judge and decision.local_check in {"exact", "contains"}):
        raise ValueError("game flag judge")
    if decision.local_check == "judge" and not caps.judge_only:
        raise ValueError("game flag judge_only")
    if decision.finished and not caps.end_score:
        raise ValueError("game flag end_score")


def game_message(
    *,
    session_id: str,
    manifest: GameManifest,
    deck: GameDeck,
    decision: TurnExit,
    qa: bool,
    steer: str,
    finished: bool,
    score: dict | None = None,
    show_hint: bool = False,
    source: str = "",
    attempts: dict | None = None,
    miss_note: dict | None = None,
    feedback_text: str = "",
) -> dict:
    active = _active(deck.targets)
    caps = manifest.capabilities
    instruction = active.instruction if active and caps.instruction else ""
    hint = ""
    if active and caps.hint and (show_hint or decision.show_hint):
        hint = active.hint
    phrase = active.phrase if active and manifest.reveal_phrase else ""
    matches, misses = _tally(deck, attempts)
    quest = []
    if caps.quest:
        quest = [{"id": target.id, "text": _quest_text(target, manifest), "status": target.status} for target in deck.targets]
    masked: list[str] = []
    if manifest.mask_lines and active is not None:
        # Only the open target's lines have been spoken and are hidden. Pending lines are not sent.
        masked = [line for line in _target_lines(active, manifest) if line]
    return {
        "type": "game",
        "session_id": session_id,
        "game_id": manifest.id,
        "finished": finished,
        "instruction": instruction,
        "phrase": phrase,
        "hint": hint,
        "feedback": decision.feedback,
        "feedback_text": feedback_text,
        "quest": quest,
        "score": score if score and (caps.end_score or caps.async_score) else None,
        "steer": steer if qa else "",
        "withheld": decision.withhold,
        "buzzer": bool(decision.buzzer) and caps.buzzer,
        "source": source.strip() if manifest.show_source else "",
        "matches": matches,
        "misses": misses,
        "total": len(deck.targets),
        "closed": sum(1 for target in deck.targets if target.status in {"hit", "missed"}),
        # H9 `history`. The source of the open target, for ReviewGame's card.
        "origin": active.origin if active is not None else "",
        "miss_note": miss_note,
        "glosses": closed_glosses(deck),
        "mask_lines": manifest.mask_lines,
        # H5. The card offers Finish for a game that scores at the end on request (RoleplayGame).
        "finish": manifest.capabilities.finish,
        "masked_lines": masked,
        "next": manifest.next,
    }


def _quest_text(target: DeckTarget, manifest: GameManifest) -> str:
    """H12. A closed row shows its phrase. An open row shows what the manifest chose."""
    if target.status in {"hit", "missed"} or manifest.quest_text == "phrase" or not target.instruction.strip():
        return target.phrase
    return target.instruction


def _target_lines(target: DeckTarget, manifest: GameManifest) -> list[str]:
    if manifest.deck_text == "phrase":
        return [target.phrase.strip()]
    return [target.stem.strip(), target.retry_line.strip()]


def material_text(service, row) -> str:
    """The raw passage for a card that shows its source. Echo does not ask for this."""
    material_id = (getattr(row, "material_id", "") or "").strip()
    if not material_id:
        return ""
    try:
        return service.materials.load(row.language_id or "en", material_id).text.strip()
    except (OSError, ValueError, FileNotFoundError):
        return ""


def session_chrome(row, qa: bool, source: str = "") -> dict | None:
    game_id = (row.game_id or "").strip()
    if not game_id or not (row.deck_json or "").strip():
        return None
    plugin = get_plugin(game_id)
    if plugin is None:
        return None
    try:
        manifest = plugin.load_manifest()
        deck = GameDeck.model_validate_json(row.deck_json)
        state = plugin.state_type().model_validate_json(row.game_state_json or "{}")
    except (OSError, ValueError, ValidationError, json.JSONDecodeError):
        return None
    show_hint = bool(getattr(state, "hint_on", False))
    return game_message(
        session_id=row.id,
        manifest=manifest,
        deck=deck,
        decision=TurnExit(show_hint=show_hint),
        qa=qa,
        steer="",
        finished=_round_closed(deck),
        score=_end_score(deck, manifest),
        show_hint=show_hint,
        source=source,
        attempts=dict(getattr(state, "attempts", {}) or {}),
    )


def run_game_prepare(
    service,
    *,
    game_id: str,
    material,
    language_id: str,
    person,
    target_languages: list[str] | None = None,
    options: dict | None = None,
    seed: str = "",
    user_id: str = "",
) -> Prepared:
    """Build the deck before create_session. A bad count does not return."""
    plugin = get_plugin(game_id)
    if plugin is None:
        raise ValueError("That game is not on this hub.")
    manifest = plugin.load_manifest()
    if manifest.id != game_id:
        raise ValueError("That game is not on this hub.")
    if "targets" in manifest.requires and not target_languages:
        raise ValueError(NEED_TARGET)
    if "teacher_voice" in manifest.requires and not _teacher_ready(service, language_id):
        raise ValueError(NO_TEACHER)
    raw_text = material.text
    history: list[dict] = []
    if manifest.prepare == "history":
        # H9. The panel's material is not read. Grounding runs against the earlier passages.
        history = history_targets(service, user_id, language_id)
        if len(history) < HISTORY_MIN:
            raise ValueError(NEED_HISTORY)
        raw_text = "\n\n".join(dict.fromkeys(item["passage"] for item in history))
    started = time.perf_counter()
    local = manifest.prepare == "local"
    wren_prompt = "" if local else load_game_prompt(game_id, "wren", language_id)
    # A partner turn loads its own prompt. Select needs it only for a partner opening.
    partner_prompt = load_game_prompt(game_id, "partner", language_id) if manifest.opening == "partner" else ""
    wren_ms: list[float] = []
    graph = plugin.build_prepare_graph(_no_wren if local else _bound_wren(service, game_id, "prepare", wren_ms))
    base = {
        "language_id": language_id,
        "raw_text": raw_text,
        "history": history,
        "material_id": material.id,
        "game_id": game_id,
        "rejection": "",
        "target_languages": list(target_languages or []),
        "game_options": game_options(manifest, options, target_languages),
        "material_title": getattr(material, "title", "") or "",
        "seed": seed or uuid.uuid4().hex,
        "wren_system": wren_prompt,
        "partner_system": partner_prompt,
        "deck": {},
        "state": {},
    }
    deck, state = _invoke_prepare(plugin, graph, base, manifest, raw_text, language_id, material.id)
    if not (manifest.min_targets <= len(deck.targets) <= manifest.max_targets):
        base["rejection"] = (
            f"grounded {len(deck.targets)} targets, need {manifest.min_targets} to {manifest.max_targets}"
        )
        deck, state = _invoke_prepare(plugin, graph, base, manifest, raw_text, language_id, material.id)
        if not (manifest.min_targets <= len(deck.targets) <= manifest.max_targets):
            raise ValueError(manifest.too_few or base["rejection"])
    if manifest.capabilities.judge or manifest.capabilities.judge_only:
        load_game_prompt(game_id, "judge", language_id)
    opening = _opening_line(
        service,
        manifest,
        deck,
        person,
        language_id,
        partner_prompt,
        material.text if manifest.show_source or manifest.partner_passage else "",
    )
    group = talking_game_group(game_id)
    elapsed = (time.perf_counter() - started) * 1000
    print(
        f"game prepare id={game_id} language={language_id} ms={elapsed:.0f} targets={len(deck.targets)}",
        file=sys.stderr,
        flush=True,
    )
    speed.prepare_timing(game_id, sum(wren_ms) if wren_ms else None)
    return Prepared(deck=deck, state=state, opening_line=opening, task_id=group.task_id)


def _teacher_ready(service, language_id: str) -> bool:
    actor = (getattr(service, "actors", None) or {}).get("teacher-one")
    return get_teacher(language_id) is not None and actor is not None and bool(getattr(actor, "active", False))


def history_targets(service, user_id: str, language_id: str, now=None) -> list[dict]:
    """H9 `history`. This user's earlier targets in this language: missed ones first, then hits older than 3 days.

    The newest closed occurrence of a chunk decides its status. ReviewGame's own rounds are not read, since their
    passage is not the chunk's source. Each entry carries the passage and title of its source.
    """
    from datetime import datetime, timedelta, timezone

    current = now or datetime.now(timezone.utc)
    cutoff = current - timedelta(days=REVIEW_HIT_AGE_DAYS)
    rows = service.store.history_rows((user_id or "user-local").strip() or "user-local", language_id)
    sources: dict[str, tuple[str, str]] = {}
    seen: set[str] = set()
    missed: list[dict] = []
    old_hits: list[dict] = []
    for row in rows:
        if (row.game_id or "").strip() == "review":
            continue
        try:
            deck = GameDeck.model_validate_json(row.deck_json)
        except (ValueError, ValidationError):
            continue
        material_id = (row.material_id or "").strip()
        if material_id not in sources:
            try:
                material = service.materials.load(language_id, material_id)
                sources[material_id] = (material.text.strip(), (getattr(material, "title", "") or material_id).strip())
            except (OSError, ValueError, FileNotFoundError):
                sources[material_id] = ("", "")
        passage, title = sources[material_id]
        created = row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=timezone.utc)
        for target in deck.targets:
            if target.status not in {"hit", "missed"}:
                continue
            key = fold(target.phrase)
            if not key or key in seen:
                continue
            seen.add(key)
            if not passage or not contains_phrase(passage, target.phrase):
                continue
            entry = {
                "phrase": target.phrase,
                "status": target.status,
                "forms": list(target.forms),
                "passage": passage,
                "origin": title[:120],
                "material_id": material_id,
                "game_id": deck.game_id,
            }
            if target.status == "missed":
                missed.append(entry)
            elif created <= cutoff:
                old_hits.append(entry)
    return (missed + old_hits)[:REVIEW_MAX]


def run_game_turn(
    service, session_id: str, row, user_text: str, emit: Callable[[dict], None], stt_ms: float | None = None
) -> None:
    """Commit the human line, then decide. Every turn prints one timing line, whatever path it took."""
    timing = speed.TurnTiming((row.game_id or "").strip(), stt_ms)
    try:
        _game_turn(service, session_id, row, user_text, emit, timing)
    finally:
        timing.emit()


def _game_turn(service, session_id: str, row, user_text: str, emit: Callable[[dict], None], timing) -> None:
    from logoskittens.session import _next_response, _sentence_models
    from logoskittens.talk import SpokenSentence

    game_id = (row.game_id or "").strip()
    plugin = get_plugin(game_id)
    if plugin is None:
        raise ValueError("That game is not on this hub.")
    if not (row.deck_json or "").strip():
        raise ValueError("This game has no deck.")
    manifest = plugin.load_manifest()
    deck = GameDeck.model_validate_json(row.deck_json)
    try:
        state = plugin.state_type().model_validate_json(row.game_state_json or "{}")
    except (ValueError, ValidationError) as exc:
        raise ValueError("This game state is from another version.") from exc
    if int(getattr(state, "state_version", 1) or 1) != 1:
        raise ValueError("This game state is from another version.")
    if _round_closed(deck):
        # The round is over (H4). No line is stored, no model is called, nobody speaks.
        emit(
            game_message(
                session_id=session_id,
                manifest=manifest,
                deck=deck,
                decision=TurnExit(),
                qa=service.qa_enabled(session_id),
                steer="",
                finished=True,
                score=_end_score(deck, manifest),
                show_hint=bool(getattr(state, "hint_on", False)),
                source=material_text(service, row),
                attempts=dict(getattr(state, "attempts", {}) or {}),
            )
        )
        print(f"game turn id={game_id} refused=finished build={BUILD}", file=sys.stderr, flush=True)
        return
    heard = user_text.strip()
    sentences = _sentence_models(row.sentences_json)
    response_index = _next_response(sentences)
    pieces = []
    for piece in split_sentences(heard):
        sentence = SpokenSentence(
            speaker="human",
            text=piece,
            id=f"line-{_token()}",
            response_index=response_index,
        )
        sentences.append(sentence)
        pieces.append({"id": sentence.id, "text": sentence.text})
    human_id = pieces[-1]["id"] if pieces else ""
    emit(
        {
            "type": "heard",
            "session_id": session_id,
            "transcript": heard,
            "pieces": pieces,
            "final": False,
        }
    )
    _save_sentences(service, session_id, row, sentences)
    stored_deck = deck.model_copy(deep=True)
    stored_state = state.model_copy(deep=True)
    graph = plugin.build_turn_graph()
    with timing.slot("check"):
        result = graph.invoke(
            {
                "heard": heard,
                "deck": stored_deck.model_dump(),
                "state": stored_state.model_dump(),
                # H4. Human responses so far, this one included.
                "turn": len({item.response_index for item in sentences if item.speaker == "human"}),
                "exit": {},
            }
        )
    if not isinstance(result, dict) or "exit" not in result:
        raise ValueError("The turn graph did not return a decision.")
    decision = TurnExit.model_validate(result["exit"])
    check_exit(decision, manifest)
    deck = stored_deck
    state = stored_state
    before_targets = [target.model_copy() for target in deck.targets]
    source = material_text(service, row)
    judged = None
    why = ""
    if decision.judge or decision.local_check == "judge":
        judged, why = _judge_answer(
            service,
            game_id,
            row.language_id,
            deck,
            state,
            heard,
            decision.local_check,
            source,
            feedback_language(row),
            timing,
            always=decision.local_check == "judge",
            last_try=_last_try(deck, state, manifest),
        )
    if decision.local_check:
        with timing.slot("check"):
            deck, state, decision = apply_local(deck, state, heard, decision, manifest, hit=judged)
    maybe_prefetch(service, session_id, row, deck)
    finished = _is_finished(deck, decision, manifest)
    if finished and not deck.closed:
        deck = deck.model_copy(update={"closed": True})
    qa = service.qa_enabled(session_id)
    miss_note = _verdict_note(sentences, human_id, decision, manifest, before_targets, deck, source, why)
    steer = _steer_text(decision, deck, manifest)
    emit(
        game_message(
            session_id=session_id,
            manifest=manifest,
            deck=deck,
            decision=decision,
            qa=qa,
            steer=steer,
            finished=finished,
            show_hint=bool(getattr(state, "hint_on", False)),
            source=source,
            attempts=dict(getattr(state, "attempts", {}) or {}),
            miss_note=miss_note,
            feedback_text=(miss_note or {}).get("explanation", ""),
            score=_end_score(deck, manifest) if finished else None,
        )
    )
    _save_game(service, session_id, deck, state, row.wren_note or "")
    if miss_note:
        _save_sentences(service, session_id, row, sentences)
    remote = 0
    if decision.remote_gate:
        remote = 1
        try:
            wren_prompt = load_game_prompt(game_id, "wren", row.language_id)
            raw = _invoke_wren(service, game_id, "gate", wren_prompt, decision.wren_user or heard)
            payload = _object(raw)
        except WrenSkipped as exc:
            raise ValueError("Wren is not available") from exc
        deck, state, note = plugin.apply_wren(deck, state, payload)
        note = (note or "")[:240]
        target = _target_by_id(deck.targets, str(payload.get("target_id") or "")) or _active(deck.targets)
        if target is None or target.status != "hit":
            decision.withhold = True
            decision.source = "none"
            decision.feedback = decision.feedback or "miss"
        else:
            decision.source = "partner"
            decision.feedback = decision.feedback or "match"
        finished = _is_finished(deck, decision, manifest)
        emit(
            game_message(
                session_id=session_id,
                manifest=manifest,
                deck=deck,
                decision=decision,
                qa=qa,
                steer=steer,
                finished=finished,
                show_hint=bool(getattr(state, "hint_on", False)),
                source=source,
                attempts=dict(getattr(state, "attempts", {}) or {}),
            )
        )
        _save_game(service, session_id, deck, state, note)
    print(
        f"game turn id={game_id} feedback={decision.feedback} remote={remote} build={BUILD}",
        file=sys.stderr,
        flush=True,
    )
    if decision.withhold or decision.source == "none":
        return
    if decision.source == "partner":
        with timing.slot("partner"):
            line, emotion = _resolve_line(service, decision, deck, manifest, heard, row, steer, sentences)
    else:
        line, emotion = _resolve_line(service, decision, deck, manifest, heard, row, steer, sentences)
    if decision.source == "deck" and finished and not line:
        line = _closing_line(manifest, row.language_id, deck)
        emotion = "encouragement" if line else emotion
    if decision.source == "deck" and finished and not line:
        return
    if not line:
        return
    person = get_personality(row.language_id, row.personality_id)
    asked = _last_buddy_line(sentences)
    tokens = keep_tokens([decision.mimic]) if manifest.capabilities.mimic and decision.mimic.strip() else []
    spoken = _spoken_target(deck, decision, line) if decision.source == "deck" else None
    if spoken is not None:
        target, retry = spoken
        # H8. The lead is voiced first, each line with its own role. A retry replays the line that holds the answer.
        for item in _lead_lines(target, retry):
            _voice_lead(service, session_id, row, sentences, item, emit, timing)
        if not retry:
            emotion = target.emotion or emotion
            if manifest.capabilities.mimic and target.mimic:
                tokens = keep_tokens([target.mimic])
    reply = BuddyReply(line=line, emotion=emotion)
    solution = solution_for(reply, active_buddy(service.actors), row.language_id, person.voice_id)
    _voice_and_store(
        service,
        session_id,
        row,
        sentences,
        solution,
        emit,
        tokens=tokens,
        timing=timing,
    )
    if decision.schedule_wren:
        _schedule_score(
            service,
            session_id,
            game_id,
            plugin,
            human_id,
            _score_user(decision.wren_user, heard, asked, source if manifest.show_source else ""),
            emit,
            manifest,
            qa,
        )


def speak_opening(service, session_id: str, emit: Callable[[dict], None]) -> None:
    line = service._openings.pop(session_id, "")
    row = service.store.get_session_row(session_id)
    if row is None:
        return
    if line:
        person = get_personality(row.language_id, row.personality_id)
        emotion, tokens = "neutral", []
        target = _opening_target(service, row, line)
        if target is not None:
            _speak_opening_lead(service, session_id, row, target, line, emit)
            emotion = target.emotion or emotion
            if target.mimic and _manifest_of(row) is not None and _manifest_of(row).capabilities.mimic:
                tokens = keep_tokens([target.mimic])
        solution = solution_for(
            BuddyReply(line=line, emotion=emotion),
            active_buddy(service.actors),
            row.language_id,
            person.voice_id,
        )
        _voice_and_store(service, session_id, row, None, solution, emit, tokens=tokens)
    if (row.game_id or "").strip():
        service._launch(lambda: presynthesize(service, session_id))
        # A deck of one target is already on its last target.
        try:
            maybe_prefetch(service, session_id, row, GameDeck.model_validate_json(row.deck_json))
        except (ValueError, ValidationError):
            pass


def _manifest_of(row) -> GameManifest | None:
    plugin = get_plugin((row.game_id or "").strip())
    if plugin is None:
        return None
    try:
        return plugin.load_manifest()
    except (OSError, ValueError, ValidationError):
        return None


def _opening_target(service, row, line: str) -> DeckTarget | None:
    """The active target when the opening is its stem. Its lead, emotion, and mimic go with the opening."""
    del service
    manifest = _manifest_of(row)
    if manifest is None or manifest.opening != "stem" or not (row.deck_json or "").strip():
        return None
    try:
        deck = GameDeck.model_validate_json(row.deck_json)
    except (ValueError, ValidationError):
        return None
    active = _active(deck.targets)
    if active is None or active.stem.strip() != line.strip():
        return None
    return active


def _speak_opening_lead(service, session_id: str, row, target: DeckTarget, line: str, emit) -> None:
    """Voice the opening's lead, then store those lines before the opening, which select already stored."""
    from logoskittens.session import _sentence_models
    from logoskittens.talk import SpokenSentence

    if not target.lead:
        return
    said: list = []
    for item in _lead_lines(target, retry=False):
        if _voice_lead(service, session_id, row, None, item, emit, None):
            for piece in split_sentences(item.line):
                said.append(SpokenSentence(speaker=item.speaker, text=piece))
    if not said:
        return
    with service._talk_lock:
        fresh = service.store.get_session_row(session_id)
        sentences = _sentence_models(fresh.sentences_json if fresh is not None else "[]")
    at = next((index for index, item in enumerate(sentences) if item.speaker == "buddy" and item.text == line), 0)
    _save_sentences(service, session_id, fresh or row, sentences[:at] + said + sentences[at:])


def _spoken_target(deck, decision: TurnExit, line: str) -> tuple[DeckTarget, bool] | None:
    """The target whose stem (False) or retry line (True) this deck line is."""
    active = _active(getattr(deck, "targets", []) or [])
    text = (line or "").strip()
    if active is None or not text:
        return None
    if text == active.stem.strip():
        return active, False
    if text == active.retry_line.strip():
        return active, True
    return None


def _lead_lines(target: DeckTarget, retry: bool) -> list[LeadLine]:
    """All of the lead before a stem. Before a retry, only the lead line that holds the answer."""
    if not retry:
        return list(target.lead)
    return [item for item in target.lead if contains_phrase(item.line, target.phrase)][:1]


def _voice_lead(service, session_id: str, row, sentences, item: LeadLine, emit, timing) -> bool:
    """One lead line. A `teacher` line is Savelij's voice through role `teacher` (H8). Rob does not run."""
    if item.speaker == "teacher":
        teacher = get_teacher(row.language_id)
        actor = (getattr(service, "actors", None) or {}).get("teacher-one")
        if teacher is None or actor is None or not getattr(actor, "active", False):
            print("game lead skipped: no teacher", file=sys.stderr, flush=True)
            return False
        solution = solution_for(BuddyReply(line=item.line, emotion="neutral"), actor, row.language_id, teacher.voice_id)
        _voice_and_store(
            service, session_id, row, sentences, solution, emit, tokens=[], timing=timing, role="teacher", speaker=teacher.name
        )
        return True
    person = get_personality(row.language_id, row.personality_id)
    solution = solution_for(BuddyReply(line=item.line, emotion="neutral"), active_buddy(service.actors), row.language_id, person.voice_id)
    _voice_and_store(service, session_id, row, sentences, solution, emit, tokens=[], timing=timing)
    return True


def pcm_cache(service, session_id: str) -> speed.PcmCache:
    with service._pcm_lock:
        cache = service._pcm.get(session_id)
        if cache is None:
            cache = service._pcm[session_id] = speed.PcmCache()
        return cache


def _pcm_key(solution) -> tuple[str, str, str]:
    return (solution.speech.voice_model_id, solution.speech.language_code, solution.speech.text)


def deck_strings(manifest: GameManifest, deck: GameDeck, language_id: str) -> list[str]:
    """Every line a deck-line turn of this session can speak: stems, retry lines or phrases, each closing."""
    lines: list[str] = []
    for target in deck.targets:
        if manifest.deck_text == "phrase":
            lines.append(target.phrase)
        else:
            lines.extend([target.stem, target.retry_line])
        lines.extend(item.line for item in target.lead if item.speaker == "buddy")
    template = (manifest.closing.get(language_id) or "").strip()
    if template:
        total = len(deck.targets)
        for hits in range(total + 1):
            lines.append(template.replace("{hits}", str(hits)).replace("{total}", str(total)))
    kept: list[str] = []
    for line in lines:
        text = (line or "").strip()
        if text and text not in kept:
            kept.append(text)
    return kept


def presynthesize(service, session_id: str) -> None:
    """Background. Voice every deck string of the session once, in the session's voice, into its cache."""
    try:
        row = service.store.get_session_row(session_id)
        if row is None or not (row.game_id or "").strip() or not (row.deck_json or "").strip():
            return
        plugin = get_plugin(row.game_id)
        if plugin is None:
            return
        manifest = plugin.load_manifest()
        if not manifest.capabilities.deck_line:
            return
        deck = GameDeck.model_validate_json(row.deck_json)
        person = get_personality(row.language_id, row.personality_id)
        actor = active_buddy(service.actors)
        cache = pcm_cache(service, session_id)
        jobs = []
        for text in deck_strings(manifest, deck, row.language_id):
            solution = solution_for(BuddyReply(line=text, emotion="neutral"), actor, row.language_id, person.voice_id)
            key = _pcm_key(solution)
            if key not in cache:
                jobs.append((key, text, solution.speech.language_code, solution.speech.voice_model_id))
        made = _voice_jobs(service, session_id, cache, jobs)
        if made < 0:
            # A new select dropped this session's cache.
            return
        made += _presynthesize_teacher(service, session_id, row, deck, cache)
        print(f"game presynth id={row.game_id} lines={made} cached={len(cache)}", file=sys.stderr, flush=True)
    except Exception as exc:  # noqa: BLE001 - a background voice must never break the talk
        print(f"game presynth failed error={type(exc).__name__}", file=sys.stderr, flush=True)


GOOGLE_PREFETCH_WORKERS = 4


def _voice_jobs(service, session_id: str, cache: speed.PcmCache, jobs: list[tuple]) -> int:
    """Voice deck lines into the cache. Google lines run four at a time; Piper is CPU bound and stays serial.
    Returns how many were made, or -1 when a new select dropped this cache."""
    from concurrent.futures import ThreadPoolExecutor

    from logoskittens.speech import settings as speech_settings
    from logoskittens.speech.voices import split

    synth = getattr(service.audio, "synthesize_background", service.audio.synthesize)

    def alive() -> bool:
        with service._pcm_lock:
            return service._pcm.get(session_id) is cache

    def one(job) -> bool:
        key, text, language_code, voice_id = job
        if key in cache:
            return False
        if not alive():
            return False
        cache.put(key, synth(text, language_code, voice_id))
        return True

    google = speech_settings.current().google_tts and any(split(job[3])[0] for job in jobs)
    if google and len(jobs) > 1:
        with ThreadPoolExecutor(max_workers=GOOGLE_PREFETCH_WORKERS, thread_name_prefix="presynth") as pool:
            made = sum(1 for done in pool.map(one, jobs) if done)
        return made if alive() else -1
    made = 0
    for job in jobs:
        if not alive():
            return -1
        if one(job):
            made += 1
    return made


def _presynthesize_teacher(service, session_id: str, row, deck: GameDeck, cache: speed.PcmCache) -> int:
    """H8. The teacher's lead lines, in Savelij's voice, into the same cache."""
    teacher = get_teacher(row.language_id)
    actor = (getattr(service, "actors", None) or {}).get("teacher-one")
    if teacher is None or actor is None or not getattr(actor, "active", False):
        return 0
    made = 0
    for target in deck.targets:
        for item in target.lead:
            if item.speaker != "teacher":
                continue
            solution = solution_for(BuddyReply(line=item.line, emotion="neutral"), actor, row.language_id, teacher.voice_id)
            key = _pcm_key(solution)
            if key in cache:
                continue
            with service._pcm_lock:
                if service._pcm.get(session_id) is not cache:
                    return made
            cache.put(key, service.audio.synthesize(item.line, solution.speech.language_code, solution.speech.voice_model_id))
            made += 1
    return made


def session_round_key(service, row, material_text: str) -> tuple:
    return speed.round_key(
        user_id=row.user_id,
        game_id=row.game_id,
        material_id=row.material_id,
        material_text=material_text,
        language_id=row.language_id,
        targets=session_targets(row),
        options=service._session_options.get(row.id, {}),
        personality_id=row.personality_id,
    )


def maybe_prefetch(service, session_id: str, row, deck) -> None:
    """When the last target turns active, prepare the next round in the background. It is not stored as a session."""
    targets = list(getattr(deck, "targets", []) or [])
    if not targets or targets[-1].status != "active":
        return
    plugin = get_plugin(row.game_id)
    try:
        if plugin is None or plugin.load_manifest().prepare != "wren":
            return
    except (OSError, ValueError, ValidationError):
        return
    from logoskittens.games.wren import load_settings

    try:
        if not load_settings().prefetch or not wren_ready(service):
            return
    except ValueError:
        return
    with service._prefetch_lock:
        if session_id in service._prefetch_started:
            return
        service._prefetch_started.add(session_id)
    game_id = row.game_id
    options = dict(service._session_options.get(session_id, {}))

    def work() -> None:
        try:
            material = service.materials.load(row.language_id, row.material_id)
            key = session_round_key(service, row, material.text)
            prepared = run_game_prepare(
                service,
                game_id=game_id,
                material=material,
                language_id=row.language_id,
                person=get_personality(row.language_id, row.personality_id),
                target_languages=session_targets(row),
                options=options,
            )
            with service._prefetch_lock:
                service._prefetched[key] = speed.Prefetched(prepared=prepared, at=speed.wall())
            print(f"game prefetch id={game_id} targets={len(prepared.deck.targets)}", file=sys.stderr, flush=True)
        except Exception as exc:  # noqa: BLE001 - a missed prefetch only means New round prepares as today
            print(f"game prefetch failed id={game_id} error={type(exc).__name__}", file=sys.stderr, flush=True)

    service._launch(work)


def take_prefetched(service, key: tuple):
    """The prefetched round for exactly these settings, used once, when under 30 minutes old."""
    with service._prefetch_lock:
        found = service._prefetched.pop(key, None)
    if found is None or speed.wall() - found.at > speed.PREFETCH_TTL_S:
        return None
    return found.prepared


def stt_prompt(manifest: GameManifest, deck: GameDeck, passage: str) -> str:
    """H17. `expected`: the passage sentence that holds the answer. `deck`: words of every target and stem,
    minus any word found only in the active phrase. `off`: nothing."""
    from logoskittens.stt_bias import bias_words, expected_hearing

    active = _active(deck.targets)
    if active is None or manifest.stt_bias == "off":
        return ""
    if manifest.stt_bias == "expected":
        return expected_hearing(active.phrase, passage)
    texts = []
    for target in deck.targets:
        texts.extend([target.stem, target.retry_line, target.instruction])
        if target.id != active.id:
            texts.append(target.phrase)
    elsewhere = {word.casefold() for word in bias_words(*texts, limit=10_000)}
    everything = bias_words(*texts, active.phrase, limit=10_000)
    return ", ".join([word for word in everything if word.casefold() in elsewhere][:80])


def finish_game(service, session_id: str, emit: Callable[[dict], None]) -> None:
    row = service.store.get_session_row(session_id)
    if row is None or not (row.game_id or "").strip():
        raise ValueError("No game is open.")
    plugin = get_plugin(row.game_id)
    if plugin is None:
        raise ValueError("That game is not on this hub.")
    if not (row.deck_json or "").strip():
        raise ValueError("This game has no deck.")
    from logoskittens.session import _sentence_models

    manifest = plugin.load_manifest()
    deck = GameDeck.model_validate_json(row.deck_json)
    state = plugin.state_type().model_validate_json(row.game_state_json or "{}")
    transcript = tuple((item.speaker, item.text) for item in _sentence_models(row.sentences_json))
    deck, state, note, score = _call_finish(plugin, deck, state, _bound_wren(service, row.game_id, "finish"), transcript)
    note = (note or "")[:240]
    if manifest.capabilities.finish:
        # H5. A game with a Finish closes its round there, with open targets or not. Games 1–3 behave as before.
        deck = deck.model_copy(update={"closed": True})
    _save_game(service, session_id, deck, state, note)
    emit(
        game_message(
            session_id=session_id,
            manifest=manifest,
            deck=deck,
            decision=TurnExit(),
            qa=service.qa_enabled(session_id),
            steer="",
            finished=_round_closed(deck),
            score=score if score is not None else _end_score(deck, manifest),
            show_hint=bool(getattr(state, "hint_on", False)),
            source=material_text(service, row),
            attempts=dict(getattr(state, "attempts", {}) or {}),
        )
    )


def _call_finish(plugin, deck, state, wren, transcript: tuple):
    """H5. `finish(deck, state, wren, transcript)` -> (deck, state, note, score). An older plugin returns three."""
    import inspect

    try:
        takes = len(inspect.signature(plugin.finish).parameters) >= 4
    except (TypeError, ValueError):
        takes = False
    result = plugin.finish(deck, state, wren, transcript) if takes else plugin.finish(deck, state, wren)
    if len(result) == 3:
        deck, state, note = result
        return deck, state, note, None
    return result


def _end_score(deck, manifest: GameManifest) -> dict | None:
    """The hits score of a closed round, for a game that shows one at the end."""
    if not manifest.capabilities.end_score or not _round_closed(deck):
        return None
    hits = sum(1 for target in deck.targets if target.status == "hit")
    return {"kind": "hits", "hit": hits, "total": len(deck.targets)}


def apply_local(
    deck: GameDeck,
    state: BaseModel,
    heard: str,
    decision: TurnExit,
    manifest: GameManifest,
    *,
    hit: bool | None = None,
):
    """The only local writer of status, attempts, and pending_hint. `hit` is a judged verdict for the active target."""
    decision = decision.model_copy(deep=True)
    targets = [target.model_copy() for target in deck.targets]
    data = state.model_dump()
    attempts = dict(data.get("attempts") or {})
    kind = decision.local_check
    if kind == "banned":
        active = _active(targets)
        banned_hit = False
        if active is not None:
            banned_hit = any(contains_phrase(heard, word) for word in active.banned if word.strip())
        if banned_hit:
            # A buzz withholds and does not count an attempt.
            decision.buzzer = True
            decision.withhold = True
            decision.feedback = "buzzer"
            updated = deck.model_copy(update={"targets": targets})
            return updated, state, decision
        # H6. A clean line goes on to the active contains check.
        kind = "contains"
    if kind == "judge":
        # H13. The verdict is the check. A failed judge call is a miss.
        hit = bool(hit)
    if kind not in {"exact", "contains", "judge"}:
        return deck, state, decision
    if decision.match == "any":
        hit_any = False
        for target in targets:
            if target.status in {"pending", "active"} and _target_hit(kind, heard, target):
                target.status = "hit"
                hit_any = True
        if hit_any:
            data["pending_hint"] = ""
            data["hint_on"] = False
        _promote(targets)
        # An open quest with no attempt cap (RoleplayGame) has no misses: a line without a chunk is just talk.
        quiet = "" if manifest.max_attempts == 0 else "miss"
        decision.feedback = decision.feedback or ("match" if hit_any else quiet)
    else:
        active = _active(targets)
        landed = hit if hit is not None else (active is not None and _target_hit(kind, heard, active))
        if active is not None and landed:
            active.status = "hit"
            data["pending_hint"] = ""
            data["hint_on"] = False
            _promote(targets)
            decision.feedback = decision.feedback or "match"
            if decision.source == "deck":
                nxt = _active(targets)
                if nxt is None:
                    decision.line = ""
                    decision.finished = True
                else:
                    decision.line = _deck_line(nxt, manifest, retry=False)
        elif active is not None:
            if (
                kind in {"contains", "judge"}
                and decision.match == "active"
                and active.hint.strip()
            ):
                data["pending_hint"] = active.hint.strip()
            cap = manifest.max_attempts
            if cap > 0:
                count = int(attempts.get(active.id, 0)) + 1
                attempts[active.id] = count
                data["attempts"] = attempts
                if count >= cap:
                    active.status = "missed"
                    _promote(targets)
            decision.feedback = decision.feedback or "miss"
            if decision.source == "deck":
                if active.status == "active":
                    data["hint_on"] = True
                    if manifest.capabilities.hint:
                        decision.show_hint = True
                    decision.line = _deck_line(active, manifest, retry=True)
                else:
                    nxt = _active(targets)
                    if nxt is None:
                        decision.line = ""
                        decision.finished = True
                    else:
                        decision.line = _deck_line(nxt, manifest, retry=False)
    if _targets_finished(targets) and not decision.finished:
        decision.finished = True
        if decision.source == "deck":
            decision.line = ""
    data["attempts"] = attempts
    if _active(targets) is not None:
        data["active_id"] = _active(targets).id
    updated_deck = deck.model_copy(update={"targets": targets})
    try:
        updated_state = state.__class__.model_validate(data)
    except ValidationError:
        updated_state = state
    return updated_deck, updated_state, decision


def wren_result_applies(service, session_id: str, token: int, sentence_id: str) -> bool:
    """A newer call, or a score for an older heard line, does not write."""
    with service._wren_lock:
        if service._wren_token.get(session_id) != token:
            return False
    row = service.store.get_session_row(session_id)
    if row is None or not sentence_id:
        return False
    from logoskittens.session import _sentence_models

    humans = [item.id for item in _sentence_models(row.sentences_json) if item.speaker == "human" and item.id]
    return bool(humans) and humans[-1] == sentence_id


def _invoke_prepare(plugin, graph, base: dict, manifest: GameManifest, raw_text: str, language_id: str, material_id: str):
    try:
        result = graph.invoke(dict(base))
    except WrenSkipped as exc:
        raise ValueError("Wren is not available") from exc
    if not isinstance(result, dict):
        raise ValueError("The prepare graph did not return a deck.")
    try:
        proposed = [DeckTarget.model_validate(item) for item in (result.get("deck") or {}).get("targets") or []]
    except ValidationError as exc:
        raise ValueError(f"The deck was not valid: {exc}") from exc
    kept = _ground(proposed, manifest, raw_text, list(base.get("target_languages") or []))
    state = plugin.state_type().model_validate(result.get("state") or {})
    if not kept:
        return _Ungrounded(manifest.id, language_id, material_id), state
    deck = GameDeck(game_id=manifest.id, language=language_id, material_id=material_id, targets=kept)
    return deck, state


class _Ungrounded:
    """Stand-in so a short deck can be counted without being stored."""

    def __init__(self, game_id: str, language: str, material_id: str):
        self.game_id = game_id
        self.language = language
        self.material_id = material_id
        self.targets: list = []


def _ground(
    proposed: list[DeckTarget], manifest: GameManifest, raw_text: str, targets: list[str] | None = None
) -> list[DeckTarget]:
    kept: list[DeckTarget] = []
    used: set[str] = set()
    needs_stem = manifest.deck_text == "stem" and (manifest.opening == "stem" or manifest.capabilities.deck_line)
    for target in proposed:
        phrase = target.phrase.strip()
        if not phrase:
            continue
        if manifest.phrase_grounding == "substring" and not contains_phrase(raw_text, phrase):
            continue
        stem = target.stem.strip()
        retry = target.retry_line.strip()
        forms = forms_of({"forms": target.forms}, phrase)
        # H13. A meaning check may ask about the phrase in its stem.
        if stem and not manifest.capabilities.judge_only and contains_phrase(stem, phrase):
            continue
        if retry and contains_phrase(retry, phrase):
            continue
        # H2. A line that says a form gives the answer away.
        if any((stem and not manifest.capabilities.judge_only and contains_phrase(stem, form)) or contains_phrase(retry, form) for form in forms):
            continue
        if needs_stem and (not stem or not retry):
            continue
        banned = [item.strip() for item in target.banned if item and item.strip() and len(item.strip()) <= 40][:24]
        gloss = gloss_of({"gloss": target.gloss}, list(targets or []))
        hint = target.hint.strip()
        if manifest.reveal_on_miss != "each" and hint and contains_phrase(hint, phrase):
            # A hint that spells out the answer would reveal it on the first miss.
            hint = ""
        # H8. Lead lines are kept as written. The emotion must be one the avatar knows. The mimic is checked
        # against the catalog when it is delivered, so a dropped token never drops the line.
        lead = [
            LeadLine(speaker=item.speaker, line=" ".join(item.line.split()))
            for item in target.lead
            if item.line.strip()
        ]
        emotion = target.emotion.strip() if target.emotion.strip() in _EMOTIONS else ""
        kept.append(
            target.model_copy(
                update={
                    "phrase": phrase,
                    "stem": stem,
                    "retry_line": retry,
                    "hint": hint,
                    "banned": banned,
                    "gloss": gloss,
                    "forms": forms,
                    "lead": lead,
                    "emotion": emotion,
                    "mimic": target.mimic.strip(),
                    "origin": target.origin.strip(),
                }
            )
        )
    numbered: list[DeckTarget] = []
    for index, target in enumerate(kept, start=1):
        ident = target.id.strip()
        if not ident or ident in used:
            ident = f"t{index}"
            while ident in used:
                index += 1
                ident = f"t{index}"
        used.add(ident)
        numbered.append(target.model_copy(update={"id": ident, "status": "pending"}))
    if numbered:
        numbered[0] = numbered[0].model_copy(update={"status": "active"})
    return numbered


def _opening_line(
    service,
    manifest: GameManifest,
    deck,
    person,
    language_id: str,
    partner_prompt: str,
    passage: str,
) -> str:
    if manifest.opening == "none":
        return ""
    active = _active(deck.targets)
    if active is None:
        raise ValueError("The deck has no active target.")
    if manifest.opening == "phrase":
        return active.phrase.strip()
    if manifest.opening == "stem":
        if not active.stem.strip():
            raise ValueError("The opening stem is empty.")
        return active.stem.strip()
    steer = ""
    if manifest.capabilities.hidden_steer:
        steer = active.prompt_to_partner.strip()
    shown = passage if manifest.show_source or manifest.partner_passage else ""
    system = _partner_system(partner_prompt, person, language_id, steer, shown)
    user = active.instruction.strip() or "Begin."
    line, _emotion = _partner_reply(service.complete_fn, user, system)
    if not line:
        raise ValueError("The opening line was empty.")
    return line


def _resolve_line(
    service, decision: TurnExit, deck: GameDeck, manifest: GameManifest, heard: str, row, steer: str, sentences=None
):
    if decision.source == "deck":
        return decision.line.strip(), "neutral"
    if decision.source != "partner":
        return "", "neutral"
    person = get_personality(row.language_id, row.personality_id)
    partner_prompt = load_game_prompt(manifest.id, "partner", row.language_id)
    passage = material_text(service, row) if manifest.show_source or manifest.partner_passage else ""
    system = _partner_system(partner_prompt, person, row.language_id, steer, passage)
    return _partner_reply(service.complete_fn, partner_user(sentences or [], heard), system)


PARTNER_HISTORY = 8


def partner_user(sentences, heard: str) -> str:
    """H1. The last 8 log lines before this response, as `- speaker: text`, then the latest heard line."""
    latest = max((item.response_index for item in sentences if item.speaker == "human"), default=0)
    earlier = [
        item
        for item in sentences
        if (getattr(item, "text", "") or "").strip()
        and not (item.speaker == "human" and item.response_index == latest)
    ][-PARTNER_HISTORY:]
    recent = "\n".join(f"- {item.speaker}: {item.text.strip()}" for item in earlier) or "- (none yet)"
    return f"recent:\n{recent}\nlatest_human: {heard.strip()}"


def _partner_system(prompt: str, person, language_id: str, steer: str, passage: str = "") -> str:
    parts = [prompt.strip(), _language_specifics(person, language_id).strip(), f"name: {person.name}"]
    if passage.strip():
        parts.append("passage:\n" + passage.strip())
    if steer.strip():
        parts.append(steer.strip())
    return "\n".join(part for part in parts if part)


def _partner_reply(complete: Callable, user: str, system: str) -> tuple[str, str]:
    for _attempt in range(2):
        raw, _record = complete(user, system=system, num_predict=128)
        line, emotion = _parse_partner(raw)
        if line:
            return line, emotion
    return "", "neutral"


def _parse_partner(raw: str) -> tuple[str, str]:
    try:
        payload = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return "", "neutral"
    if not isinstance(payload, dict):
        return "", "neutral"
    line = payload.get("line") or ""
    emotion = str(payload.get("emotion") or "neutral").strip()
    if not isinstance(line, str):
        return "", "neutral"
    if emotion not in _EMOTIONS:
        emotion = "neutral"
    return line.strip(), emotion


def _steer_text(decision: TurnExit, deck: GameDeck, manifest: GameManifest) -> str:
    suffix = decision.prompt_suffix.strip()
    if suffix:
        return suffix
    if not manifest.capabilities.hidden_steer:
        return ""
    active = _active(deck.targets)
    if active is None:
        return ""
    return active.prompt_to_partner.strip()


def _voice_and_store(
    service, session_id, row, sentences, solution, emit, tokens: list[str], timing=None, role: str = "buddy", speaker: str = ""
) -> None:
    from logoskittens.session import _deliver_voiced, _log_first_audio, _with_audio
    from logoskittens.content import language as language_doc
    from logoskittens.talk import SpokenSentence

    started = time.perf_counter()
    began = speed.clock()
    cached = pcm_cache(service, session_id).get(_pcm_key(solution))
    if cached is not None:
        speech = solution.speech.model_copy(update={"precomputed_audio_pcm": cached})
        voiced = solution.model_copy(update={"speech": speech})
    else:
        voiced = _with_audio(service.audio, solution)
    if timing is not None:
        timing.add("tts", (speed.clock() - began) * 1000)
        if cached is None:
            from logoskittens.speech.router import last_tts_via

            timing.tts_via = last_tts_via()
    try:
        recognizer = str(language_doc(row.language_id)["recognizer_model"])
    except KeyError:
        recognizer = ""
    _log_first_audio((time.perf_counter() - started) * 1000, recognizer, voiced.speech.voice_model_id, row.language_id or "")
    _deliver_voiced(
        service,
        voiced,
        session_id,
        row.language_id or "",
        _game_emit(emit),
        role=role,
        tokens=tokens,
        steer="",
        speaker=speaker,
    )
    if timing is not None:
        timing.first_audio()
    if sentences is None:
        return
    for piece in split_sentences(solution.speech.text):
        sentences.append(SpokenSentence(speaker="teacher" if role == "teacher" else "buddy", text=piece))
    _save_sentences(service, session_id, row, sentences)


def _schedule_score(service, session_id, game_id, plugin, sentence_id, user, emit, manifest, qa) -> None:
    def work() -> None:
        try:
            row = service.store.get_session_row(session_id)
            language_id = row.language_id if row is not None else "en"
            raw = _invoke_wren(
                service,
                game_id,
                "score",
                load_game_prompt(game_id, "wren", language_id),
                user,
            )
            payload = _object(raw)
        except WrenSkipped:
            _emit_quiet(service, session_id, emit, manifest, qa)
            return
        except (ValueError, json.JSONDecodeError):
            _emit_quiet(service, session_id, emit, manifest, qa)
            return
        with service._talk_lock:
            row = service.store.get_session_row(session_id)
            if row is None or not (row.deck_json or "").strip():
                return
            deck = GameDeck.model_validate_json(row.deck_json)
            state = plugin.state_type().model_validate_json(row.game_state_json or "{}")
            if getattr(state, "scoring_sentence_id", "") == sentence_id:
                return
            active = _active(deck.targets)
            if active is None or not isinstance(payload, dict):
                return
            target_id = payload.get("target_id")
            if not isinstance(target_id, str) or not target_id.strip():
                payload = {**payload, "target_id": active.id}
                target_id = active.id
            if active.id != target_id.strip():
                return
            before_targets = [target.model_copy() for target in deck.targets]
            before_attempts = dict(getattr(state, "attempts", {}) or {})
            try:
                deck, state, note = plugin.apply_wren(deck, state, payload)
            except (ValueError, ValidationError):
                _emit_quiet(service, session_id, emit, manifest, qa)
                return
            note = (note or "")[:240]
            _save_game(service, session_id, deck, state, note)
        feedback = _score_feedback(before_targets, before_attempts, deck, state)
        hits = sum(1 for target in deck.targets if target.status == "hit")
        miss_note = None
        if feedback == "miss":
            why = payload.get("why") if isinstance(payload, dict) else ""
            if not isinstance(why, str) or not why.strip():
                why = "That was not the line in the text."
            miss_note = _store_miss(service, session_id, row, sentence_id, why)
        emit(
            game_message(
                session_id=session_id,
                manifest=manifest,
                deck=deck,
                decision=TurnExit(feedback=feedback),
                qa=qa,
                steer="",
                finished=_is_finished(deck, TurnExit(), manifest),
                score={"kind": "hits", "hit": hits, "total": len(deck.targets)},
                show_hint=bool(getattr(state, "hint_on", False)),
                source=material_text(service, row),
                attempts=dict(getattr(state, "attempts", {}) or {}),
                miss_note=miss_note,
            )
        )

    service._launch(work)




def _mark_line(sentences, sentence_id: str, verdict: str, explanation: str, expected: str = "") -> dict | None:
    text = " ".join((explanation or "").split())[:500]
    wanted = " ".join((expected or "").split())[:500]
    for item in sentences:
        if getattr(item, "id", "") == sentence_id and getattr(item, "speaker", "") == "human":
            item.verdict = verdict
            if text:
                item.explanation = text
            if wanted:
                item.expected = wanted
            note = {"sentence_id": sentence_id, "verdict": verdict, "explanation": text}
            if wanted:
                note["expected"] = wanted
            return note
    return None


def _closing_line(manifest: GameManifest, language_id: str, deck) -> str:
    """The manifest's closing for this language, with the tally. Empty when the game has none."""
    template = (manifest.closing.get(language_id) or "").strip()
    if not template:
        return ""
    hits = sum(1 for target in deck.targets if target.status == "hit")
    return template.replace("{hits}", str(hits)).replace("{total}", str(len(deck.targets)))


def _deck_line(target: DeckTarget, manifest: GameManifest, *, retry: bool) -> str:
    """The deck string a `source: "deck"` turn speaks for this target."""
    if manifest.deck_text == "phrase":
        return target.phrase
    return target.retry_line if retry else target.stem


def _sentence_for_phrase(phrase: str, passage: str) -> str:
    for part in split_sentences(passage or ""):
        if phrase and contains_phrase(part, phrase):
            return part.strip()
    return ""


def _last_try(deck, state, manifest: GameManifest) -> bool:
    """A miss on this turn closes the active target. The judge may then say the answer."""
    active = _active(deck.targets)
    if active is None or manifest.max_attempts <= 0:
        return False
    attempts = dict(getattr(state, "attempts", {}) or {})
    return int(attempts.get(active.id, 0) or 0) + 1 >= manifest.max_attempts


def _asked_line(target: DeckTarget, attempts: dict) -> str:
    """The question on the log for this target: the stem first, the retry line after a miss."""
    if int(attempts.get(target.id, 0) or 0) > 0 and target.retry_line.strip():
        return target.retry_line.strip()
    return target.stem.strip()


def _judge_answer(
    service,
    game_id: str,
    language_id: str,
    deck,
    state,
    heard: str,
    kind: str,
    passage: str,
    feedback: str = "",
    timing=None,
    always: bool = False,
    last_try: bool = False,
) -> tuple[bool | None, str]:
    """Hit at once when the answer holds the phrase or a form, unless `always` (H13). Otherwise Wren judges.

    None means no verdict, and apply_local falls back to the local check.
    """
    active = _active(deck.targets)
    if active is None:
        return None, ""
    if not always and _target_hit(kind, heard, active):
        return True, ""
    attempts = dict(getattr(state, "attempts", {}) or {})
    user = "\n".join(
        [
            f"question: {_asked_line(active, attempts)}",
            f"expected: {active.phrase}",
            *([f"forms: {'; '.join(active.forms)}"] if active.forms else []),
            f"answer: {heard}",
            f"feedback_language: {feedback or language_id}",
            f"last_try: {'yes' if last_try else 'no'}",
            "passage:",
            passage.strip(),
        ]
    )
    began = speed.clock()
    try:
        raw = _invoke_wren(service, game_id, "judge", load_game_prompt(game_id, "judge", language_id), user)
    except (WrenSkipped, LLMError, ValueError) as exc:
        if timing is not None:
            timing.add("judge", (speed.clock() - began) * 1000)
        print(f"game judge failed id={game_id} error={type(exc).__name__}", file=sys.stderr, flush=True)
        return None, ""
    if timing is not None:
        timing.add("judge", (speed.clock() - began) * 1000)
    payload = _object(raw)
    verdict = payload.get("hit")
    if not isinstance(verdict, bool):
        print(f"game judge unreadable id={game_id}", file=sys.stderr, flush=True)
        return None, ""
    why = payload.get("why")
    return verdict, " ".join(why.split())[:240] if isinstance(why, str) else ""


def _verdict_note(sentences, human_id: str, decision: TurnExit, manifest: GameManifest, before_targets, deck, passage: str, why: str):
    """Mark the human line. What a miss reveals is the manifest's `reveal_on_miss` (H3)."""
    if decision.feedback not in {"match", "miss"}:
        return None
    asked = _active(before_targets)
    if asked is None:
        return None
    after = _target_by_id(deck.targets, asked.id)
    if decision.feedback == "match":
        if not manifest.show_source:
            return None
        return _mark_line(sentences, human_id, "correct", "")
    reveal = manifest.reveal_on_miss
    still_open = after is not None and after.status == "active"
    said = " ".join((why or "").split())
    if manifest.show_why == "never" or (manifest.show_why == "final" and still_open):
        said = ""
    lead = f"{said} " if said else ""
    if reveal == "each":
        return _mark_line(sentences, human_id, "wrong", f"{lead}The line was: {asked.phrase}", expected=asked.phrase)
    if reveal == "never" or still_open:
        return _mark_line(sentences, human_id, "wrong", said or ("Not quite. Try again." if still_open else "Not quite."))
    if manifest.show_source:
        told = _sentence_for_phrase(asked.phrase, passage) or asked.phrase
        return _mark_line(sentences, human_id, "wrong", f"{lead}The passage says: {told}")
    return _mark_line(sentences, human_id, "wrong", f"{lead}The line was: {asked.phrase}", expected=asked.phrase)


def _last_buddy_line(sentences) -> str:
    """The question the human just answered. The partner's new line is not that question."""
    for item in reversed(sentences):
        if getattr(item, "speaker", "") == "buddy" and getattr(item, "text", "").strip():
            return item.text.strip()
    return ""


def _score_user(prepared: str, heard: str, question: str, passage: str) -> str:
    """Score the answer against the question that was already asked."""
    parts = [(prepared or f"heard: {heard}").strip()]
    if question.strip():
        parts.append("question_answered:\n" + question.strip())
    if passage.strip():
        parts.append("passage:\n" + passage.strip())
    return "\n".join(parts)


def _tally(deck, attempts: dict | None) -> tuple[int, int]:
    matches = sum(1 for target in deck.targets if target.status == "hit")
    misses = 0
    for value in (attempts or {}).values():
        try:
            misses += int(value)
        except (TypeError, ValueError):
            continue
    return matches, misses


def _attempts_of(row) -> dict:
    try:
        payload = json.loads(row.game_state_json or "{}")
    except json.JSONDecodeError:
        return {}
    attempts = payload.get("attempts") if isinstance(payload, dict) else None
    return dict(attempts) if isinstance(attempts, dict) else {}


def _annotate_miss(sentences, sentence_id: str, explanation: str) -> dict | None:
    text = " ".join((explanation or "").split())[:500]
    if not text or not sentence_id:
        return None
    for item in sentences:
        if getattr(item, "id", "") == sentence_id and getattr(item, "speaker", "") == "human":
            item.explanation = text
            return {"sentence_id": sentence_id, "explanation": text}
    return None


def _store_miss(service, session_id: str, row, sentence_id: str, explanation: str) -> dict | None:
    from logoskittens.session import _sentence_models

    sentences = _sentence_models(row.sentences_json)
    note = _annotate_miss(sentences, sentence_id, explanation)
    if note is None:
        return None
    _save_sentences(service, session_id, row, sentences)
    return note


def _score_feedback(before_targets, before_attempts: dict, deck, state) -> str:
    """Match when the active phrase was accepted. Miss when a scored try failed."""
    active = _active(before_targets)
    if active is None:
        return "score"
    after = _target_by_id(deck.targets, active.id)
    if after is None:
        return "score"
    if after.status == "hit":
        return "match"
    attempts = dict(getattr(state, "attempts", {}) or {})
    if after.status == "missed" or attempts.get(after.id, 0) > before_attempts.get(after.id, 0):
        return "miss"
    return "score"


def _emit_quiet(service, session_id, emit, manifest, qa) -> None:
    print("game wren skipped", file=sys.stderr, flush=True)
    row = service.store.get_session_row(session_id)
    if row is None or not (row.deck_json or "").strip():
        return
    try:
        deck = GameDeck.model_validate_json(row.deck_json)
    except (ValueError, ValidationError):
        return
    emit(
        game_message(
            session_id=session_id,
            manifest=manifest,
            deck=deck,
            decision=TurnExit(feedback="quiet"),
            qa=qa,
            steer="",
            finished=_deck_finished(deck.targets),
            source=material_text(service, row),
            attempts=_attempts_of(row),
        )
    )


def _no_wren(user: str, *, system: str = "") -> str:
    """H9. A `local` game builds its deck in the plugin. It never reaches Wren."""
    del user, system
    raise WrenSkipped("This game prepares with no Wren")


def _bound_wren(service, game_id: str, purpose: str, spent: list[float] | None = None):
    def wren(user: str, *, system: str = "") -> str:
        began = speed.clock()
        try:
            return _invoke_wren(service, game_id, purpose, system, user)
        finally:
            if spent is not None:
                spent.append((speed.clock() - began) * 1000)

    return wren


def _invoke_wren(service, game_id: str, purpose: str, system: str, user: str) -> str:
    if service.wren_fn is not None:
        return service.wren_fn(user, system=system, purpose=purpose, game_id=game_id)
    from logoskittens.games.wren import call

    return call(game_id=game_id, purpose=purpose, system=system, user=user)


def _object(raw: str) -> dict:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Wren did not return an object.")
    return payload


def _save_sentences(service, session_id: str, row, sentences) -> None:
    with service._talk_lock:
        service.store.save_talk(
            session_id,
            material_id=row.material_id,
            subject_json=row.subject_json or "",
            sentences_json=json.dumps([item.model_dump() for item in sentences], ensure_ascii=False),
        )


def _save_game(service, session_id: str, deck, state: BaseModel, note: str) -> None:
    targets = getattr(deck, "targets", None)
    if not targets:
        return
    with service._talk_lock:
        service.store.save_game(
            session_id,
            deck.model_dump_json(),
            state.model_dump_json(),
            (note or "")[:240],
        )


def _game_emit(emit: Callable[[dict], None]) -> Callable[[dict], None]:
    def wrapped(payload: dict) -> None:
        if payload.get("type") == "actor":
            payload = {**payload, "game": True}
        emit(payload)

    return wrapped


def _target_hit(kind: str, heard: str, target: DeckTarget) -> bool:
    """H2. The phrase or any accepted form, with the same fold."""
    return any(_phrase_hit(kind, heard, text) for text in [target.phrase, *target.forms])


def _phrase_hit(kind: str, heard: str, phrase: str) -> bool:
    if kind == "exact":
        return same_phrase(heard, phrase)
    if kind == "contains":
        return contains_phrase(heard, phrase)
    return False


def _active(targets: list[DeckTarget]) -> DeckTarget | None:
    for target in targets:
        if target.status == "active":
            return target
    return None


def _target_by_id(targets: list[DeckTarget], target_id: str) -> DeckTarget | None:
    if not target_id:
        return None
    for target in targets:
        if target.id == target_id:
            return target
    return None


def _promote(targets: list[DeckTarget]) -> None:
    if _active(targets) is not None:
        return
    for index, target in enumerate(targets):
        if target.status == "pending":
            targets[index] = target.model_copy(update={"status": "active"})
            return


def _targets_finished(targets: list[DeckTarget]) -> bool:
    return bool(targets) and all(target.status not in {"pending", "active"} for target in targets)


def _deck_finished(targets: list[DeckTarget]) -> bool:
    return _targets_finished(targets)


def _round_closed(deck) -> bool:
    """H4. Closed by a finished turn or by Finish, or every target is closed."""
    return bool(getattr(deck, "closed", False)) or _deck_finished(getattr(deck, "targets", []))


def _is_finished(deck, decision: TurnExit, manifest: GameManifest) -> bool:
    if decision.finished and manifest.capabilities.end_score:
        return True
    return _round_closed(deck) or decision.finished


def _token() -> str:
    import uuid

    return uuid.uuid4().hex[:12]
