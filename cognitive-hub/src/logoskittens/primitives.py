"""Cognitive primitives. ElementSolution on the wire stays protobuf."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VoiceProfile(BaseModel):
    engine: str = Field(min_length=1)
    voice_id: str = Field(min_length=1)


class Embodiment(BaseModel):
    medium: Literal["virtual_screen", "physical_robot"]
    voice_profile: VoiceProfile
    supported_primitives: list[str] = Field(min_length=1)


class Traits(BaseModel):
    patience: float = Field(ge=0, le=1)
    expressiveness: float = Field(ge=0, le=1)
    assertiveness: float = Field(ge=0, le=1)
    gender: Literal["male", "female"] = "male"


class LinguisticStyle(BaseModel):
    vocabulary_complexity: str = Field(min_length=1)
    correction_strictness: str = Field(min_length=1)


class Personality(BaseModel):
    archetype: str = Field(min_length=1)
    traits: Traits
    linguistic_style: LinguisticStyle
    emotional_baseline: str = Field(min_length=1)


class Actor(BaseModel):
    actor_id: str = Field(min_length=1)
    embodiment: Embodiment
    role: str = Field(min_length=1)
    personality: Personality
    active: bool = True


class Situation(BaseModel):
    situation_id: str
    medium: str
    description: str
    participant_ids: list[str]
    bounds: str


class Task(BaseModel):
    task_id: str
    objective: str
    language_code: str
    success_hint: str


class TurnSlot(BaseModel):
    actor_id: str
    purpose: Literal["correct", "practice", "talk"]


class GroupSolution(BaseModel):
    solution_id: str
    task_id: str
    protocol: str
    turn_order: list[TurnSlot]


class Vector3Model(BaseModel):
    x: float = 0
    y: float = 0
    z: float = 0


class AudioPayloadModel(BaseModel):
    text: str
    language_code: str
    voice_model_id: str
    precomputed_audio_pcm: bytes = b""


class KinematicGestureModel(BaseModel):
    primitive_name: str
    target_vector: Vector3Model = Field(default_factory=Vector3Model)
    duration_ms: float


class ScreenVisualCueModel(BaseModel):
    animation_id: str = ""
    focus_target_id: str = ""
    highlight_elements: list[str] = Field(default_factory=list)


class ElementSolutionModel(BaseModel):
    """Hub-boundary mirror of cerm.execution.v1.ElementSolution. Field names match the proto."""

    solution_id: str
    actor_id: str
    emotion: str
    speech: AudioPayloadModel
    physical_gestures: list[KinematicGestureModel] = Field(default_factory=list)
    screen_visuals: ScreenVisualCueModel = Field(default_factory=ScreenVisualCueModel)


class TurnAssessment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    form_ok: bool
    speech_register: Literal["formal", "informal", "neutral"] = Field(alias="register")
    pronunciation_note: str = ""
    corrected_form: str
    error_tags: list[str] = Field(default_factory=list)
    new_words: list[str] = Field(default_factory=list)
    coaching_point: str = ""
    spoken_line: str = Field(default="", alias="line")


DESKTOP_SITUATION = Situation(
    situation_id="desktop_edge_free_speech",
    medium="virtual_screen",
    description="Local runtime, one human via microphone, one active buddy. A second buddy is present and inactive. The same directives can drive a screen or a hexapod.",
    participant_ids=["human", "buddy-one", "buddy-two"],
    bounds="local_desktop",
)

FREE_SPEECH_TASK = Task(
    task_id="free_speech",
    objective="An open conversation grounded in one lesson subject. The talk does not end and the human is not corrected.",
    language_code="en",
    success_hint="The buddy stays with the theme and answers the human.",
)
