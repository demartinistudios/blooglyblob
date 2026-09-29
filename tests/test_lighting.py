"""Lighting outcomes, independent of devices and the microphone."""

from blooglyblob.hardware.lighting import LightingState, render
from blooglyblob.audio.presentation import OutputPresentation


def test_all_modes_cover_chain_and_sleep_stop_are_dark_faced():
    state = LightingState()
    for mode in (
        "sleeping",
        "listening",
        "waiting",
        "speaking",
        "dancing",
        "alert",
        "waking",
        "goodbye",
        "fault",
        "stopped",
    ):
        state.set_mode(mode, now=0)
        frame = render(state.snapshot(5), 5)
        assert len(frame) == 16
        assert all(0 <= channel <= 255 for rgb in frame for channel in rgb)
        if mode in ("sleeping", "stopped"):
            assert frame[6:] == ((0, 0, 0),) * 10
        if mode == "stopped":
            assert frame == ((0, 0, 0),) * 16


def test_speech_is_output_driven_symmetric_and_silent_between_intervals():
    output = OutputPresentation()
    state = LightingState(output)
    state.set_mode("listening", now=0)
    owner = output.begin("speech")
    output.commit(owner, start=1, end=1.1, position=0, level=0.8)
    mouth = render(state.snapshot(1.05), 1.05)[8:]
    assert any(rgb != (0, 0, 0) for rgb in mouth)
    assert mouth == mouth[::-1]
    assert render(state.snapshot(1.11), 1.11)[8:] == ((0, 0, 0),) * 8
    output.retire(owner)
    assert render(state.snapshot(1.05), 1.05)[8:] == ((0, 0, 0),) * 8


def test_waiting_has_identity_and_stop_cannot_be_reopened():
    state = LightingState()
    state.set_mode("listening", now=0)
    state.pending("old", True)
    state.pending("new", True)
    state.pending("old", False)
    assert state.snapshot(2).mode == "waiting"
    state.pending("new", False)
    assert state.snapshot(2).mode == "listening"
    state.stop()
    state.set_mode("dancing")
    assert render(state.snapshot(2), 2) == ((0, 0, 0),) * 16


def test_finishing_greeting_does_not_clear_pending_connection():
    state = LightingState()
    state.set_mode("listening", now=0)
    state.pending("connection", True)
    state.pending("greeting", True)
    state.pending("greeting", False)
    assert state.snapshot(2).mode == "waiting"
    state.pending("connection", False)
    assert state.snapshot(2).mode == "listening"
