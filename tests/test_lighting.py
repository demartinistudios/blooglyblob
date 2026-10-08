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


def blink_state(*, double=False):
    from unittest.mock import Mock

    rng = Mock()
    rng.uniform.side_effect = lambda low, high: 4.0 if low == 3.4 else 0.25
    rng.random.return_value = 0.05 if double else 0.5
    state = LightingState(rng=rng)
    state.set_mode("listening", now=0)
    return state


def test_eyes_close_together_and_reopen_softly_without_changing_other_zones():
    from dataclasses import replace

    state = blink_state()
    assert state.snapshot(0).eye_openness == 1
    state.snapshot(4)
    samples = [(t, state.snapshot(t)) for t in (4.025, 4.065, 4.16, 4.25)]
    close, shut, opening, open_ = [s.eye_openness for _, s in samples]
    assert 0 < close < 1
    assert shut == 0
    assert 0 < opening < 1
    assert open_ == 1
    for now, snapshot in samples:
        frame = render(snapshot, now)
        steady = render(replace(snapshot, eye_openness=1), now)
        assert frame[6] == frame[7]
        assert frame[:6] == steady[:6]
        assert frame[8:] == steady[8:]
    assert render(samples[1][1], samples[1][0])[6:8] == ((0, 0, 0),) * 2


def test_occasional_double_blink_has_an_open_gap_then_returns_to_rest():
    state = blink_state(double=True)
    state.snapshot(0)
    state.snapshot(4)
    assert state.snapshot(4.065).eye_openness == 0
    assert state.snapshot(4.30).eye_openness == 1
    assert state.snapshot(4.445).eye_openness == 0
    assert state.snapshot(4.61).eye_openness == 1
    assert state.snapshot(5).eye_openness == 1


def test_waiting_and_dance_do_not_restart_the_blink_schedule():
    state = blink_state()
    state.snapshot(0)
    state.pending("search", True)
    assert state.snapshot(2).mode == "waiting"
    state.set_mode("dancing", now=3)
    state.snapshot(4)
    assert state.snapshot(4.065).eye_openness == 0


def test_sleep_cancels_pending_double_blink_and_wake_starts_fresh():
    state = blink_state(double=True)
    state.snapshot(0)
    state.snapshot(4)
    state.set_mode("sleeping", now=4.1)
    assert render(state.snapshot(4.445), 4.445)[6:] == ((0, 0, 0),) * 10
    state.set_mode("waking", now=5)
    assert state.snapshot(5.3).eye_openness == 1
    assert state.snapshot(5.7).eye_openness == 1
    assert state.snapshot(6).eye_openness == 1
    state.stop()
    assert render(state.snapshot(100), 100) == ((0, 0, 0),) * 16


def test_alert_and_fault_keep_steady_eyes_even_during_a_blink():
    for mode in ("alert", "fault"):
        state = blink_state(double=True)
        state.snapshot(0)
        state.snapshot(4)
        state.set_mode(mode, now=4.01)
        assert state.snapshot(4.065).eye_openness == 1
        assert state.snapshot(4.445).eye_openness == 1


def test_blink_intervals_vary_and_stalled_frames_do_not_catch_up_in_a_burst():
    from random import Random

    state = LightingState(rng=Random(7))
    state.set_mode("listening", now=0)
    # A seeded minute exercises real interval/double-blink draws deterministically.
    starts = []
    previous = 1
    for tick in range(1800):
        now = tick / 30
        openness = state.snapshot(now).eye_openness
        assert 0 <= openness <= 1
        if previous == 1 and openness < 1:
            starts.append(now)
        previous = openness
    intervals = [b - a for a, b in zip(starts, starts[1:])]
    normal = [x for x in intervals if x > 1]
    assert len(normal) >= 5
    assert all(3.3 <= x <= 8.7 for x in normal)
    assert len({round(x, 1) for x in normal}) > 2
    state.snapshot(600)
    assert state.snapshot(601).eye_openness == 1


def test_body_does_not_follow_speech_level_or_pauses():
    from dataclasses import replace
    from blooglyblob.audio.presentation import OutputSample

    for mode in ("listening", "waiting", "speaking", "goodbye", "dancing"):
        state = LightingState()
        state.set_mode(mode, now=0)
        snapshot = state.snapshot(5)
        quiet = render(snapshot, 5)[:6]
        for level in (0, 0.024, 0.026, 0.4, 1):
            speaking = replace(
                snapshot, output=OutputSample(kind="speech", level=level)
            )
            assert render(speaking, 5)[:6] == quiet


