"""Ambient movements must share gesture ownership and current positions."""

import threading
import pytest
import time

from blooglyblob.audio.presentation import OutputPresentation
from types import SimpleNamespace

from blooglyblob.hardware.ambient_animator import AmbientAnimator
from blooglyblob.hardware.conversation_state import ConversationState, ConversationMode
from blooglyblob.hardware.servo_config import HEAD, LEFT_ARM, RIGHT_ARM


def animator_fixture():
    servos = SimpleNamespace(
        **{
            name: SimpleNamespace(position=profile.rest, profile=profile)
            for name, profile in (
                ("head", HEAD),
                ("left_arm", LEFT_ARM),
                ("right_arm", RIGHT_ARM),
            )
        }
    )
    state = ConversationState()
    state.mode = ConversationMode.SPEAKING
    output = OutputPresentation()
    owner = output.begin("speech")
    now = time.monotonic()
    output.commit(owner, start=now, end=now + 1, position=0, level=0.8)
    lock = threading.Lock()
    animator = AmbientAnimator(servos, state, lock, output)
    animator._sync_from_servos()
    animator._head_target = 0.5
    animator._speech_owner = owner
    animator._update_speaking = lambda: None
    return animator, servos, lock


def test_ambient_updates_only_while_owning_gesture_lock(monkeypatch):
    animator, servos, lock = animator_fixture()
    observed = []
    apply = animator._apply_head_movement

    def record():
        observed.append(lock.locked())
        apply()

    animator._apply_head_movement = record
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.time.sleep",
        lambda _: setattr(animator, "_running", False),
    )
    animator._running = True
    animator._animation_loop()
    assert observed == [True]
    assert servos.head.position > 0
    assert not lock.locked()


def test_gesture_completed_between_frames_does_not_snap_back(monkeypatch):
    animator, servos, lock = animator_fixture()
    frames = []

    def between_frames(_):
        frames.append(servos.head.position)
        if len(frames) == 1:
            with lock:
                servos.head.position = -0.6
        else:
            animator._running = False

    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.time.sleep", between_frames
    )
    animator._running = True
    animator._animation_loop()
    assert frames[0] > 0
    assert frames[1] == -0.6


def test_busy_gesture_skips_ambient_frame_without_waiting(monkeypatch):
    animator, servos, lock = animator_fixture()
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.time.sleep",
        lambda _: setattr(animator, "_running", False),
    )
    animator._running = True
    with lock:
        animator._animation_loop()
        assert servos.head.position == HEAD.rest
        assert lock.locked()


def test_failed_ambient_update_releases_gesture_lock(monkeypatch):
    import pytest

    animator, _, lock = animator_fixture()

    def fail():
        raise ValueError("test failure")

    animator._update = fail
    animator._running = True
    with pytest.raises(ValueError):
        animator._animation_loop()
    assert not lock.locked()


def test_head_command_trace_records_targets_without_logging_arms(monkeypatch, caplog):
    from blooglyblob.hardware import servo_controller as module
    from blooglyblob.hardware.config import gpio_config

    monkeypatch.setattr(
        module, "_create_servo", lambda pin: SimpleNamespace(value=None)
    )
    head = module.BaseServo(gpio_config.HEAD_PIN, HEAD, "Head")
    arm = module.BaseServo(gpio_config.LEFT_ARM_PIN, LEFT_ARM, "Left")
    caplog.set_level("INFO", logger=module.__name__)
    head.position = 0.2
    head.position = 0.2
    arm.position = 0.2
    records = [r.message for r in caplog.records]
    assert len(records) == 1
    assert "Head command" in records[0] and "target=0.2000" in records[0]
    assert "source=MainThread" in records[0]
    caplog.clear()
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    head.move_to(-0.2)
    assert head.position == -0.2
    assert len(caplog.records) == 2
    assert "phase=start" in caplog.records[0].message
    assert "phase=complete" in caplog.records[1].message


async def test_buffered_speech_moves_after_software_queue_is_empty(monkeypatch):
    import asyncio
    from blooglyblob.audio.controller import AudioController
    from blooglyblob.audio.presentation import OutputTimeline
    from tests.support.audio import Driver

    driver = Driver()
    driver.out_stream.get_output_latency = lambda: 0.5
    monkeypatch.setattr(
        "blooglyblob.audio.playback.OutputTimeline",
        lambda *args: OutputTimeline(*args, clock=lambda: 1.0),
    )
    audio = AudioController(driver_factory=lambda: driver)
    animator, servos, _ = animator_fixture()
    animator._output = audio.presentation
    del animator._update_speaking
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.random", lambda: 0
    )
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.uniform", lambda a, b: b
    )
    try:
        await audio.begin(1)
        idle = threading.Event()
        wait = audio._writer._condition.wait

        def queue_wait(timeout):
            if driver.out_stream.frames:
                idle.set()
            return wait(timeout)

        monkeypatch.setattr(audio._writer._condition, "wait", queue_wait)
        await audio.audio(1, b"\xa0\x0f" * 2400)
        for _ in range(200):
            if idle.is_set():
                break
            await asyncio.sleep(0.005)
        assert idle.is_set(), "writer did not return to its empty-queue wait"
        assert not audio._writer._commands
        now = 1.51
        assert audio.presentation.sample(now).level >= 0.1
        monkeypatch.setattr(
            "blooglyblob.hardware.ambient_animator.time",
            SimpleNamespace(monotonic=lambda: now, time=lambda: now),
        )
        animator._update()
        assert servos.head.position > 0
    finally:
        await audio.close()


