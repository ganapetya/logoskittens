"""Free-speech subject card, the last eight sentences, and one buddy line.

Human speech is stored as heard. Nothing in this module repairs it.
"""

import json
import re
import sys
import uuid
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from logoskittens.bob import buddy_turns, steer_block
from logoskittens.content import buddy_voice, language as language_doc, languages, prompt_text
from logoskittens.personalities import BuddyPersonality
from logoskittens.llm import LLMError
from logoskittens.primitives import (
    Actor,
    AudioPayloadModel,
    ElementSolutionModel,
    ScreenVisualCueModel,
)

WINDOW = 8
SUBJECT_PROMPT = "prompt-of-subject-creation"
INSTRUCTION_PROMPT = "ongoing_instruction_prompt"
PSEUDO_HUMAN_PROMPT = "pseudo_human"
BUDDY_ID = "buddy-one"

_EMOTIONS = {
    "neutral": "EMOTION_NEUTRAL",
    "curiosity": "EMOTION_CURIOSITY",
    "amusement": "EMOTION_AMUSEMENT",
    "encouragement": "EMOTION_ENCOURAGEMENT",
}


class LessonSubjectInput(BaseModel):
    used_words: list[str] = Field(min_length=1)
    significant_words: list[str] = Field(min_length=1)
    theme: str = Field(min_length=1)
    small_talk_subjects: list[str] = Field(min_length=1)
    important_words: list[str] = Field(default_factory=list)


class SpokenSentence(BaseModel):
    speaker: Literal["human", "buddy", "teacher"]
    text: str = Field(min_length=1)
    altered: bool = False
    steer: str = ""
    id: str = ""
    response_index: int = 0
    explanation: str = ""
    verdict: str = ""
    # The line a game expected, kept beside a wrong verdict so the page can show the word diff.
    expected: str = ""


class OngoingConversation(BaseModel):
    """The buddy's view of the talk. ``recent`` is the last eight sentences."""

    language: str
    lesson_subject_input: LessonSubjectInput
    recent: list[SpokenSentence]
    ongoing_instruction_prompt: str
    personality: BuddyPersonality | None = None
    bob_steer: str = ""
    reading_word: str = ""


class BuddyReply(BaseModel):
    line: str = Field(min_length=1)
    emotion: str = "neutral"


def clean_transcript(text: str) -> str:
    """Drop whisper special tokens. A caption-only result is silence.

    A comma between every word is the bias list copied back as speech. Join it.
    """
    cleaned = re.sub(r"<\|[^|>]*\|>", " ", text or "")
    cleaned = re.sub(r"\[(?:BLANK_AUDIO|NO_SPEECH|INAUDIBLE)\]", " ", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split())
    return _unwrap_comma_words(cleaned)


def _unwrap_comma_words(text: str) -> str:
    if text.count(",") < 2:
        return text
    parts = [part.strip() for part in text.split(",")]
    if len(parts) < 3 or not all(part and len(part.split()) <= 3 for part in parts):
        return text
    return " ".join(parts)


def split_sentences(text: str) -> list[str]:
    """One utterance may hold more than one sentence. A fragment stays whole."""
    body = text.strip()
    if not body:
        return []
    parts = re.findall(r"[^.!?]+[.!?]+|[^.!?]+$", body)
    cleaned = [part.strip() for part in parts if part.strip()]
    return cleaned or [body]


def last_sentences(sentences: list[SpokenSentence], limit: int = WINDOW) -> list[SpokenSentence]:
    if limit < 1:
        return []
    return sentences[-limit:]


def ongoing_for(
    subject: LessonSubjectInput,
    sentences: list[SpokenSentence],
    language: str,
    personality: BuddyPersonality | None = None,
    bob_steer: str = "",
    latest_human: str = "",
) -> OngoingConversation:
    return OngoingConversation(
        language=language,
        lesson_subject_input=subject,
        recent=last_sentences(sentences),
        ongoing_instruction_prompt=prompt_text(INSTRUCTION_PROMPT, language),
        personality=personality,
        bob_steer=bob_steer,
        reading_word=choose_reading_word(subject, sentences, latest_human, bob_steer),
    )


def steer_applies(latest_human: str, steer: str) -> bool:
    """True when this local call may use the steer.

    A question or a greeting ignores a statement hint. A question hint may be
    asked after answering a question, a greeting, or a line with no subject.
    """
    text = steer.strip()
    if not text:
        return False
    if _may_ask(latest_human, text):
        return True
    return not _direct(latest_human)


def subject_user(raw_text: str) -> str:
    return f"RAW MATERIAL:\n{raw_text.strip()}\n"


# The prompt's recent block keeps the newest lines that fit in this many characters.
# Eight short lines fit. Long Cyrillic lines no longer push the prompt past the context.
RECENT_CHARS = 900


def recent_within_budget(recent: list[SpokenSentence], budget: int = RECENT_CHARS) -> list[SpokenSentence]:
    """The newest sentences whose text fits ``budget`` characters. The latest one is always kept."""
    kept: list[SpokenSentence] = []
    total = 0
    for item in reversed(recent):
        size = len(item.text)
        if kept and total + size > budget:
            break
        kept.append(item)
        total += size
    kept.reverse()
    return kept


