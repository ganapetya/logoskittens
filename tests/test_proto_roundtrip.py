from cerm.execution.v1 import element_solution_pb2 as pb

from logoskittens.primitives import (
    AudioPayloadModel,
    ElementSolutionModel,
    KinematicGestureModel,
    ScreenVisualCueModel,
    Vector3Model,
)
from logoskittens.wire import decode, encode


def test_element_solution_round_trip():
    model = ElementSolutionModel(
        solution_id="sol-1",
        actor_id="actor_tutor_01",
        emotion="EMOTION_ENCOURAGEMENT",
        speech=AudioPayloadModel(
            text="Hei!",
            language_code="nb",
            voice_model_id="no_NO-talesyntese-medium",
            precomputed_audio_pcm=b"\x01\x02\x03\x04",
        ),
        physical_gestures=[
            KinematicGestureModel(
                primitive_name="nod",
                target_vector=Vector3Model(x=0.1, y=0.2, z=0.3),
                duration_ms=800,
            )
        ],
        screen_visuals=ScreenVisualCueModel(
            animation_id="nod",
            focus_target_id="user",
            highlight_elements=["correction"],
        ),
    )
    restored = decode(encode(model))
    assert restored == model


def test_mirror_fields_match_the_proto():
    assert list(ElementSolutionModel.model_fields) == [
        field.name for field in pb.ElementSolution.DESCRIPTOR.fields
    ]
    assert list(AudioPayloadModel.model_fields) == [
        field.name for field in pb.AudioPayload.DESCRIPTOR.fields
    ]
    assert list(KinematicGestureModel.model_fields) == [
        field.name for field in pb.KinematicGesture.DESCRIPTOR.fields
    ]
    assert list(ScreenVisualCueModel.model_fields) == [
        field.name for field in pb.ScreenVisualCue.DESCRIPTOR.fields
    ]
