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
    animator._choose_head_target = lambda: None
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
    del animator._choose_head_target
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
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.choice", lambda _: "left"
    )
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.triangular",
        lambda low, high, mode: high,
    )
    animator, servos, lock = animator_fixture()
    # Use real selection, unlike the lock-only fixture.
    del animator._choose_head_target
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
        animator._arm_gesture,
    )

    def unexpected():
        raise AssertionError("quiet gap selected a new gesture")

    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.random", unexpected
    )
    assert frame(10.15) > first
    assert targets == (
        animator._head_target,
        animator._arm_gesture,
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
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(0)
    assert RIGHT_ARM.percent_at(servos.right_arm.position) == pytest.approx(0)

    # No repeated movement after completion, even across a missed frame.
    def unexpected_write(*args, **kwargs):
        raise AssertionError("restarted")

    animator._write_positions = unexpected_write
    assert frame(20) == 0


def test_hold_expiring_in_silence_never_resumes_pending_motion(monkeypatch):
    animator, servos, clock, frame = envelope_fixture(monkeypatch)
    for i in range(17):
        frame(10 + i * 0.05, 0.8)
    animator.hold_all(0.1)
    held = frame(10.85, 0.8)
    for at in (10.95, 11.11, 11.4, 11.8):
        assert frame(at) == held
    assert frame(11.85, 0.8) > held


@pytest.mark.parametrize("at", [10.9, 11.55, 11.65])
@pytest.mark.parametrize(
    "cancel", ["mute", "retire", "replace", "disable", "idle", "dancing", "alert"]
)
def test_cancellation_discards_grace_and_relaxation(monkeypatch, at, cancel):
    animator, servos, clock, frame = envelope_fixture(monkeypatch)
    for i in range(17):
        frame(10 + i * 0.05, 0.8)
    if at == 11.55:
        for i in range(17, 27):
            frame(10 + i * 0.05, 0.8)
        frame(11.45)  # Peak hold continues across this gap until cancellation.
    elif at > 11:
        frame(10.95)
        frame(11.1)
        frame(11.35)
    assert LEFT_ARM.percent_at(servos.left_arm.position) > 0
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
    for i in range(17):
        frame(10 + i * 0.05, 0.8)
    frame(11.1)
    animator._last_positions = animator._positions()

    def one_frame():
        animator._running = True
        animator._animation_loop()

    def stop(_):
        animator._running = False

    from blooglyblob.hardware import ambient_animator as module

    module.time.sleep = stop
    clock[0] = 11.2
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
    for i in range(17):
        frame(10 + i * 0.05, 0.8)
    getattr(animator, f"hold_{held}")(0.1)
    frame(10.85, 0.8)
    positions = animator._positions()
    for at in (10.95, 11.11, 11.4, 11.8):
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


def test_brief_gap_continues_but_long_pause_returns_from_current_pose(monkeypatch):
    animator, servos, _, frame = envelope_fixture(monkeypatch)
    for i in range(17):
        frame(10 + i * 0.05, 0.8)
    low = LEFT_ARM.percent_at(servos.left_arm.position)
    frame(10.95)
    raised = LEFT_ARM.percent_at(servos.left_arm.position)
    assert 0 < low < raised < 32
    frame(11.1)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == raised
    frame(11.4)
    assert 0 < LEFT_ARM.percent_at(servos.left_arm.position) < raised
    frame(11.71)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(0)
    assert RIGHT_ARM.percent_at(servos.right_arm.position) == 0
    pose = animator._positions()
    frame(20)
    assert animator._positions() == pose


def test_speech_resuming_does_not_restart_or_reverse_return(monkeypatch):
    _, servos, _, frame = envelope_fixture(monkeypatch)
    for i in range(17):
        frame(10 + i * 0.05, 0.8)
    frame(11.1)
    previous = LEFT_ARM.percent_at(servos.left_arm.position)
    for i in range(1, 14):
        frame(11.1 + i * 0.05, 0.8)
        position = LEFT_ARM.percent_at(servos.left_arm.position)
        assert position <= previous
        previous = position
    assert previous == pytest.approx(0)


def test_continuing_speech_completes_gesture_then_leaves_shared_rest(monkeypatch):
    _, servos, _, frame = envelope_fixture(monkeypatch)
    for i in range(27):
        frame(10 + i * 0.05, 0.8)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(32)
    assert RIGHT_ARM.percent_at(servos.right_arm.position) == 0
    for i in range(27, 55):
        frame(10 + i * 0.05, 0.8)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(0)
    for i in range(55, 109):
        frame(10 + i * 0.05, 0.8)
        assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(0)
        assert RIGHT_ARM.percent_at(servos.right_arm.position) == 0
    for i in range(109, 117):
        frame(10 + i * 0.05, 0.8)
    assert LEFT_ARM.percent_at(servos.left_arm.position) > 0


def test_arm_choice_can_repeat_and_can_choose_the_other_side(monkeypatch):
    _, servos, _, frame = envelope_fixture(monkeypatch)
    sides = iter(("left", "left", "right"))
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.choice", lambda _: next(sides)
    )
    gestures = []
    resting = True
    for i in range(230):
        frame(10 + i * 0.05, 0.8)
        left = LEFT_ARM.percent_at(servos.left_arm.position)
        right = RIGHT_ARM.percent_at(servos.right_arm.position)
        if resting and max(left, right) > 0:
            gestures.append("left" if left > 0 else "right")
        resting = max(left, right) == 0
    assert gestures == ["left", "left", "right"]