def buddy_user(ongoing: OngoingConversation, latest_human: str) -> str:
    subject = ongoing.lesson_subject_input
    window = recent_within_budget(ongoing.recent)
    said = [item.text for item in window if item.speaker == "buddy"]
    openings = [item for item in subject.small_talk_subjects if not _covers(item, said)]
    recent = "\n".join(f"- {item.speaker}: {item.text}" for item in window) or "- (none yet)"
    passive = _passive(latest_human)
    asked = _direct(latest_human)
    steered = steer_applies(latest_human, ongoing.bob_steer)
    talks = (
        "\n".join(f"- {item}" for item in openings) or "- (none left)"
        if passive
        else "- (do not ask one; answer the human)"
    )
    banned = "\n".join(f"- {item}" for item in said) or "- (none)"
    tail = ""
    if _may_ask(latest_human, ongoing.bob_steer):
        tail = (
            f'\nThe human said: "{latest_human.strip()}"\n'
            "Answer that first, in your own words. Do not copy their sentence.\n"
            "Then ask this private hint, in your own words:\n"
            f'"{ongoing.bob_steer.strip()}"\n'
            f"{_hint_clause(ongoing, latest_human)}"
            "Do not replace what they said with the question alone.\n"
        )
    elif asked and _mentions_theme(latest_human, ongoing):
        tail = (
            f'\nThe human asked: "{latest_human.strip()}"\n'
            "Answer that question. Do not add a story about something else.\n"
        )
    elif asked:
        tail = (
            f'\nThe human asked: "{latest_human.strip()}"\n'
            "Answer that in one short sentence. Stop. Do not add a story or a detail from the theme.\n"
        )
    elif steered:
        tail = (
            f'\nThe human said: "{latest_human.strip()}"\n'
            "Answer that in your own words. Do not copy their sentence.\n"
            "This private hint replaces the theme detail for this turn:\n"
            f'"{ongoing.bob_steer.strip()}"\n'
            "The part you must use is its last sentence.\n"
            f"{_hint_clause(ongoing, latest_human)}"
            "Do not replace what they said with the hint alone.\n"
        )
    elif not passive:
        tail = (
            f'\nThe human brought this up: "{latest_human.strip()}"\n'
            "Acknowledge it in your own words. Do not copy their sentence. Then add one detail from the theme. Do not ask a question from the card.\n"
            f"{_reading_clause(ongoing.reading_word)}"
        )
    return (
        f"language: {ongoing.language}\n"
        f"{_personality_block(ongoing.personality)}"
        f"{_language_specifics(ongoing.personality, ongoing.language)}"
        f"theme: {subject.theme}\n"
        f"used_words: {', '.join(subject.used_words)}\n"
        f"significant_words: {', '.join(subject.significant_words)}\n"
        f"small_talk_subjects:\n{talks}\n"
        f"do_not_repeat:\n{banned}\n"
        f"recent:\n{recent}\n"
        f"latest_human: {latest_human}\n"
        f"{tail}"
    )


def create_subject(raw_text: str, language: str, complete) -> LessonSubjectInput:
    system = prompt_text(SUBJECT_PROMPT, language)
    user = subject_user(raw_text)
    raw, _record = complete(user, system=system, num_predict=1024)
    try:
        return _ground_subject(_parse(raw, LessonSubjectInput, "subject card"), raw_text)
    except LLMError:
        snippet = " ".join(raw.split())[:180]
        print(f"subject card was not JSON: {snippet}", file=sys.stderr, flush=True)
        raw, _record = complete(
            user
            + "\nReturn one JSON object and nothing else. "
            "Keys: used_words, significant_words, theme, small_talk_subjects, important_words.\n",
            system=system,
            num_predict=1024,
            think="off",
        )
        return _ground_subject(_parse(raw, LessonSubjectInput, "subject card"), raw_text)


