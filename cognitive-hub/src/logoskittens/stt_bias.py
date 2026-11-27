"""Words Mary expects to hear, sent to whisper as a bias on each hearing."""

import re

from logoskittens.games.host import contains_phrase
from logoskittens.talk import split_sentences

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_LIMIT = 80


def bias_words(*texts: str, limit: int = _LIMIT) -> list[str]:
    """Unique words, first-seen order, at least three letters. Digits and punctuation drop out."""
    seen: set[str] = set()
    words: list[str] = []
    for text in texts:
        for token in _WORD.findall(text or ""):
            key = token.casefold()
            if len(key) < 3 or key in seen:
                continue
            seen.add(key)
            words.append(token)
            if len(words) >= limit:
                return words
    return words


def bias_prompt(*texts: str) -> str:
    return ", ".join(bias_words(*texts))


def expected_hearing(phrase: str, passage: str) -> str:
    """The passage sentence Mary is waiting for, as a sentence. Not a comma list, and not her question."""
    if not (phrase or "").strip():
        return ""
    for part in split_sentences(passage or ""):
        if contains_phrase(part, phrase):
            return part.strip()
    return phrase.strip()