def test_head_hold_leaves_coordinated_arm_gestures_available(monkeypatch):
    animator, servos, _, frame = envelope_fixture(monkeypatch)
    servos.head.position = -0.6
    animator._sync_from_servos()
    animator.hold_head(5)
    for i in range(27):
        frame(10 + i * 0.05, 0.8)
    assert servos.head.position == -0.6
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(32)
    for i in range(27, 55):
        frame(10 + i * 0.05)
    assert servos.head.position == -0.6
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(0)


def test_missed_head_window_preserves_unexpired_arm_without_late_rise(monkeypatch):
    _, servos, _, frame = envelope_fixture(monkeypatch)
    for i in range(17):
        frame(10 + i * 0.05, 0.8)
    head = servos.head.position
    early_arm = LEFT_ARM.percent_at(servos.left_arm.position)
    frame(11.7)  # Head settle expired; arm's original return is still live.
    assert servos.head.position == head
    assert LEFT_ARM.percent_at(servos.left_arm.position) <= early_arm
    previous = LEFT_ARM.percent_at(servos.left_arm.position)
    for i in range(35, 47):
        frame(10 + i * 0.05)
        current = LEFT_ARM.percent_at(servos.left_arm.position)
        assert current <= previous
        previous = current
    assert previous == pytest.approx(0)


def test_missing_both_windows_discards_expired_arm_motion(monkeypatch):
    animator, _, _, frame = envelope_fixture(monkeypatch)
    for i in range(17):
        frame(10 + i * 0.05, 0.8)
    pose = animator._positions()
    frame(14)
    frame(15)
    assert animator._positions() == pose


def test_coordinated_gestures_leave_rest_before_first_movement(monkeypatch):
    animator, servos, _, frame = envelope_fixture(monkeypatch)
    for i in range(7):
        frame(10 + i * 0.05, 0.8)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == 0
    assert RIGHT_ARM.percent_at(servos.right_arm.position) == 0


def test_coordinated_gestures_never_move_both_arms_at_once(monkeypatch):
    _, servos, _, frame = envelope_fixture(monkeypatch)
    moving_frames = 0
    previous = (0, 0)
    for i in range(400):
        frame(10 + i * 0.05, 0.8)
        positions = (
            LEFT_ARM.percent_at(servos.left_arm.position),
            RIGHT_ARM.percent_at(servos.right_arm.position),
        )
        moving = [abs(a - b) > 0.01 for a, b in zip(positions, previous)]
        assert sum(moving) <= 1
        assert max(positions) <= 32
        moving_frames += any(moving)
        previous = positions
    assert moving_frames > 10


def test_sustained_quiet_settles_arm_to_calibrated_rest(monkeypatch):
    _, servos, _, frame = envelope_fixture(monkeypatch)
    for i in range(19):
        frame(10 + i * 0.05, 0.8)
    for i in range(19, 55):
        frame(10 + i * 0.05)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(0)
    assert RIGHT_ARM.percent_at(servos.right_arm.position) == pytest.approx(0)


def test_resumed_speech_cannot_replay_peak_after_a_missed_frame(monkeypatch):
    _, servos, _, frame = envelope_fixture(monkeypatch)
    for i in range(17):
        frame(10 + i * 0.05, 0.8)
    frame(11.7)
    previous = LEFT_ARM.percent_at(servos.left_arm.position)
    for i in range(1, 14):
        frame(11.7 + i * 0.05, 0.8)
        current = LEFT_ARM.percent_at(servos.left_arm.position)
        assert current <= previous
        previous = current
    assert previous == pytest.approx(0)


@pytest.mark.parametrize("height", [12, 32])
def test_completed_lift_holds_through_a_normal_speech_pause(monkeypatch, height):
    _, servos, _, frame = envelope_fixture(monkeypatch)
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.triangular", lambda *args: height
    )
    for i in range(27):
        frame(10 + i * 0.05, 0.8)
    peak = LEFT_ARM.percent_at(servos.left_arm.position)
    assert peak == pytest.approx(height, abs=0.5)
    for i in range(27, 35):
        frame(10 + i * 0.05)
        assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(peak)
    frame(11.95)
    assert 0 < LEFT_ARM.percent_at(servos.left_arm.position) < peak
    frame(12.7)
    assert LEFT_ARM.percent_at(servos.left_arm.position) == pytest.approx(0)