def buddy_reply(ongoing: OngoingConversation, latest_human: str, complete) -> BuddyReply:
    user = buddy_user(ongoing, latest_human)
    system = ongoing.ongoing_instruction_prompt + steer_block(ongoing.bob_steer)
    reply = _complete_buddy(user, system, complete)
    reply = _prefer_human_meaning(reply, ongoing, latest_human)
    reply = _without_echo(reply, latest_human)
    if _acceptable(reply.line, ongoing, latest_human):
        return reply
    story = _adds_theme_story(reply.line, ongoing, latest_human)
    aside = _third_person_self(reply.line, ongoing)
    banned = reply.line.strip()
    missed = (
        steer_applies(latest_human, ongoing.bob_steer)
        and bool(hint_words(ongoing.bob_steer, ongoing, latest_human))
        and not steer_taken(banned, ongoing.bob_steer, ongoing, latest_human)
    )
    copied = _echoes_human(latest_human, banned)
    reason = (
        "spoke in the third person"
        if aside
        else "added a theme story"
        if story
        else "repeated the human"
        if copied
        else "ignored the hint"
        if missed
        else "ignored the latest sentence"
    )
    print(f"buddy {reason}: {banned[:180]}", file=sys.stderr, flush=True)
    if not aside and not copied and not _reasks_soft_misses(ongoing.language):
        return _kept_soft_miss(reply, ongoing, latest_human, story)
    if aside:
        name = ongoing.personality.name if ongoing.personality else "yourself"
        specifics = _language_specifics(ongoing.personality, ongoing.language).strip()
        notes = [
            f'Do not talk about yourself as "{name}".',
            specifics or "Speak in the first person. Use I, me, and my.",
            f'The human asked: "{latest_human.strip()}"',
            "Answer that. Keep the same meaning.",
        ]
    elif story:
        dropped = [item for item in split_sentences(banned) if _mentions_theme(item, ongoing)]
        notes = [f'Do not say this: "{item}"' for item in dropped]
        notes.append(f'The human asked: "{latest_human.strip()}"')
        notes.append("Answer in one short sentence. Do not mention the theme.")
    else:
        notes = [f'Do not say this again: "{banned}"']
        if copied:
            notes.append(f'The human said: "{latest_human.strip()}"')
            notes.append("Do not repeat their sentence.")
            notes.append("Answer the point in your own words. Name the subject once.")
            fresh = hint_words(ongoing.bob_steer, ongoing, latest_human)[:6]
            if fresh:
                notes.append(f"Use at least one of these new words: {', '.join(fresh)}.")
        elif missed:
            words = ", ".join(hint_words(ongoing.bob_steer, ongoing, latest_human)[:6])
            notes.append(f'The human said: "{latest_human.strip()}"')
            notes.append("Answer the point in your own words. Do not copy their sentence.")
            notes.append(f"Use at least one of these new words: {words}.")
            notes.append("A theme word does not count. Do not replace what they said.")
        elif _breaks_human(latest_human, banned):
            notes.append(f'The human said: "{latest_human.strip()}"')
            notes.append("Answer only that, in your own words. Do not copy their sentence.")
            notes.append("Leave the side-track out.")
        elif _passive(latest_human):
            notes.append("Answer the latest human sentence. Add a new detail from the theme.")
        elif _direct(latest_human) and _mentions_theme(latest_human, ongoing):
            notes.append(f'The human asked: "{latest_human.strip()}"')
            notes.append("Answer that question. Do not add a story about something else.")
        elif _direct(latest_human):
            notes.append(f'The human asked: "{latest_human.strip()}"')
            notes.append("Answer that in one short sentence. Stop. Do not mention the theme.")
        else:
            notes.append(f'The human brought this up: "{latest_human.strip()}"')
            notes.append("Acknowledge it in your own words. Do not copy their sentence. Then add one detail from the theme. Do not ask a question from the card.")
    notes.append('Return one JSON object and nothing else: {"line": "<what you say>", "emotion": "neutral"}')
    reply = _complete_buddy(user + "\n" + "\n".join(notes) + "\n", system, complete, num_predict=768, think="off")
    reply = _prefer_human_meaning(reply, ongoing, latest_human)
    reply = _without_echo(reply, latest_human)
    if _acceptable(reply.line, ongoing, latest_human):
        return reply
    if _passive(latest_human):
        opening = _unused_opening(ongoing)
        if opening:
            return BuddyReply(line=opening, emotion="curiosity")
    spoken = _as_first_person(reply.line, ongoing) or reply.line
    short = _without_theme_story(spoken, ongoing, latest_human)
    if short:
        return BuddyReply(line=short, emotion=reply.emotion)
    if spoken != reply.line:
        return BuddyReply(line=spoken, emotion=reply.emotion)
    if _repeats(spoken, ongoing):
        opening = _unused_opening(ongoing)
        if opening:
            return BuddyReply(line=opening, emotion="curiosity")
    return reply


def _complete_buddy(user: str, system: str, complete, num_predict: int = 512, think: str | None = None) -> BuddyReply:
    kwargs: dict = {"num_predict": num_predict}
    if think is not None:
        kwargs["think"] = think
    raw, _record = complete(user, system=system, **kwargs)
    try:
        return _finish_buddy(raw)
    except LLMError:
        snippet = " ".join(raw.split())[:180]
        print(f"buddy reply was not JSON: {snippet}", file=sys.stderr, flush=True)
        raw, _record = complete(
            user + '\nReturn one JSON object and nothing else: {"line": "<what you say>", "emotion": "neutral"}\n',
            system=system,
            num_predict=768,
            think="off",
        )
        return _finish_buddy(raw)


