"""Dial, register, play, and report. No servos and no microphone."""

from collections.abc import Callable


class BodyLoop:
    """The messages every body sends. A subclass plays PCM and may move."""

    def __init__(self, body_id: str, *, speaking: str, stances: list[dict] | None = None):
        self.body_id = body_id
        self.speaking = speaking
        self.stances = list(stances or [])

    def attach(self, token: str) -> dict:
        return {"type": "attach", "body_id": self.body_id, "token": token}

    def register(self) -> dict:
        return {
            "type": "register",
            "speaking": {"action": self.speaking, "intent": "voice"},
            "stances": self.stances,
        }

    def on_delivery(
        self,
        message: dict,
        play: Callable[[bytes], None],
    ) -> dict | None:
        """Play this body's PCM, then tell the hub the sentence finished."""
        if message.get("type") != "delivery":
            return None
        import base64

        raw = message.get("pcm") or ""
        pcm = base64.b64decode(raw) if raw else b""
        if pcm:
            play(pcm)
        return {"type": "played"}
