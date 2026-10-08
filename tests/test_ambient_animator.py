"""Ambient movements must share gesture ownership and current positions."""

import threading
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
    state.mode, state.audio_level = ConversationMode.SPEAKING, 0.8
    lock = threading.Lock()
    animator = AmbientAnimator(servos, state, lock)
    animator._sync_from_servos()
    animator._head_target = 0.5
    animator._update_speaking = lambda level: None
    return animator, servos, lock


def test_ambient_updates_only_while_owning_gesture_lock(monkeypatch):
    animator, servos, lock = animator_fixture()
    observed = []
    apply = animator._apply_movements

    def record():
        observed.append(lock.locked())
        apply()

    animator._apply_movements = record
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