def _personality_block(person: BuddyPersonality | None) -> str:
    if person is None:
        return ""
    home = f"\nhome: {person.home}" if person.home else ""
    nature = person.nature.strip()
    nature_line = f"\nnature: {nature}" if nature else ""
    alias = person.alias.strip()
    alias_line = f"\nalias: {alias}" if alias else ""
    asked = "name, gender, mood, tastes, or beliefs"
    if nature or alias:
        parts = ["name"]
        if alias:
            parts.append("alias")
        parts.extend(["gender"])
        if nature:
            parts.append("nature")
        parts.extend(["mood", "tastes", "or beliefs"])
        asked = ", ".join(parts)
    hold = ""
    if nature:
        hold += (
            "Nature is what you are. When asked, say it in that short sentence. "
            "Do not turn the theme into a lesson about it.\n"
        )
    if alias:
        hold += "Your alias is another name you answer to. Your name stays the one written above. Speak as I.\n"
    return (
        "personality:\n"
        f"name: {person.name}\n"
        f"gender: {person.gender}\n"
        f"mood: {person.mood}{home}\n"
        f"stance: {person.stance}\n"
        f"likes: {', '.join(person.likes)}{nature_line}{alias_line}\n"
        f"You are this person. If asked your {asked}, answer from this block in one short sentence. "
        "Do not deny a trait written here. Do not add a story after the answer.\n"
        f"{hold}"
    )


_EN_SPECIFICS = (
    "language_specifics:\n"
    "person: 1st\n"
    "gender: {gender}\n"
    "Speak in the first person. Use I, me, and my. "
    "You are a {gender}. Do not use your name as the subject. Do not say {other} about yourself.\n"
)


def _language_specifics(person: BuddyPersonality | None, language_id: str = "en") -> str:
    """Pronoun instructions from the language pack. A missing template stays English."""
    if person is None:
        return ""
    gender = person.gender.strip() or "person"
    other = {"man": "he", "woman": "she"}.get(gender, "they")
    gender_word = gender
    doc: dict = {}
    try:
        doc = language_doc(language_id)
    except KeyError:
        doc = {}
    words = doc.get("gender_words") or {}
    others = doc.get("other_words") or {}
    if isinstance(words, dict) and words.get(gender):
        gender_word = str(words[gender])
    if isinstance(others, dict) and others.get(gender):
        other = str(others[gender])
    template = str(doc.get("language_specifics") or "").strip()
    if not template:
        template = _EN_SPECIFICS
    elif not template.startswith("language_specifics:"):
        template = "language_specifics:\n" + template
    if not template.endswith("\n"):
        template += "\n"
    try:
        return template.format(gender=gender, gender_word=gender_word, other=other)
    except (KeyError, IndexError, ValueError):
        return _EN_SPECIFICS.format(gender=gender, gender_word=gender_word, other=other)


def _reasks_soft_misses(language_id: str) -> bool:
    """A soft miss (theme story, missed hint, a line the word checks think ignores the human)
    costs a second model call only where the pack asks for it. The word checks compare word
    forms, so an inflected language trips them on good lines."""
    try:
        doc = language_doc(language_id)
    except KeyError:
        return True
    return bool(doc.get("reask_soft_misses", True))


def _kept_soft_miss(reply: BuddyReply, ongoing: OngoingConversation, latest_human: str, story: bool) -> BuddyReply:
    """The first reply, cleaned without another model call."""
    line = reply.line.strip()
    if story:
        short = _without_theme_story(line, ongoing, latest_human)
        if short:
            return BuddyReply(line=short, emotion=reply.emotion)
    if _repeats(line, ongoing):
        opening = _unused_opening(ongoing)
        if opening:
            return BuddyReply(line=opening, emotion="curiosity")
    print(f"buddy kept without a second call ({ongoing.language})", file=sys.stderr, flush=True)
    return reply


def _rewrites_first_person(language_id: str) -> bool:
    try:
        doc = language_doc(language_id)
    except KeyError:
        return True
    return bool(doc.get("first_person_rewrite", True))


def solution_for(
    reply: BuddyReply,
    actor: Actor,
    language: str,
    voice_id: str = "",
) -> ElementSolutionModel:
    voice = voice_id or buddy_voice(language) or actor.embodiment.voice_profile.voice_id
    return ElementSolutionModel(
        solution_id=f"sol-{uuid.uuid4().hex[:12]}",
        actor_id=actor.actor_id,
        emotion=_EMOTIONS[reply.emotion],
        speech=AudioPayloadModel(
            text=reply.line,
            language_code=language,
            voice_model_id=voice,
        ),
        physical_gestures=[],
        screen_visuals=ScreenVisualCueModel(animation_id="nod", focus_target_id="human"),
    )


def active_buddy(actors: dict[str, Actor]) -> Actor:
    chosen = actors.get(BUDDY_ID)
    if chosen is None or not chosen.active:
        raise KeyError(BUDDY_ID)
    return chosen


def choose_reading_word(
    subject: LessonSubjectInput,
    sentences: list[SpokenSentence],
    latest_human: str,
    steer: str = "",
) -> str:
    """One practice word for this turn, or nothing.

    The word is optional. A question, a greeting, a passive line, and a turn
    that already carries a steer do not get one. A word the buddy has already
    said is not offered again. While any practice word is still in the last
    eight sentences, the turn stays quiet. Eligible turns alternate.
    """
    words = [word.strip() for word in subject.important_words if word.strip()]
    if not words or not latest_human.strip():
        return ""
    if _direct(latest_human) or _passive(latest_human) or steer_applies(latest_human, steer):
        return ""
    buddy_said = _norm(" ".join(item.text for item in sentences if item.speaker == "buddy"))
    unused = [word for word in words if not _phrase_in(word, buddy_said)]
    if not unused:
        return ""
    recent = _norm(" ".join(item.text for item in last_sentences(sentences)))
    if any(_phrase_in(word, recent) for word in words):
        return ""
    if buddy_turns([item.speaker for item in sentences]) % 2 == 1:
        return ""
    return unused[0]


