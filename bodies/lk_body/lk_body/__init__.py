"""Shape of a LogosKittens body. Hardware stays on the machine.

A body dials the hub, registers the actions it can play, accepts PCM for its
role, and says when that sentence has finished. It does not choose the words.
"""

from lk_body.loop import BodyLoop

__all__ = ["BodyLoop"]
