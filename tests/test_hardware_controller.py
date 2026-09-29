"""Direct hardware lifetime and physical local-media completion contracts."""

import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from blooglyblob.hardware.controller import HardwareController


class Audio:
    def __init__(self):
        from blooglyblob.audio.presentation import OutputPresentation

        self.presentation = OutputPresentation()
        self.muted = 0
        self.calls = []
        self.entered = threading.Event()
        self.allow = threading.Event()
        self.release_gate = None
        self.failure = False
        self.active = False

    def mute(self):
        self.muted += 1

    async def release(self):
        if self.release_gate:
            await self.release_gate.wait()
        assert not self.active, "release raced physical writer"
        self.calls.append("release")
        if self.failure:
            raise RuntimeError("private device error")

    def play_file(self, path, stop_event, *, output_rate=None, music=False):
        self.active = True
        self.calls.append((str(path), output_rate))
        self.entered.set()
        self.allow.wait(2)
        self.active = False
        self.calls.append("physical-close")


async def until(predicate):
    async with asyncio.timeout(2):
        while not predicate():
            await asyncio.sleep(0.002)


def rig(tmp_path, **kwargs):
    (tmp_path / "songs").mkdir(exist_ok=True)
    (tmp_path / "sounds").mkdir(exist_ok=True)
    (tmp_path / "songs/dance_song_beats.json").write_text('{"bpm":120,"beats":[]}')
    audio = kwargs.pop("audio", None) or Audio()
    button = MagicMock()
    hardware = HardwareController(
        audio,
        media_dir=tmp_path,
        button_factory=lambda: button,
        servo_factory=lambda: None,
        led_factory=lambda **_: None,
        ambient_factory=lambda **_: None,
        **kwargs,
    )
    return hardware, audio, button


@pytest.mark.parametrize("kind", ["dance", "chime"])
async def test_button_during_delayed_start_mutes_without_waiting(tmp_path, kind):
    decisions = []
    hardware, audio, button = rig(
        tmp_path, on_button=lambda: decisions.append("button")
    )
    await hardware.prepare()
    audio.release_gate = asyncio.Event()
    if kind == "dance":
        assert hardware.start_dance("old") == "Dance mode starting"
    else:
        task = asyncio.create_task(hardware.chime("old"))
        await asyncio.sleep(0)
    button.when_pressed()
    assert audio.muted == 1
    assert not decisions
    audio.release_gate.set()
    await hardware.stop_media()
    if kind == "chime":
        await task
    assert decisions == ["button"]
    assert not audio.entered.is_set()
    await hardware.close()


async def test_dance_completion_after_physical_release_once(tmp_path):
    completions = []
    hardware, audio, _ = rig(
        tmp_path,
        on_dance_finished=lambda ident: completions.append((ident, list(audio.calls))),
    )
    await hardware.prepare()
    assert hardware.start_dance("first") == "Dance mode starting"
    assert hardware.start_dance("other") == "Already dancing!"
    await until(audio.entered.is_set)
    assert not completions
    audio.allow.set()
    await until(lambda: bool(completions))
    assert completions[0][0] == "first"
    assert completions[0][1][-2:] == ["physical-close", "release"]
    assert hardware.start_dance("second") == "Dance mode starting"
    await until(lambda: len(completions) == 2)
    assert [x[0] for x in completions] == ["first", "second"]
    await hardware.stop_media()
    await hardware.stop_media()
    assert len(completions) == 2
    await hardware.close()


async def test_chime_waits_for_real_release_and_uses_audio_owner(tmp_path):
    hardware, audio, _ = rig(tmp_path)
    await hardware.prepare()
    task = asyncio.create_task(hardware.chime("alert"))
    await until(audio.entered.is_set)
    hardware.mute_media()
    assert not task.done()
    audio.allow.set()
    await task
    assert audio.calls[1] == (str(tmp_path / "sounds/alert_16k.wav"), 48000)
    assert audio.calls[-2:] == ["physical-close", "release"]
    await hardware.close()


