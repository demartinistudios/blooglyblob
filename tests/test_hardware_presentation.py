"""LED state cannot change microphone or servo-facing presentation."""

from blooglyblob.hardware.conversation_state import ConversationMode, ConversationState
from blooglyblob.hardware.lighting import LightingState, render


def test_lighting_does_not_repurpose_servo_state():
    servo = ConversationState()
    servo.mode = ConversationMode.LISTENING
    servo.audio_level = 0.8
    lights = LightingState()
    for mode in ("listening", "waiting", "goodbye", "dancing", "alert"):
        lights.set_mode(mode, now=0)
        render(lights.snapshot(2), 2)
        assert servo.mode == ConversationMode.LISTENING
        assert servo.audio_level == 0.8


def test_dance_body_and_eyes_are_independent_of_music_energy():
    from dataclasses import replace
    from blooglyblob.audio.presentation import OutputSample

    lights = LightingState()
    lights.set_mode("dancing", now=0)
    state = replace(lights.snapshot(2), output=OutputSample("music", 0, 1))
    quiet = render(replace(state, music=(0.1,) * 8), 2)
    loud = render(replace(state, music=(0.9,) * 8), 2)
    assert quiet[:8] == loud[:8]
    assert quiet[8:] != loud[8:]
    assert len(set(loud[8:])) == 8
