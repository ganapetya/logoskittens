"""One spoken turn, two faces.

Synthesis has already finished. Web keeps the PCM on the page. Botnet sends
that PCM to the role's body. The wait for a voice that is already playing
starts here, after the audio exists.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from logoskittens.primitives import ElementSolutionModel
from logoskittens.wire import encode

import base64
import sys


@dataclass
class SpokenTurn:
    session_id: str
    role: str
    voiced: ElementSolutionModel
    language_id: str
    tokens: list[str] = field(default_factory=list)
    altered: bool = False
    steer: str = ""
    speaker: str = ""


def deliver_spoken(
    turn: SpokenTurn,
    *,
    emit: Callable[[dict], None],
    deliver_pcm: Callable[..., None] | None,
    botnet: Callable[[], bool] | None,
) -> None:
    """Hand one finished line to the page or to that role's body."""
    to_robot = deliver_pcm is not None and (botnet is None or botnet())
    pcm = turn.voiced.speech.precomputed_audio_pcm
    page_view = turn.voiced
    if to_robot:
        page_view = turn.voiced.model_copy(
            update={"speech": turn.voiced.speech.model_copy(update={"precomputed_audio_pcm": b""})}
        )
        try:
            deliver_pcm(pcm, list(turn.tokens), language=turn.language_id, role=turn.role)
        except TypeError:
            try:
                deliver_pcm(pcm, list(turn.tokens), language=turn.language_id)
            except TypeError:
                deliver_pcm(pcm, list(turn.tokens))
        except Exception as exc:
            print(f"player delivery failed: {exc}", file=sys.stderr, flush=True)
    message = {
        "type": "actor",
        "session_id": turn.session_id,
        "final": True,
        "altered": turn.altered,
        "steer": turn.steer,
        "play_on_page": botnet is not None and not to_robot,
        "solutions": [base64.b64encode(encode(page_view)).decode("ascii")],
    }
    if turn.speaker:
        message["speaker"] = turn.speaker
    emit(message)
