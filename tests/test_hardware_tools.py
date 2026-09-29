"""Preserved direct gesture tool results and physical choreography."""

import threading
from unittest.mock import AsyncMock, MagicMock

import pytest

from blooglyblob.hardware.controller import ANIMATIONS, HEAD_SPEEDS, HardwareController
from blooglyblob.hardware.local_media import dance_move


@pytest.mark.parametrize(
    "name", ["wave_hello", "celebrate", "think", "shrug", "six_seven", "attention"]
)
async def test_each_animation_holds_and_releases_lock(name):
    servos, ambient = MagicMock(), MagicMock()
    hardware = HardwareController(MagicMock())
    hardware.servos, hardware.ambient = servos, ambient
    assert (
        await hardware.execute("playAnimation", {"animation": name})
        == f"Playing {name}"
    )
    await hardware.wait_gestures()
    getattr(servos, name).assert_called_once_with()
    ambient.hold_all.assert_called_once_with(5.0)
    assert not hardware.animation_lock.locked()
    assert set(ANIMATIONS) == {
        "wave_hello",
        "celebrate",
        "think",
        "shrug",
        "six_seven",
        "attention",
    }


@pytest.mark.parametrize(
    "direction,method",
    [("left", "look_left"), ("right", "look_right"), ("center", "center")],
)
@pytest.mark.parametrize(
    "speed,value", [("slow", 0.5), ("normal", 1.0), ("fast", 2.5), ("unknown", 1.0)]
)
async def test_head_speeds_and_holds(direction, method, speed, value):
    hardware = HardwareController(MagicMock())
    hardware.servos, hardware.ambient = MagicMock(), MagicMock()
    assert (
        await hardware.execute("moveHead", {"direction": direction, "speed": speed})
        == f"Moving head {direction}"
    )
    await hardware.wait_gestures()
    getattr(hardware.servos.head, method).assert_called_once_with(speed=value)
    hardware.ambient.hold_head.assert_called_once_with(5.0)
    assert HEAD_SPEEDS == {"slow": 0.5, "normal": 1.0, "fast": 2.5}


async def test_tool_errors_sleep_busy_and_diagnostics():
    hardware = HardwareController(MagicMock())
    assert (
        await hardware.execute("playAnimation", {"animation": "bad"})
        == "Error: Unknown animation 'bad'"
    )
    assert (
        await hardware.execute("playAnimation", {"animation": "think"})
        == "Error: Servo controller not initialized"
    )
    assert (
        await hardware.execute("moveHead", {"direction": "up"})
        == "Error: Invalid direction 'up'"
    )
    assert (
        await hardware.execute("moveHead", {"direction": "left"})
        == "Error: Servo controller not initialized"
    )
    assert await hardware.execute("goToSleep", {}) == "Going to sleep"
    assert await hardware.execute("bad", {}) == "Error: Unknown tool 'bad'"
    hardware.servos = MagicMock()
    hardware.animation_lock.acquire()
    assert (
        await hardware.execute("playAnimation", {"animation": "think"})
        == "Error: Animation already playing"
    )
    assert (
        await hardware.execute("moveHead", {"direction": "left"}) == "Moving head left"
    )
    hardware.present("idle")
    hardware.servos.head.center.assert_not_called()
    hardware.animation_lock.release()
    await hardware.rest()
    await hardware.detach_all()
    hardware.servos.rest.assert_called_once_with()
    hardware.servos.detach_all.assert_called_once_with()


def test_dance_pattern_values_and_accents(monkeypatch):
    servos = MagicMock()
    monkeypatch.setattr(
        "blooglyblob.hardware.local_media.random.uniform", lambda *_: 0.0
    )
    pauses = []
    monkeypatch.setattr("blooglyblob.hardware.local_media.time.sleep", pauses.append)
    for index in range(17):
        dance_move(servos, index, 120)
    assert [call.kwargs["speed"] for call in servos.head.look_left.call_args_list] == [
        2.5,
        2.5,
    ]
    assert servos.head.center.call_count == 2
    servos.head.look_right.assert_called_once_with(speed=2.5)
    assert servos.left_arm.set_percent.call_args_list[0].args == (65.0,)
    assert servos.left_arm.set_percent.call_args_list[1].args == (35.0,)
    assert servos.left_arm.set_percent.call_args_list[-2].args == (80,)
    assert servos.left_arm.set_percent.call_args_list[-2].kwargs == {"speed": 3.0}
    assert pauses == [0.15]


