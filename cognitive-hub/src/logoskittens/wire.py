"""Convert the hub mirror to and from cerm.execution.v1.ElementSolution."""

from cerm.execution.v1 import element_solution_pb2 as pb

from logoskittens.primitives import (
    AudioPayloadModel,
    ElementSolutionModel,
    KinematicGestureModel,
    ScreenVisualCueModel,
    Vector3Model,
)

# Signed 16-bit little-endian mono. Piper output is resampled to this rate
# before it is stored on AudioPayload.precomputed_audio_pcm.
PCM_SAMPLE_RATE = 22050
PCM_SAMPLE_WIDTH = 2
PCM_CHANNELS = 1


def emotion_name(value: int) -> str:
    return pb.EmotionType.Name(value)


def to_proto(model: ElementSolutionModel) -> pb.ElementSolution:
    message = pb.ElementSolution(
        solution_id=model.solution_id,
        actor_id=model.actor_id,
        emotion=pb.EmotionType.Value(model.emotion),
        speech=pb.AudioPayload(
            text=model.speech.text,
            language_code=model.speech.language_code,
            voice_model_id=model.speech.voice_model_id,
            precomputed_audio_pcm=model.speech.precomputed_audio_pcm,
        ),
        screen_visuals=pb.ScreenVisualCue(
            animation_id=model.screen_visuals.animation_id,
            focus_target_id=model.screen_visuals.focus_target_id,
            highlight_elements=model.screen_visuals.highlight_elements,
        ),
    )
    for gesture in model.physical_gestures:
        message.physical_gestures.add(
            primitive_name=gesture.primitive_name,
            target_vector=pb.Vector3(
                x=gesture.target_vector.x,
                y=gesture.target_vector.y,
                z=gesture.target_vector.z,
            ),
            duration_ms=gesture.duration_ms,
        )
    return message


def from_proto(message: pb.ElementSolution) -> ElementSolutionModel:
    return ElementSolutionModel(
        solution_id=message.solution_id,
        actor_id=message.actor_id,
        emotion=pb.EmotionType.Name(message.emotion),
        speech=AudioPayloadModel(
            text=message.speech.text,
            language_code=message.speech.language_code,
            voice_model_id=message.speech.voice_model_id,
            precomputed_audio_pcm=message.speech.precomputed_audio_pcm,
        ),
        physical_gestures=[
            KinematicGestureModel(
                primitive_name=gesture.primitive_name,
                target_vector=Vector3Model(
                    x=gesture.target_vector.x,
                    y=gesture.target_vector.y,
                    z=gesture.target_vector.z,
                ),
                duration_ms=gesture.duration_ms,
            )
            for gesture in message.physical_gestures
        ],
        screen_visuals=ScreenVisualCueModel(
            animation_id=message.screen_visuals.animation_id,
            focus_target_id=message.screen_visuals.focus_target_id,
            highlight_elements=list(message.screen_visuals.highlight_elements),
        ),
    )


def encode(model: ElementSolutionModel) -> bytes:
    return to_proto(model).SerializeToString()


def decode(payload: bytes) -> ElementSolutionModel:
    message = pb.ElementSolution()
    message.ParseFromString(payload)
    return from_proto(message)
