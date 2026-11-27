"""Deterministic stand-ins for the LLM and the audio engine."""

import json

from logoskittens.llm import ComparisonRecord

_RECORD = ComparisonRecord(
    backend="fake",
    model="fake",
    latency_ms=0,
    prompt_tokens=1,
    completion_tokens=1,
)

SUBJECT = {
    "used_words": ["tunnels", "fjords", "vacation", "Norway", "ferries"],
    "significant_words": ["tunnels", "fjords"],
    "important_words": ["ferries", "slopes", "goats"],
    "theme": "A vacation on the west coast of Norway, through tunnels and above fjords.",
    "small_talk_subjects": [
        "What was the longest tunnel like?",
        "Did the fjord look dark or bright?",
        "Would you take that road again?",
        "What did the ferries look like from above?",
    ],
}


def fake_complete(user: str, *, system: str, **kwargs) -> tuple[str, ComparisonRecord]:
    del kwargs
    if "RAW MATERIAL:" in user or system.startswith("You read raw material"):
        return json.dumps(SUBJECT), _RECORD
    if "You are the human" in system:
        return json.dumps({"line": "The tunnels were long."}), _RECORD
    return (
        json.dumps(
            {
                "line": "The light at the end of the tunnel opened onto a quiet fjord.",
                "emotion": "curiosity",
            }
        ),
        _RECORD,
    )


class FakeAudio:
    def transcribe(
        self,
        audio: bytes,
        content_type: str = "application/octet-stream",
        language: str = "en",
        prompt: str = "",
    ) -> str:
        del content_type, language, prompt
        if not audio or audio == b"silence":
            return ""
        return "The fjords were beautiful."

    def synthesize(self, text: str, language_code: str, voice_id: str) -> bytes:
        del text, language_code, voice_id
        return b"\x00\x01" * 220
