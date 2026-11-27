"""Shared shape of a background expert. Each expert keeps its own clock.

The call runs after the spoken line is already handed to the face. A missing
prompt skips that expert. It does not fall back to another language, and it
does not delay the reply.
"""

from logoskittens.content import prompt_text


class ExpertSkipped(RuntimeError):
    """The expert did not run. The spoken line is unchanged."""


def expert_prompt(name: str, language_id: str) -> str:
    """The language file for this expert, or a skip that names the missing file."""
    try:
        return prompt_text(name, language_id)
    except FileNotFoundError as exc:
        raise ExpertSkipped(f"missing prompt {name}_{language_id}.md") from exc