def _reading_clause(word: str) -> str:
    cleaned = word.strip()
    if not cleaned:
        return ""
    return (
        f'If it fits, let that detail use this word from the reading: "{cleaned}". '
        "Leave the word out when it does not fit. Do not build the line around it.\n"
    )


def _phrase_in(phrase: str, normalized_text: str) -> bool:
    body = _norm(phrase)
    if not body:
        return False
    return f" {body} " in f" {normalized_text} "


def _ground_subject(card: LessonSubjectInput, raw_text: str = "") -> LessonSubjectInput:
    used = _dedupe(card.used_words)
    if not used:
        raise LLMError("subject card has no used words")
    allowed = {word.casefold(): word for word in used}
    significant: list[str] = []
    for word in _dedupe(card.significant_words):
        match = allowed.get(word.casefold())
        if match and match not in significant:
            significant.append(match)
    if not significant:
        raise LLMError("subject card has no significant words from the used words")
    talks = [item.strip() for item in card.small_talk_subjects if item.strip()]
    if not talks:
        raise LLMError("subject card has no small-talk subjects")
    theme = card.theme.strip()
    if not theme:
        raise LLMError("subject card has no theme")
    return LessonSubjectInput(
        used_words=used,
        significant_words=significant,
        theme=theme,
        small_talk_subjects=talks,
        important_words=_important_from(card.important_words, raw_text, significant),
    )


_GLUE = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "with",
        "from",
        "by",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "it",
        "its",
        "this",
        "that",
        "these",
        "those",
        "we",
        "our",
        "you",
        "your",
        "they",
        "their",
        "them",
        "he",
        "she",
        "his",
        "her",
        "i",
        "me",
        "my",
        "not",
        "no",
        "so",
        "too",
        "very",
        "just",
        "than",
        "then",
        "there",
        "here",
        "into",
        "over",
        "about",
        "also",
        "have",
        "has",
        "had",
    }
)


def _important_from(words: list[str], raw_text: str, significant: list[str]) -> list[str]:
    """Practice words that occur in the sentences and are not already theme anchors."""
    hay = _norm(raw_text)
    taken = {_norm(item) for item in significant}
    chosen: list[str] = []
    seen: set[str] = set()
    for word in _dedupe(words):
        phrase = _norm(word)
        if not phrase or phrase in seen or phrase in taken:
            continue
        tokens = phrase.split()
        if all(token in _GLUE for token in tokens):
            continue
        if not _phrase_in(word, hay):
            continue
        seen.add(phrase)
        chosen.append(word.strip())
        if len(chosen) == 12:
            break
    return chosen