async def test_gesture_failure_is_reported_and_lock_released():
    failures = []
    hardware = HardwareController(
        MagicMock(), on_failure=lambda ident, reason: failures.append(reason)
    )
    hardware.servos = MagicMock()
    hardware.servos.think.side_effect = RuntimeError("private detail")
    await hardware.execute("playAnimation", {"animation": "think"})
    with pytest.raises(RuntimeError, match="gesture_failed"):
        await hardware.wait_gestures()
    assert failures == ["gesture_failed"]
    assert not hardware.animation_lock.locked()


async def test_gesture_timeout_does_not_cleanup_owned_servos():
    release = threading.Event()
    hardware = HardwareController(MagicMock(), operation_timeout=0.02)
    hardware.servos = MagicMock()
    hardware.servos.think.side_effect = lambda: release.wait(2)
    await hardware.execute("playAnimation", {"animation": "think"})
    try:
        with pytest.raises(RuntimeError):
            await hardware.close()
        hardware.servos.cleanup.assert_not_called()
    finally:
        release.set()
        await hardware.wait_gestures()


async def test_real_dance_uses_every_second_beat_and_clears_ambient_hold(
    tmp_path, monkeypatch
):
    import asyncio
    from blooglyblob.hardware.local_media import LocalMedia

    beats = tmp_path / "beats.json"
    beats.write_text('{"bpm":120,"beats":[0,0,0,0,0]}')
    hardware = HardwareController(MagicMock())
    hardware.servos, hardware.ambient, hardware.leds = (
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    hardware.beats_path, hardware.dance_path = beats, tmp_path / "dance.wav"
    audio = MagicMock()
    audio.release = AsyncMock()
    media = LocalMedia(audio, hardware)
    calls = []
    monkeypatch.setattr(
        "blooglyblob.hardware.local_media.dance_move",
        lambda servos, index, bpm: calls.append((index, bpm)),
    )
    assert media.start_dance("dance") == "Dance mode starting"
    await asyncio.shield(media.active.task)
    assert calls == [(0, 120), (1, 120), (2, 120)]
    assert [c.args for c in hardware.ambient.hold_all.call_args_list] == [
        (300.0,),
        (0,),
    ]
    hardware.servos.head.center.assert_called_once_with(speed=1.0)
    hardware.servos.left_arm.down.assert_called_once_with(speed=1.0)
    hardware.servos.right_arm.down.assert_called_once_with(speed=1.0)
    assert audio.play_file.call_count == 1
    assert audio.release.await_count == 2


async def test_listening_voice_presentation_preserves_ambient_holds(monkeypatch):
    from blooglyblob.hardware.ambient_animator import AmbientAnimator
    from blooglyblob.hardware.servo_config import ServoProfile
    from types import SimpleNamespace

    hardware = HardwareController(MagicMock())
    profile = ServoProfile(start=0, end=1)
    servos = SimpleNamespace(
        **{
            name: SimpleNamespace(position=0.0, profile=profile)
            for name in ("head", "left_arm", "right_arm")
        }
    )
    animator = AmbientAnimator(servos, hardware.presentation, threading.Lock())
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.random", lambda: 0.0
    )
    monkeypatch.setattr(
        "blooglyblob.hardware.ambient_animator.random.uniform", lambda low, high: high
    )
    hardware.present("listening")
    hardware.set_level(0.8)
    animator._update()
    assert hardware.presentation.mode.value == "listening"

    def positions():
        return (
            servos.head.position,
            servos.left_arm.position,
            servos.right_arm.position,
        )

    initial = positions()
    assert initial[1] > 0
    hardware.set_level(0)
    animator._update()
    assert positions() == initial
    hardware.set_level(0.8)
    animator.hold_all(300)
    animator._update()
    assert positions() == initial
    animator.hold_all(0)
    for state in ("idle", "dancing", "alert"):
        hardware.present(state)
        animator._update()
        assert positions() == initial


def test_dance_move_error_continues_without_logging_private_content(caplog):
    servos = MagicMock()
    servos.head.look_left.side_effect = RuntimeError("private device details")
    dance_move(servos, 0, 120)
    dance_move(servos, 1, 120)
    assert servos.left_arm.set_percent.call_count == 1
    assert "dance_move_failed" in caplog.text
    assert "private device details" not in caplog.text


async def test_completed_gesture_failure_is_consumed_and_next_gesture_runs():
    hardware = HardwareController(MagicMock())
    hardware.servos = MagicMock()
    hardware.servos.think.side_effect = RuntimeError("bad movement")
    await hardware.execute("playAnimation", {"animation": "think"})
    with pytest.raises(RuntimeError, match="gesture_failed"):
        await hardware.wait_gestures()
    assert not hardware.ownership_uncertain
    assert (
        await hardware.execute("playAnimation", {"animation": "shrug"})
        == "Playing shrug"
    )
    await hardware.wait_gestures()
    await hardware.close()