async def test_failed_release_blocks_next_media_and_is_content_free(tmp_path):
    errors = []
    hardware, audio, _ = rig(
        tmp_path, on_failure=lambda ident, reason: errors.append((ident, reason))
    )
    await hardware.prepare()
    audio.failure = True
    with pytest.raises(RuntimeError):
        await hardware.chime("failed")
    assert errors == [("failed", "media_release_failed")]
    with pytest.raises(RuntimeError):
        hardware.start_dance("next")
    with pytest.raises(RuntimeError):
        await hardware.close()


async def test_prepare_registers_once_and_close_is_repeatable(tmp_path):
    hardware, _, button = rig(tmp_path)
    await asyncio.gather(hardware.prepare(), hardware.prepare())
    registered = button.when_pressed
    await hardware.prepare()
    assert button.when_pressed is registered
    await hardware.close()
    await hardware.close()
    button.close.assert_called_once()


async def test_presentation_and_levels_do_not_call_audio(tmp_path):
    hardware, audio, _ = rig(tmp_path)
    await hardware.prepare()
    for state in ["idle", "listening", "speaking", "processing", "dancing", "alert"]:
        hardware.present(state)
        hardware.set_level(2)
        assert hardware.presentation.mode.value == state
        assert hardware.presentation.audio_level == 1
    assert audio.calls == []
    assert audio.muted == 0
    await hardware.close()


async def test_partial_preparation_cleans_existing_controllers(tmp_path):
    leds, servos, ambient = MagicMock(), MagicMock(), MagicMock()
    hardware, _, _ = rig(tmp_path)
    hardware._servo_factory = lambda: servos
    hardware._led_factory = lambda **_: leds
    hardware._ambient_factory = lambda **_: ambient
    hardware._button_factory = lambda: (_ for _ in ()).throw(
        RuntimeError("button unavailable")
    )
    with pytest.raises(RuntimeError, match="hardware_prepare_failed"):
        await hardware.prepare()
    ambient.stop.assert_called_once()
    leds.cleanup.assert_called_once()
    servos.cleanup.assert_called_once()
    await hardware.close()
    servos.cleanup.assert_called_once()


async def test_optional_failed_start_cleans_created_led_and_keeps_button(tmp_path):
    hardware, _, button = rig(tmp_path)
    leds = MagicMock()
    leds.start.side_effect = RuntimeError("start failed")
    hardware._led_factory = lambda **_: leds
    hardware._servo_factory = lambda: (_ for _ in ()).throw(
        RuntimeError("missing servo")
    )
    await hardware.prepare()
    assert hardware.servos is None and hardware.leds is None
    leds.cleanup.assert_called_once()
    assert callable(button.when_pressed)
    await hardware.close()


async def test_blocked_dance_cleanup_keeps_physical_dependencies(tmp_path):
    errors, completions = [], []
    hardware, audio, button = rig(
        tmp_path,
        operation_timeout=0.02,
        on_failure=lambda ident, reason: errors.append(reason),
        on_dance_finished=completions.append,
    )
    await hardware.prepare()
    servos, leds, ambient = MagicMock(), MagicMock(), MagicMock()
    hardware.servos, hardware.leds, hardware.ambient = servos, leds, ambient
    hardware.start_dance("blocked")
    await until(audio.entered.is_set)
    button.when_pressed()
    assert audio.muted == 1
    assert audio.active
    try:
        with pytest.raises(RuntimeError):
            await hardware.close()
        servos.cleanup.assert_not_called()
        leds.cleanup.assert_not_called()
        ambient.stop.assert_not_called()
        button.close.assert_called_once()
        assert audio.calls.count("release") == 1
        assert not completions
        assert errors
        assert hardware.ownership_uncertain
    finally:
        audio.allow.set()
        await until(
            lambda: not any(w.thread.is_alive() for w in hardware.media.active.workers)
        )


async def test_close_suppresses_retiring_dance_completion(tmp_path):
    finished = []
    hardware, audio, _ = rig(tmp_path, on_dance_finished=finished.append)
    await hardware.prepare()
    hardware.start_dance("retiring")
    await until(audio.entered.is_set)
    close = asyncio.create_task(hardware.close())
    await asyncio.sleep(0)
    audio.allow.set()
    await close
    assert finished == []


