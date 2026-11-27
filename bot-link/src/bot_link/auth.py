"""Attach tokens. A missing, empty, or short value never reaches the digest compare."""

import hmac

MIN_TOKEN_CHARS = 32


def tokens_match(presented: object, expected: object) -> bool:
    """True when both sides are long strings and the digest matches.

    Returns before hmac.compare_digest when either side is missing, empty,
    or shorter than 32 characters.
    """
    if not _ready(presented) or not _ready(expected):
        return False
    return hmac.compare_digest(presented, expected)  # type: ignore[arg-type]


def _ready(value: object) -> bool:
    return isinstance(value, str) and len(value) >= MIN_TOKEN_CHARS