def envelope_fixture(monkeypatch):
    clock = [10.0]
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.time",
        SimpleNamespace(monotonic=lambda: clock[0], time=lambda: clock[0]),
    )
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.random", lambda: 0
    )
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.uniform", lambda a, b: b
    )
    animator, servos, lock = animator_fixture()
    # Use real selection, unlike the lock-only fixture.
    del animator._update_speaking
    output = animator._output = OutputPresentation()
    owner = output.begin("speech")

    def frame(at, level=0):
        clock[0] = at
        output.commit(owner, start=at, end=at + 0.04, position=0, level=level)
        animator._update()
        return servos.head.position

    return animator, servos, clock, frame


def test_quiet_speech_and_short_pause_continue_without_reselection(monkeypatch):
    animator, servos, _, frame = envelope_fixture(monkeypatch)
    assert frame(10, 0) == 0
    first = frame(10.05, 0.05)
    assert first > 0
    targets = (
        animator._head_target,
        dict(animator._arm_gestures),
    )

    def unexpected():
        raise AssertionError("quiet gap selected a new gesture")

    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.random", unexpected
    )
    assert frame(10.15) > first
    assert targets == (
        animator._head_target,
        dict(animator._arm_gestures),
    )


def test_long_pause_relaxes_once_and_new_speech_resumes_from_current_pose(monkeypatch):
    animator, servos, _, frame = envelope_fixture(monkeypatch)
    for i in range(8):
        frame(10 + i * 0.05, 0.8)
    frame(10.5)
    start = frame(10.61)
    middle = frame(10.91)
    assert 0 < middle < start
    resumed = frame(10.96, 0.8)
    assert middle < resumed < start
    frame(11.22)
    assert frame(11.83) == 0
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(15)
    assert RIGHT_ARM.percent_at(servos.right_arm.position) == pytest.approx(15)

    # No repeated movement after completion, even across a missed frame.
    def unexpected_write(*args, **kwargs):
        raise AssertionError("restarted")

    animator._write_positions = unexpected_write
    assert frame(20) == 0


def test_hold_expiring_in_silence_never_resumes_pending_motion(monkeypatch):
    animator, servos, clock, frame = envelope_fixture(monkeypatch)
    frame(10, 0.8)
    animator.hold_all(0.1)
    held = frame(10.05, 0.8)
    for at in (10.15, 10.31, 10.6, 11.0):
        assert frame(at) == held
    assert frame(11.05, 0.8) > held


@pytest.mark.parametrize("at", [10.1, 10.6])
@pytest.mark.parametrize(
    "cancel", ["mute", "retire", "replace", "disable", "idle", "dancing", "alert"]
)
def test_cancellation_discards_grace_and_relaxation(monkeypatch, at, cancel):
    animator, servos, clock, frame = envelope_fixture(monkeypatch)
    frame(10, 0.8)
    if at > 10.3:
        frame(10.3)
        frame(10.45)
    output = animator._output
    owner = output.sample(clock[0]).owner
    if cancel == "mute":
        output.mute()
    elif cancel == "retire":
        output.retire(owner)
    elif cancel == "replace":
        output.begin("speech")
    elif cancel == "disable":
        output.commit(owner, start=at, end=at + 3, position=0, level=1)
    else:
        animator._conversation_state.mode = ConversationMode(cancel)
    positions = animator._positions()
    for tick in (at, at + 0.5, at + 2):
        clock[0] = tick
        animator._update()
        assert animator._positions() == positions


@pytest.mark.parametrize("busy", [False, True])
def test_explicit_motion_discards_relaxation_even_between_frames(monkeypatch, busy):
    animator, servos, clock, frame = envelope_fixture(monkeypatch)
    frame(10, 0.8)
    frame(10.3)
    frame(10.45)
    animator._last_positions = animator._positions()

    def one_frame():
        animator._running = True
        animator._animation_loop()

    def stop(_):
        animator._running = False

    from blooglyblob.hardware import ambient_animator as module

    module.time.sleep = stop
    clock[0] = 10.5
    if busy:
        with animator._animation_lock:
            one_frame()
    servos.head.position = -0.6
    servos.left_arm.position = LEFT_ARM.at_percent(70)
    servos.right_arm.position = RIGHT_ARM.at_percent(70)
    commanded = animator._positions()
    one_frame()
    clock[0] = 12
    one_frame()
    assert animator._positions() == commanded