async def test_stale_dance_completion_does_not_change_presentation(tmp_path):
    hardware, audio, _ = rig(tmp_path)
    await hardware.prepare()
    hardware.start_dance("old")
    await until(audio.entered.is_set)
    hardware.present("listening")
    audio.allow.set()
    await hardware.stop_media()
    assert hardware.presentation.mode.value == "listening"
    await hardware.close()


async def test_file_worker_failure_never_reports_dance_success(tmp_path):
    errors, finished = [], []
    hardware, audio, _ = rig(
        tmp_path,
        on_failure=lambda ident, reason: errors.append((ident, reason)),
        on_dance_finished=finished.append,
    )

    def broken(*args, **kwargs):
        raise RuntimeError("private filename")

    audio.play_file = broken
    await hardware.prepare()
    hardware.start_dance("broken")
    await until(lambda: bool(errors))
    assert errors == [("broken", "media_worker_failed")]
    assert finished == []
    assert not hardware.ownership_uncertain
    await hardware.close()


async def test_unexpected_callbacks_are_observed_without_content(tmp_path, caplog):
    failures = []

    def broken():
        raise RuntimeError("secret content")

    hardware, _, button = rig(
        tmp_path,
        on_button=broken,
        on_failure=lambda ident, reason: failures.append(reason),
    )
    await hardware.prepare()
    button.when_pressed()
    await asyncio.sleep(0)
    assert failures == ["hardware_callback_failed"]
    assert "secret content" not in caplog.text
    await hardware.close()


async def test_default_paths_use_package_resources(monkeypatch):
    monkeypatch.delenv("BLOOGLYBLOB_MEDIA_DIR", raising=False)
    hardware = HardwareController(
        Audio(),
        servo_factory=lambda: None,
        led_factory=lambda **_: None,
        button_factory=MagicMock,
    )
    await hardware.prepare()
    assert hardware.alert_path.is_file()
    assert hardware.search_path.is_file()
    assert hardware.dance_path.is_file()
    assert hardware.beats_path.is_file()
    await hardware.close()


def test_import_hardware_controller_does_not_load_driver_or_calibration():
    import subprocess
    import sys

    code = "import sys; import blooglyblob.hardware.controller; assert not any(x in sys.modules for x in ['gpiozero','rpi_ws281x','pyaudio','blooglyblob.hardware.servo_config','pi.main','client.state'])"
    subprocess.run([sys.executable, "-c", code], check=True)


@pytest.mark.parametrize("which", ["ambient", "leds"])
def test_native_stop_never_claims_stuck_worker_stopped(which):
    from blooglyblob.hardware.ambient_animator import AmbientAnimator
    from blooglyblob.hardware.led_controller import LEDController
    from blooglyblob.hardware.conversation_state import ConversationState

    if which == "ambient":
        controller = AmbientAnimator(MagicMock(), ConversationState(), threading.Lock())
    else:
        controller = LEDController.__new__(LEDController)
        from blooglyblob.hardware.lighting import LightingState

        controller.lighting = LightingState()
        controller._clear_all = MagicMock()
    controller._thread = MagicMock()
    controller._thread.is_alive.return_value = True
    with pytest.raises(RuntimeError, match="release not confirmed"):
        controller.stop()
    if which == "leds":
        controller._clear_all.assert_not_called()