def _dedupe(words: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for word in words:
        cleaned = word.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _finish_buddy(raw: str) -> BuddyReply:
    reply = _buddy_from(raw)
    if not reply.line.strip():
        raise LLMError("buddy reply was empty")
    emotion = reply.emotion.strip().lower()
    if emotion not in _EMOTIONS:
        emotion = "neutral"
    return BuddyReply(line=reply.line.strip(), emotion=emotion)


def _buddy_from(raw: str) -> BuddyReply:
    text = _strip_think(raw)
    try:
        payload = json.loads(_json_object(text, "buddy reply"))
    except (LLMError, json.JSONDecodeError):
        sentence = _plain_line(text)
        if not sentence:
            raise LLMError("buddy reply was not JSON")
        payload = {"line": sentence, "emotion": "neutral"}
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if isinstance(payload, str):
        payload = {"line": payload, "emotion": "neutral"}
    if not isinstance(payload, dict):
        raise LLMError("buddy reply was not JSON")
    if not str(payload.get("line") or "").strip():
        for key in ("text", "reply", "message", "response", "utterance"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                payload["line"] = value.strip()
                break
    if not isinstance(payload.get("emotion"), str):
        payload["emotion"] = "neutral"
    try:
        return BuddyReply.model_validate(payload)
    except ValidationError as exc:
        raise LLMError("buddy reply was not JSON") from exc


# Letters and digits in any script. An apostrophe inside a word stays (don't, м'ята, п’ять).
_WORD = re.compile(r"'?[^\W_]+(?:['’][^\W_]+)*'?")


def _norm(text: str) -> str:
    return " ".join(word.replace("’", "'") for word in _WORD.findall(text.casefold()))


def _echoes_human(latest_human: str, line: str) -> bool:
    """True when the reply pastes the human sentence instead of answering it."""
    human_words = _norm(latest_human).split()
    if len(human_words) < 4:
        return False
    return " ".join(human_words) in _norm(line)


def _drop_copied_prefix(sentence: str, latest_human: str) -> str:
    human_words = _norm(latest_human).split()
    if len(human_words) < 4:
        return sentence
    matches = list(_WORD.finditer(sentence))
    reply_words = [_norm(match.group()) for match in matches]
    count = len(human_words)
    if len(reply_words) < count or reply_words[:count] != human_words:
        return sentence
    rest = sentence[matches[count - 1].end():].lstrip(" \t,;:-")
    rest = re.sub(r"^(and|but|so)\b[, ]*", "", rest, count=1, flags=re.IGNORECASE).strip()
    return rest


def _without_echo(reply: BuddyReply, latest_human: str) -> BuddyReply:
    """Cut a leading copy of the human sentence. A later sentence can stay."""
    parts = split_sentences(reply.line)
    if not parts:
        return reply
    kept = []
    for part in parts:
        stripped = _drop_copied_prefix(part, latest_human)
        if not stripped or _echoes_human(latest_human, stripped):
            continue
        if _norm(stripped) in {"too", "yeah", "yes", "also"}:
            continue
        kept.append(stripped)
    if not kept:
        return reply
    line = " ".join(kept).strip()
    if line == reply.line.strip():
        return reply
    return BuddyReply(line=line, emotion=reply.emotion)


def _covers(candidate: str, lines: list[str]) -> bool:
    """True when the candidate is a buddy line already spoken, or contains one."""
    fresh = _norm(candidate)
    if not fresh:
        return False
    for line in lines:
        old = _norm(line)
        if not old:
            continue
        if fresh == old:
            return True
        if len(old.split()) >= 5 and f" {old} " in f" {fresh} ":
            return True
        if len(fresh.split()) >= 5 and f" {fresh} " in f" {old} ":
            return True
    return False


_PASSIVE = frozenset({"yes", "yeah", "yep", "ok", "okay", "mhm", "mm", "sure", "nice", "i guess"})


def _pack_phrases(key: str) -> set[str]:
    """Short phrases named by any language pack. A new pack does not need a Python branch."""
    found: set[str] = set()
    try:
        packs = languages()
    except (FileNotFoundError, ValueError, OSError):
        return found
    for doc in packs.values():
        raw = doc.get(key) or []
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            continue
        for item in raw:
            phrase = _norm(str(item))
            if phrase:
                found.add(phrase)
    return found


def _passive(text: str) -> bool:
    passive = _PASSIVE | _pack_phrases("passive")
    norm = _norm(text)
    if not norm or norm in passive:
        return True
    words = norm.split()
    return len(words) <= 2 and words[0] in passive


def _uses_card(line: str, ongoing: OngoingConversation) -> bool:
    return _covers(line, list(ongoing.lesson_subject_input.small_talk_subjects))


def _acceptable(line: str, ongoing: OngoingConversation, latest_human: str) -> bool:
    if _repeats(line, ongoing):
        return False
    if _third_person_self(line, ongoing):
        return False
    if _adds_theme_story(line, ongoing, latest_human):
        return False
    if _echoes_human(latest_human, line):
        return False
    if _breaks_human(latest_human, line):
        return False
    if (
        steer_applies(latest_human, ongoing.bob_steer)
        and hint_words(ongoing.bob_steer, ongoing, latest_human)
        and not steer_taken(line, ongoing.bob_steer, ongoing, latest_human)
    ):
        return False
    return _passive(latest_human) or not _uses_card(line, ongoing)


def _content_words(text: str) -> set[str]:
    extra = {"else", "know", "want", "tell", "please"}
    return {_stem(word) for word in _norm(text).split() if len(word) >= 4 and word not in _STEER_SKIP and word not in extra}


def steer_shows(line: str, steer: str, latest_human: str) -> bool:
    """True when the reply used a hint word the human did not say."""
    spoken = {_stem(word) for word in _norm(line).split()}
    return bool((_content_words(steer) - _content_words(latest_human)) & spoken)


def _may_ask(latest_human: str, steer: str) -> bool:
    """A question hint is asked after the answer, including when the human named a subject."""
    del latest_human
    return "?" in steer


_VAGUE = frozenset(
    {
        "amazing",
        "cool",
        "feel",
        "feeling",
        "fine",
        "good",
        "great",
        "happen",
        "okay",
        "happening",
        "interesting",
        "nice",
        "really",
        "stuff",
        "thing",
        "today",
        "well",
    }
)


def _unspecific(text: str) -> bool:
    """True when the line does not take up a subject of its own."""
    if _passive(text):
        return True
    words = _content_words(text)
    return not words or words <= _VAGUE


def _breaks_human(latest_human: str, line: str) -> bool:
    """True when a content line was answered without any of its content words."""
    wanted = _content_words(latest_human)
    if not wanted or _direct(latest_human) or _passive(latest_human) or _unspecific(latest_human):
        return False
    spoken = {_stem(word) for word in _norm(line).split()}
    return not bool(wanted & spoken)


def _prefer_human_meaning(reply: BuddyReply, ongoing: OngoingConversation, latest_human: str) -> BuddyReply:
    """Drop a bolted-on sentence that neither answers the human nor carries the new hint."""
    if not steer_applies(latest_human, ongoing.bob_steer) or not _content_words(latest_human):
        return reply
    if _may_ask(latest_human, ongoing.bob_steer):
        return reply
    parts = split_sentences(reply.line)
    if len(parts) < 2:
        return reply
    fresh = set(hint_words(ongoing.bob_steer, ongoing, latest_human))
    kept = []
    for part in parts:
        if not _breaks_human(latest_human, part):
            kept.append(part)
            continue
        spoken = {_stem(word) for word in _norm(part).split()}
        if fresh and fresh & spoken:
            kept.append(part)
    if not kept or len(kept) == len(parts):
        return reply
    return BuddyReply(line=" ".join(kept).strip(), emotion=reply.emotion)


_STEER_SKIP = frozenset(
    {
        "about",
        "after",
        "again",
        "already",
        "also",
        "another",
        "anything",
        "around",
        "away",
        "back",
        "been",
        "before",
        "being",
        "between",
        "both",
        "bring",
        "compare",
        "could",
        "drop",
        "each",
        "even",
        "from",
        "have",
        "here",
        "instead",
        "into",
        "just",
        "leave",
        "like",
        "many",
        "mention",
        "more",
        "most",
        "move",
        "much",
        "only",
        "onto",
        "other",
        "over",
        "rather",
        "same",
        "shift",
        "should",
        "some",
        "something",
        "start",
        "still",
        "stop",
        "such",
        "switch",
        "talk",
        "talking",
        "than",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "under",
        "upon",
        "using",
        "very",
        "what",
        "when",
        "where",
        "which",
        "while",
        "with",
        "would",
        "your",
    }
)


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("s"):
        return word[:-1]
    return word


def _steer_context(ongoing: OngoingConversation) -> set[str]:
    subject = ongoing.lesson_subject_input
    chunks = [item.text for item in ongoing.recent]
    chunks.append(subject.theme)
    chunks.extend(subject.used_words)
    chunks.extend(subject.significant_words)
    chunks.extend(subject.small_talk_subjects)
    return {_stem(word) for word in _norm(" ".join(chunks)).split()}


def hint_words(steer: str, ongoing: OngoingConversation, latest_human: str) -> list[str]:
    """New words from the last sentence of the hint. Words already in the talk do not count."""
    parts = split_sentences(steer)
    last = parts[-1] if parts else steer
    found = _fresh_words(last, ongoing, latest_human)
    if found:
        return found
    return _fresh_words(steer, ongoing, latest_human)


def _fresh_words(text: str, ongoing: OngoingConversation, latest_human: str) -> list[str]:
    context = _steer_context(ongoing)
    context |= {_stem(word) for word in _norm(latest_human).split()}
    found: list[str] = []
    for word in _norm(text).split():
        if len(word) < 4 or word in _STEER_SKIP:
            continue
        stem = _stem(word)
        if stem in context or stem in found:
            continue
        found.append(stem)
    return found


def steer_taken(line: str, steer: str, ongoing: OngoingConversation, latest_human: str) -> bool:
    """True when the reply uses a new hint word, not a word already in the theme."""
    fresh = hint_words(steer, ongoing, latest_human)
    if not fresh:
        return False
    spoken = {_stem(word) for word in _norm(line).split()}
    return any(word in spoken for word in fresh)


def _hint_clause(ongoing: OngoingConversation, latest_human: str) -> str:
    words = hint_words(ongoing.bob_steer, ongoing, latest_human)[:6]
    if not words:
        return ""
    return f"Use at least one of these new words: {', '.join(words)}. A theme word does not count.\n"


def steer_landed(line: str, steer: str, ongoing: OngoingConversation) -> bool:
    """True when the reply uses a steer word that was not already in the talk."""
    context = _steer_context(ongoing)
    fresh = [
        _stem(word)
        for word in _norm(steer).split()
        if len(word) >= 4 and word not in _STEER_SKIP and _stem(word) not in context
    ]
    if not fresh:
        return True
    spoken = {_stem(word) for word in _norm(line).split()}
    return any(word in spoken for word in fresh)


_TO_FIRST = {
    "likes": "like",
    "thinks": "think",
    "wants": "want",
    "is": "am",
    "has": "have",
    "does": "do",
    "goes": "go",
    "needs": "need",
    "feels": "feel",
    "uses": "use",
    "buys": "buy",
}


def _third_person_self(line: str, ongoing: OngoingConversation) -> bool:
    """The buddy's own name used as someone being talked about, not as 'my name is'."""
    person = ongoing.personality
    if person is None or not person.name.strip():
        return False
    name = _norm(person.name)
    body = _norm(line)
    for phrase in (
        f"my name is {name}",
        f"i am {name}",
        f"i'm {name}",
        f"this is {name}",
        f"call me {name}",
        f"jeg heter {name}",
        f"mitt navn er {name}",
        f"navnet mitt er {name}",
    ):
        body = body.replace(phrase, " ")
    return name in body.split()


def _as_first_person(line: str, ongoing: OngoingConversation) -> str:
    if not _rewrites_first_person(ongoing.language):
        return ""
    if not _third_person_self(line, ongoing):
        return ""
    name = re.escape(ongoing.personality.name)
    verbs = "|".join(_TO_FIRST)
    text = re.sub(rf"\b{name}'s\b", "my", line, flags=re.IGNORECASE)

    def _verb(match: re.Match[str]) -> str:
        return "I " + _TO_FIRST[match.group(1).lower()]

    text = re.sub(rf"\b{name}\s+({verbs})\b", _verb, text, flags=re.IGNORECASE)
    text = re.sub(rf"\b{name}\b", "I", text, flags=re.IGNORECASE)
    text = re.sub(rf"\bI\s+({verbs})\b", _verb, text, flags=re.IGNORECASE)
    text = re.sub(r"\bI\s+I\b", "I", text)
    return " ".join(text.split())


_GREETING = frozenset({"hello", "hi", "hey", "good morning", "good evening", "good afternoon"})
_QUESTION = frozenset(
    {
        "what",
        "whats",
        "who",
        "whose",
        "where",
        "when",
        "why",
        "how",
        "which",
        "do",
        "does",
        "did",
        "are",
        "is",
        "am",
        "was",
        "were",
        "can",
        "could",
        "would",
        "will",
        "have",
        "has",
        "should",
    }
)


def _direct(text: str) -> bool:
    """A question or a greeting. The answer stops there."""
    if "?" in text:
        return True
    words = _norm(text).split()
    if not words:
        return False
    greetings = _GREETING | _pack_phrases("greetings")
    if " ".join(words) in greetings:
        return True
    hello = {"hello", "hi", "hey"} | {item for item in greetings if " " not in item}
    if words[0] in hello:
        words = words[1:]
    questions = _QUESTION | _pack_phrases("question_words")
    return bool(words) and words[0] in questions


def _theme_tokens(ongoing: OngoingConversation) -> set[str]:
    subject = ongoing.lesson_subject_input
    tokens: set[str] = set()
    for item in list(subject.used_words) + list(subject.significant_words):
        for word in _norm(item).split():
            if len(word) >= 4:
                tokens.add(word)
    return tokens


def _mentions_theme(line: str, ongoing: OngoingConversation) -> bool:
    return bool(_theme_tokens(ongoing) & set(_norm(line).split()))


def _adds_theme_story(line: str, ongoing: OngoingConversation, latest_human: str) -> bool:
    """A direct question that did not mention the theme should not grow a theme sentence."""
    if not _direct(latest_human) or _mentions_theme(latest_human, ongoing):
        return False
    parts = split_sentences(line)
    if _may_ask(latest_human, ongoing.bob_steer):
        parts = [item for item in parts if "?" not in item]
    return any(_mentions_theme(item, ongoing) for item in parts)


def _without_theme_story(line: str, ongoing: OngoingConversation, latest_human: str) -> str:
    if not _adds_theme_story(line, ongoing, latest_human):
        return ""
    keep_question = _may_ask(latest_human, ongoing.bob_steer)
    kept = [
        item
        for item in split_sentences(line)
        if (keep_question and "?" in item) or not _mentions_theme(item, ongoing)
    ]
    return " ".join(kept).strip()


def _repeats(line: str, ongoing: OngoingConversation) -> bool:
    said = [item.text for item in ongoing.recent if item.speaker == "buddy"]
    return _covers(line, said)


def _unused_opening(ongoing: OngoingConversation) -> str:
    said = [item.text for item in ongoing.recent if item.speaker == "buddy"]
    for item in ongoing.lesson_subject_input.small_talk_subjects:
        if not _covers(item, said):
            return item
    return ""


def _plain_line(text: str) -> str:
    """A spoken sentence with no JSON object is still a line."""
    if "{" in text:
        return ""
    sentence = text.strip().strip("`").strip()
    if sentence.lower().startswith("json"):
        sentence = sentence[4:].strip()
    if not sentence or len(sentence) > 500:
        return ""
    return sentence


def _parse(raw: str, model: type[BaseModel], label: str) -> BaseModel:
    text = _strip_think(raw)
    try:
        payload = json.loads(_json_object(text, label))
    except json.JSONDecodeError as exc:
        raise LLMError(f"{label} was not JSON") from exc
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        raise LLMError(f"{label} was not JSON") from exc


def _strip_think(raw: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE)
    think = re.search(r"<think>", text, flags=re.IGNORECASE)
    if think:
        brace = text.find("{", think.end())
        text = text[: think.start()] + (text[brace:] if brace != -1 else "")
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    return text


def _json_object(text: str, label: str) -> str:
    """One object. A local model sometimes stops before the closing brace."""
    start = text.find("{")
    if start == -1:
        raise LLMError(f"{label} was not JSON")
    try:
        _obj, end = json.JSONDecoder().raw_decode(text, start)
        return text[start:end]
    except json.JSONDecodeError:
        pass
    end = text.rfind("}")
    fragment = text[start : end + 1] if end > start else text[start:]
    fragment = re.sub(r",\s*([}\]])", r"\1", fragment).rstrip()
    if fragment.count('"') % 2 == 1:
        fragment += '"'
    if not fragment.endswith("}"):
        fragment = fragment.rstrip().rstrip(",") + "}"
    return fragment