@pytest.mark.parametrize("held", ["head", "arms", "all"])
def test_holds_preserve_each_axis_after_expiry_in_silence(monkeypatch, held):
    animator, servos, clock, frame = envelope_fixture(monkeypatch)
    frame(10, 0.8)
    getattr(animator, f"hold_{held}")(0.1)
    frame(10.05, 0.8)
    positions = animator._positions()
    for at in (10.15, 10.31, 10.6, 11.0):
        frame(at)
        current = animator._positions()
        if held in ("head", "all"):
            assert current[0] == positions[0]
        if held in ("arms", "all"):
            assert current[1:] == positions[1:]


def test_policy_and_holds_do_not_read_wall_clock(monkeypatch):
    animator, _, clock, frame = envelope_fixture(monkeypatch)

    def wall_clock():
        raise AssertionError("wall clock used for movement deadline")

    from blooglyblob.hardware import ambient_animator as module

    module.time.time = wall_clock
    animator.hold_all(0.1)
    assert frame(10.05, 0.8) == 0
    assert frame(10.15, 0.8) > 0
    frame(10.41)
    assert frame(11.02) == 0


def test_missed_settling_window_discards_stale_motion(monkeypatch):
    animator, _, _, frame = envelope_fixture(monkeypatch)
    pose = frame(10, 0.8)
    assert frame(12) == pose
    assert frame(12.3) == pose
    assert frame(13) == pose
    assert frame(13.05, 0.8) > pose


def test_late_settling_frame_keeps_original_deadline(monkeypatch):
    _, _, _, frame = envelope_fixture(monkeypatch)
    frame(10, 0.8)
    frame(10.4)
    assert frame(10.86) == 0


def test_arm_finishes_rising_through_pause_then_returns_independently(monkeypatch):
    animator, servos, _, frame = envelope_fixture(monkeypatch)
    choices = iter((0, 1, 1))  # left starts, right/head do not
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.random", lambda: next(choices, 1)
    )
    frame(10, 0.8)
    frame(10.2)
    low = LEFT_ARM.percent_at(servos.left_arm.position)
    frame(10.5)
    peak = LEFT_ARM.percent_at(servos.left_arm.position)
    assert peak == pytest.approx(50)
    assert peak > low > 0
    assert RIGHT_ARM.percent_at(servos.right_arm.position) == 0
    frame(10.9)
    assert 15 < LEFT_ARM.percent_at(servos.left_arm.position) < peak
    frame(11.31)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(15)
    positions = animator._positions()
    frame(15)
    assert animator._positions() == positions


def test_staggered_arms_can_move_in_opposite_directions(monkeypatch):
    animator, servos, _, frame = envelope_fixture(monkeypatch)
    # Selection order is left, right, head; active arms cannot be reselected.
    choices = iter((0, 1, 1, 0, 1))
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.random", lambda: next(choices, 1)
    )
    frame(10, 0.8)
    frame(10.4, 0.8)
    frame(10.6)
    left = LEFT_ARM.percent_at(servos.left_arm.position)
    right = RIGHT_ARM.percent_at(servos.right_arm.position)
    frame(10.8)
    assert LEFT_ARM.percent_at(servos.left_arm.position) < left
    assert RIGHT_ARM.percent_at(servos.right_arm.position) > right


def test_continuing_speech_does_not_retarget_an_active_arm_gesture(monkeypatch):
    animator, servos, _, frame = envelope_fixture(monkeypatch)
    for i in range(11):
        frame(10 + i * 0.05, 0.8)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(50)
    assert RIGHT_ARM.percent_at(servos.right_arm.position) == pytest.approx(50)
    for i in range(11, 27):
        frame(10 + i * 0.05, 0.8)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(15)
    assert RIGHT_ARM.percent_at(servos.right_arm.position) == pytest.approx(15)


def test_head_hold_leaves_independent_arm_gestures_available(monkeypatch):
    animator, servos, _, frame = envelope_fixture(monkeypatch)
    servos.head.position = -0.6
    animator._sync_from_servos()
    animator.hold_head(5)
    frame(10, 0.8)
    frame(10.5)
    assert servos.head.position == -0.6
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(50)
    frame(10.6)
    frame(11.31)
    assert servos.head.position == -0.6
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(15)


def test_missed_head_window_preserves_unexpired_arm_gesture(monkeypatch):
    _, servos, _, frame = envelope_fixture(monkeypatch)
    frame(10, 0.8)
    frame(10.2)
    head = servos.head.position
    early_arm = LEFT_ARM.percent_at(servos.left_arm.position)
    frame(10.9)  # Missed the head window, but the arm still has 400ms left.
    assert servos.head.position == head
    assert LEFT_ARM.percent_at(servos.left_arm.position) > early_arm
    frame(11.31)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(15)


def test_missing_both_windows_discards_expired_arm_motion(monkeypatch):
    animator, _, _, frame = envelope_fixture(monkeypatch)
    frame(10, 0.8)
    frame(10.2)
    pose = animator._positions()
    frame(12)
    frame(13)
    assert animator._positions() == pose