@pytest.mark.parametrize("speaker_index", [0, 1])
async def test_chime_and_dance_use_same_real_audio_selection(
    monkeypatch, tmp_path, speaker_index
):
    """Full LocalMedia -> AudioController -> fake PortAudio boundary, no devices."""
    import sys
    import wave
    from types import SimpleNamespace
    from blooglyblob.audio.controller import AudioController

    for directory in ("songs", "sounds"):
        (tmp_path / directory).mkdir()
    for path, rate in [
        ("songs/dance_song.wav", 22050),
        ("sounds/alert_16k.wav", 16000),
    ]:
        with wave.open(str(tmp_path / path), "wb") as source:
            source.setnchannels(1)
            source.setsampwidth(2)
            source.setframerate(rate)
            source.writeframes(b"\0" * 2048)
    players = []
    devices = [
        {"name": "USB wrong hw:2", "maxOutputChannels": 2},
    ]
    devices.insert(
        speaker_index, {"name": "USB selected speaker hw:4", "maxOutputChannels": 2}
    )

    def player():
        pa = MagicMock()
        pa.get_device_count.return_value = len(devices)
        pa.get_device_info_by_index.side_effect = devices.__getitem__
        players.append(pa)
        return pa

    monkeypatch.setenv("AUDIO_OUTPUT_DEVICE", "selected speaker")
    monkeypatch.setitem(sys.modules, "pyaudio", SimpleNamespace(PyAudio=player))
    finished = []
    audio = AudioController()
    hardware, _, _ = rig(tmp_path, audio=audio, on_dance_finished=finished.append)
    await hardware.prepare()
    await hardware.chime("alert")
    hardware.start_dance("dance")
    await until(lambda: bool(finished))
    assert len(players) == 2
    assert [pa.open.call_args.kwargs["output_device_index"] for pa in players] == [
        speaker_index,
        speaker_index,
    ]
    assert [pa.open.call_args.kwargs["rate"] for pa in players] == [48000, 22050]
    for pa in players:
        pa.open.return_value.close.assert_called_once()
        pa.terminate.assert_called_once()
    await hardware.close()
    await audio.close()


async def test_completed_file_error_can_recover_after_confirmed_release(tmp_path):
    hardware, audio, _ = rig(tmp_path)
    await hardware.prepare()
    original = audio.play_file
    audio.play_file = MagicMock(side_effect=RuntimeError("bad media"))
    with pytest.raises(RuntimeError, match="media_worker_failed"):
        await hardware.chime("bad")
    assert audio.calls == ["release", "release"]
    assert not hardware.ownership_uncertain
    assert hardware.media.active is None
    audio.play_file = original
    audio.allow.set()
    await hardware.chime("good")
    await hardware.close()


async def test_failed_ambient_stop_preserves_servos_but_closes_independent_devices(
    tmp_path,
):
    hardware, _, button = rig(tmp_path)
    await hardware.prepare()
    servos, leds, ambient = MagicMock(), MagicMock(), MagicMock()
    hardware.servos, hardware.leds, hardware.ambient = servos, leds, ambient
    ambient.stop.side_effect = RuntimeError("stuck")
    with pytest.raises(RuntimeError, match="hardware_cleanup_failed"):
        await hardware.close()
    assert hardware.ownership_uncertain
    servos.cleanup.assert_not_called()
    leds.cleanup.assert_called_once()
    button.close.assert_called_once()


@pytest.mark.parametrize(
    "which,reason",
    [("ambient", "ambient_worker_failed"), ("leds", "led_worker_failed")],
)
def test_native_animation_worker_failure_is_sanitized(which, reason, capsys):
    from blooglyblob.hardware.ambient_animator import AmbientAnimator
    from blooglyblob.hardware.led_controller import LEDController

    cls = AmbientAnimator if which == "ambient" else LEDController
    controller = cls.__new__(cls)
    controller._animation_loop = MagicMock(side_effect=RuntimeError("private details"))
    failures = []
    controller.on_failure = failures.append
    controller._guarded_loop()
    assert failures == [reason]
    assert "private details" not in capsys.readouterr().out


def test_servo_cleanup_closes_factory_and_does_not_swallow_failure(monkeypatch):
    from blooglyblob.hardware.servo_controller import BaseServo
    from blooglyblob.hardware.servo_config import ServoProfile
    from blooglyblob.hardware.local_media import HardwareReleaseError

    monkeypatch.setattr(
        "blooglyblob.hardware.servo_controller.time.sleep", lambda _: None
    )
    servo = BaseServo.__new__(BaseServo)
    servo.profile = ServoProfile()
    servo._servo = native = MagicMock()
    native.close.side_effect = RuntimeError("cannot close")
    with pytest.raises(HardwareReleaseError):
        servo.cleanup()
    native.pin_factory.close.assert_called_once()
    assert servo._servo is native


