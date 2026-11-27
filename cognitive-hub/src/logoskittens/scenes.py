"""Which graph a session runs.

``free_speech`` is the talk that ships. ``joint_hunting`` is reserved. It has
no graph, no downloads, and no page until a later project fills them.
"""


class SceneNotBuilt(ValueError):
    """The scene id is known and not implemented."""


FREE_SPEECH = "free_speech"
TALKING_GAME = "talking_game"
JOINT_HUNTING = "joint_hunting"
DETACHED = "detached"
ATTACHED = "attached"


def require_scene(scene_id: str) -> str:
    """The live scene, or an error before any model call."""
    scene = (scene_id or FREE_SPEECH).strip() or FREE_SPEECH
    if scene == JOINT_HUNTING:
        raise SceneNotBuilt("joint_hunting is not built")
    if scene in {FREE_SPEECH, TALKING_GAME}:
        return scene
    raise ValueError(f"Unknown scene {scene}")


def require_material_mode(mode: str) -> str:
    """Detached uses the files. Attached is the LogosCat slot and is not wired."""
    value = (mode or DETACHED).strip() or DETACHED
    if value == ATTACHED:
        raise ValueError("LogosCat download is not implemented")
    if value != DETACHED:
        raise ValueError(f"Unknown material mode {value}")
    return value