def test_unavailable_is_amber_and_overrides_late_speech_and_sleep():
    output = OutputPresentation()
    state = LightingState(output)
    owner = output.begin("speech")
    output.commit(owner, start=0.95, end=1.1, position=0, level=1)
    state.set_unavailable(True)
    for mode in ("speaking", "sleeping", "alert", "dancing"):
        state.set_mode(mode, now=0)
        state.pending("late", True)
        frame = render(state.snapshot(1), 1)
        assert all(red > green > 0 and blue == 0 for red, green, blue in frame[:6])
        assert frame[6:] == ((0, 0, 0),) * 10
    state.set_unavailable(False)
    assert state.snapshot(2).mode == "sleeping"
    state.set_unavailable(True)
    state.set_mode("fault")
    assert state.snapshot(3).mode == "fault"
    state.stop()
    assert render(state.snapshot(4), 4) == ((0, 0, 0),) * 16


def test_eye_wake_ramp_survives_fast_connection_and_stops_when_unavailable():
    state = LightingState()
    state.set_mode("waking", now=10)
    assert render(state.snapshot(10), 10)[6:8] == ((0, 0, 0),) * 2
    early = render(state.snapshot(10.1), 10.1)[6]
    state.set_mode("listening", now=10.1)
    assert render(state.snapshot(10.1), 10.1)[6] == early
    middle = render(state.snapshot(10.3), 10.3)[6]
    full = render(state.snapshot(10.6), 10.6)[6]
    assert 0 < early[0] < middle[0] < full[0]
    state.set_unavailable(True)
    assert render(state.snapshot(10.7), 10.7)[6:] == ((0, 0, 0),) * 10
    state.set_unavailable(False)
    assert render(state.snapshot(10.8), 10.8)[6:] == ((0, 0, 0),) * 10
    state.set_mode("waking", now=11)
    assert render(state.snapshot(11), 11)[6:8] == ((0, 0, 0),) * 2


def test_sleep_is_purple_and_waking_starts_a_continuous_rainbow_transition():
    from dataclasses import replace

    state = LightingState()
    for now in (1, 15, 40, 90):
        body = render(state.snapshot(now), now)[:6]
        assert all(blue > red > green for red, green, blue in body)
    state.set_mode("waking", now=10)
    early = render(state.snapshot(10.1), 10.1)
    sleeping = render(
        replace(state.snapshot(10.1), mode="sleeping", previous="sleeping"), 10.1
    )
    assert early[:6] != sleeping[:6]
    state.set_mode("listening", now=10.1)
    assert render(state.snapshot(10.1), 10.1)[:8] == early[:8]
    awake = render(state.snapshot(11), 11)
    assert len(set(awake[:6])) == 6
    red, green, blue = awake[6]
    assert red > green > blue and green > blue * 2
    assert render(state.snapshot(26), 26)[:6] != awake[:6]


def test_lava_body_flows_slowly_without_blackouts_or_losing_state_colors():
    for mode, ceiling in (("sleeping", 123), ("listening", 64), ("unavailable", 49)):
        state = LightingState()
        if mode == "unavailable":
            state.set_unavailable(True)
        else:
            state.set_mode(mode, now=0)
        frames = [
            render(state.snapshot(10 + tick / 30), 10 + tick / 30)[:6]
            for tick in range(1800)
        ]
        assert len(set(frames[0])) > 2  # Distinct pools rather than a uniform pulse.
        assert frames[0] != frames[300] != frames[900]
        for frame in frames:
            assert all(ceiling * 0.70 <= max(rgb) <= ceiling for rgb in frame)
            if mode == "sleeping":
                assert all(blue > red > green for red, green, blue in frame)
            if mode == "unavailable":
                assert all(red > green > 0 and blue == 0 for red, green, blue in frame)
        for before, after in zip(frames, frames[1:]):
            assert (
                max(
                    abs(a - b)
                    for old, new in zip(before, after)
                    for a, b in zip(old, new)
                )
                <= 3
            )


def test_speech_spectrum_is_saturated_and_drifts_without_changing_meter_shape():
    from dataclasses import replace
    from blooglyblob.audio.presentation import OutputSample

    state = LightingState()
    state.set_mode("speaking", now=0)
    snapshot = replace(state.snapshot(2), output=OutputSample(kind="speech", level=1))
    first, later = (render(snapshot, now)[8:] for now in (2, 6))
    assert first != later
    for mouth in (first, later):
        assert mouth == mouth[::-1]
        assert len(set(mouth)) == 4
        assert all(min(rgb) < max(rgb) * 0.2 for rgb in mouth)
        assert all(max(rgb) <= 192 for rgb in mouth)
    quiet = replace(snapshot, output=OutputSample(kind="speech", level=0))
    assert render(quiet, 6)[8:] == ((0, 0, 0),) * 8