def test_supported_gpio_and_native_timing_profile():
    from blooglyblob.hardware.config import gpio_config
    from blooglyblob.hardware.servo_controller import (
        DEFAULT_STEP,
        DEFAULT_DELAY,
        MIN_PULSE_WIDTH,
        MAX_PULSE_WIDTH,
    )
    from blooglyblob.hardware.config import BODY_LEDS, EYE_LEDS
    from blooglyblob.hardware.lighting import EYE_COLOR

    assert vars(gpio_config) == {
        "LEFT_ARM_PIN": 12,
        "RIGHT_ARM_PIN": 13,
        "HEAD_PIN": 16,
        "LED_PIN": 18,
        "LED_COUNT": 16,
        "LED_BRIGHTNESS": 128,
        "BUTTON_PIN": 17,
    }
    assert (DEFAULT_STEP, DEFAULT_DELAY, MIN_PULSE_WIDTH, MAX_PULSE_WIDTH) == (
        0.02,
        0.015,
        0.001,
        0.002,
    )
    assert list(BODY_LEDS) == list(range(6))
    assert list(EYE_LEDS) == [6, 7]
    assert EYE_COLOR == (255, 200, 150)


@pytest.mark.parametrize(
    "failure_stage,created_count", [("right_arm", 1), ("head", 2), ("rest", 3)]
)
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_servo_construction_cleans_only_created_devices(
    monkeypatch, failure_stage, created_count, cleanup_fails
):
    from blooglyblob.hardware import servo_controller as module
    from blooglyblob.hardware.local_media import HardwareReleaseError

    created = []
    failure = ValueError("startup positioning failed")

    def construct(pin, calibration, name):
        if name.lower().replace(" ", "_") == failure_stage:
            raise failure
        servo = MagicMock()
        created.append(servo)
        if cleanup_fails and len(created) == 1:
            servo.cleanup.side_effect = RuntimeError("release unconfirmed")
        return servo

    monkeypatch.setattr(module, "ArmServo", construct)
    monkeypatch.setattr(module, "HeadServo", construct)
    if failure_stage == "rest":
        monkeypatch.setattr(
            module.ServoController, "fit_pose", MagicMock(side_effect=failure)
        )
    expected = HardwareReleaseError if cleanup_fails else ValueError
    with pytest.raises(expected) as captured:
        module.ServoController()
    if not cleanup_fails:
        assert captured.value is failure
    assert len(created) == created_count
    for servo in created:
        servo.cleanup.assert_called_once_with()


async def test_completed_gesture_failures_remain_bounded_and_observed(tmp_path):
    failures = []
    hardware, _, _ = rig(tmp_path, on_failure=lambda *args: failures.append(args))
    await hardware.prepare()

    def failed():
        raise RuntimeError("private native detail")

    for _ in range(40):
        assert hardware._gesture(failed)
        await until(lambda: not hardware.animation_lock.locked())
        await asyncio.sleep(0.001)
        assert len(hardware._gestures) <= 1
    with pytest.raises(RuntimeError, match="gesture_failed"):
        await hardware.wait_gestures()
    assert len(failures) == 40
    assert not hardware.ownership_uncertain
    await hardware.close()


async def test_completed_optional_gesture_error_does_not_claim_unreleased_hardware(
    tmp_path,
):
    failures = []
    hardware, _, button = rig(tmp_path, on_failure=lambda *args: failures.append(args))
    await hardware.prepare()

    def failed():
        raise RuntimeError("private")

    assert hardware._gesture(failed)
    await until(lambda: bool(failures))
    await hardware.close()
    button.close.assert_called_once()
    assert not hardware.ownership_uncertain


async def test_lighting_states_preserve_servo_mode_and_shutdown_wins(tmp_path):
    from blooglyblob.hardware.conversation_state import ConversationMode
    from blooglyblob.hardware.lighting import render

    hardware, audio, _ = rig(tmp_path)
    await hardware.prepare()
    hardware.present("listening")
    hardware.light("waiting")
    assert hardware.presentation.mode == ConversationMode.LISTENING
    assert hardware.lighting.snapshot(2).mode == "waiting"
    await hardware.close()
    hardware.light("dancing")
    assert render(hardware.lighting.snapshot(2), 2) == ((0, 0, 0),) * 16
