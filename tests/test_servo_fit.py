"""Exercise real fit control with only the native GPIO boundary replaced."""

import signal
from pathlib import Path
import re
from unittest.mock import Mock

import pytest


@pytest.fixture
def native_servos(monkeypatch):
    from blooglyblob.hardware import servo_controller

    devices = []

    class NativeServo:
        def __init__(self, pin, **kwargs):
            self.pin = pin
            self.kwargs = kwargs
            self.pin_factory = kwargs["pin_factory"]
            self.values = [kwargs.get("initial_value", 0)]
            self.closed = False
            devices.append(self)

        @property
        def value(self):
            return self.values[-1]

        @value.setter
        def value(self, value):
            self.values.append(value)

        def detach(self):
            self.value = None

        def close(self):
            self.closed = True

    monkeypatch.setattr(servo_controller, "ON_PI", True)
    monkeypatch.setattr(servo_controller, "Servo", NativeServo)
    monkeypatch.setattr(servo_controller, "PiGPIOFactory", Mock, raising=False)
    return devices


@pytest.mark.parametrize("ending", ["STOP", "eof", "interrupt", "SIGTERM", "SIGHUP"])
def test_fit_holds_all_axes_and_releases_without_recentering(
    native_servos, monkeypatch, capsys, ending
):
    from blooglyblob.hardware import servo_fit

    prompts = []

    def read(prompt):
        prompts.append(prompt)
        assert [servo.pin for servo in native_servos] == [12, 13, 16]
        for servo, pulse in zip(native_servos, (2000, 1000, 1500), strict=True):
            assert servo.values[0] is None
            assert len(servo.values) == 2
            width = servo.kwargs["min_pulse_width"] + (servo.value + 1) / 2 * (
                servo.kwargs["max_pulse_width"] - servo.kwargs["min_pulse_width"]
            )
            assert width * 1_000_000 == pytest.approx(pulse)
            assert not servo.closed
        if len(prompts) == 1:
            return "anything else"
        if ending == "eof":
            raise EOFError
        if ending == "interrupt":
            raise KeyboardInterrupt
        if ending.startswith("SIG"):
            signal.raise_signal(getattr(signal, ending))
        return ending

    monkeypatch.setattr("builtins.input", read)
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP)}
    assert servo_fit.main([]) == (0 if ending == "STOP" else 1)
    assert len(prompts) == 2
    # Only a completed hold tells the builder to fasten the parts.
    output = capsys.readouterr().out
    assert "Servo pulses stopped" in output
    assert ("drive the center screws" in output) == (ending == "STOP")
    for servo in native_servos:
        assert servo.values[-1] is None
        assert len(servo.values) == 3  # off, fit, off; no center or sweep
        assert servo.closed
        servo.pin_factory.close.assert_called_once()
    assert {sig: signal.getsignal(sig) for sig in handlers} == handlers


def test_fit_partial_construction_releases_existing_outputs(native_servos, monkeypatch):
    from blooglyblob.hardware import servo_controller, servo_fit

    create = servo_controller._create_servo

    def fail_second(pin):
        if pin == 13:
            raise RuntimeError("creation failed")
        return create(pin)

    monkeypatch.setattr(servo_controller, "_create_servo", fail_second)
    assert servo_fit.main([]) == 1
    assert len(native_servos) == 1
    assert native_servos[0].value is None
    assert native_servos[0].closed
    native_servos[0].pin_factory.close.assert_called_once()


def test_fit_release_failure_attempts_every_output(native_servos, monkeypatch):
    from blooglyblob.hardware import servo_fit

    def read(prompt):
        native_servos[0].detach = Mock(side_effect=RuntimeError("failed"))
        return "STOP"

    monkeypatch.setattr("builtins.input", read)
    assert servo_fit.main([]) == 73
    assert all(servo.closed for servo in native_servos)
    for servo in native_servos:
        servo.pin_factory.close.assert_called_once()


def test_fit_refuses_simulation(monkeypatch):
    from blooglyblob.hardware import servo_controller, servo_fit

    monkeypatch.setattr(servo_controller, "ON_PI", False)
    read = Mock()
    monkeypatch.setattr("builtins.input", read)
    assert servo_fit.main([]) == 1
    read.assert_not_called()


def test_fit_factory_release_failure_is_ownership_uncertain(native_servos, monkeypatch):
    from blooglyblob.hardware import servo_controller, servo_fit

    factory = Mock()
    factory.close.side_effect = RuntimeError("release failed")
    monkeypatch.setattr(servo_controller, "PiGPIOFactory", Mock(return_value=factory))
    monkeypatch.setattr(
        servo_controller, "Servo", Mock(side_effect=RuntimeError("open failed"))
    )
    assert servo_fit.main([]) == 73
    factory.close.assert_called_once()


def test_fit_interrupt_during_initial_pose_releases_all_axes(
    native_servos, monkeypatch
):
    from blooglyblob.hardware import servo_controller, servo_fit

    def interrupted(controller):
        controller.left_arm.position = 1
        raise KeyboardInterrupt

    monkeypatch.setattr(servo_controller.ServoController, "fit_pose", interrupted)
    assert servo_fit.main([]) == 1
    assert len(native_servos) == 3
    assert all(servo.value is None and servo.closed for servo in native_servos)


def test_fit_interrupt_during_native_creation_releases_factory(
    native_servos, monkeypatch
):
    from blooglyblob.hardware import servo_controller, servo_fit

    factory = Mock()
    monkeypatch.setattr(servo_controller, "PiGPIOFactory", Mock(return_value=factory))
    monkeypatch.setattr(servo_controller, "Servo", Mock(side_effect=KeyboardInterrupt))
    assert servo_fit.main([]) == 1
    factory.close.assert_called_once()


@pytest.mark.parametrize("release_fails", [False, True])
def test_fit_signal_during_failed_startup_cleanup_cannot_skip_outputs(
    native_servos, monkeypatch, capsys, release_fails
):
    from blooglyblob.hardware import servo_controller, servo_fit

    def fail_pose(controller):
        controller.left_arm.position = 1
        detach = native_servos[0].detach

        def interrupted_detach():
            signal.raise_signal(signal.SIGTERM)
            if release_fails:
                raise RuntimeError("detach failed")
            detach()

        native_servos[0].detach = interrupted_detach
        raise RuntimeError("initial positioning failed")

    monkeypatch.setattr(servo_controller.ServoController, "fit_pose", fail_pose)
    handlers = {
        sig: signal.getsignal(sig)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    assert servo_fit.main([]) == (73 if release_fails else 1)
    assert all(servo.closed for servo in native_servos)
    for servo in native_servos:
        servo.pin_factory.close.assert_called_once()
    if release_fails:
        assert "Servo pulses stopped" not in capsys.readouterr().out
    else:
        assert all(servo.value is None for servo in native_servos)
    assert {sig: signal.getsignal(sig) for sig in handlers} == handlers


def test_fit_help_does_not_initialize_hardware(monkeypatch):
    from blooglyblob.hardware import servo_controller, servo_fit

    create = Mock()
    monkeypatch.setattr(servo_controller, "_create_servo", create)
    with pytest.raises(SystemExit) as exit_info:
        servo_fit.main(["--help"])
    assert exit_info.value.code == 0
    create.assert_not_called()


@pytest.mark.parametrize("release_fails", [False, True])
def test_fit_signal_during_failed_native_creation_cannot_skip_factory_release(
    native_servos, monkeypatch, release_fails
):
    from blooglyblob.hardware import servo_controller, servo_fit

    factory = Mock()
    released = []

    def close():
        signal.raise_signal(signal.SIGTERM)
        if release_fails:
            raise RuntimeError("close failed")
        released.append(True)

    factory.close.side_effect = close
    monkeypatch.setattr(servo_controller, "PiGPIOFactory", Mock(return_value=factory))
    monkeypatch.setattr(
        servo_controller, "Servo", Mock(side_effect=RuntimeError("open failed"))
    )
    assert servo_fit.main([]) == (73 if release_fails else 1)
    assert released == ([] if release_fails else [True])


def test_application_can_release_servos_from_worker_thread(native_servos):
    from concurrent.futures import ThreadPoolExecutor
    from blooglyblob.hardware.servo_controller import ServoController

    with ThreadPoolExecutor(max_workers=1) as worker:
        controller = worker.submit(ServoController).result(timeout=1)
        worker.submit(controller.cleanup).result(timeout=1)
    assert all(servo.closed and servo.value is None for servo in native_servos)


def test_application_starts_directly_at_fit_pose_and_releases_without_motion(
    native_servos,
):
    from blooglyblob.hardware.servo_controller import ServoController

    controller = ServoController()
    assert [servo.values for servo in native_servos] == [
        [None, 1],
        [None, -1],
        [None, 0],
    ]
    assert all(servo.kwargs["frame_width"] == 0.02 for servo in native_servos)
    controller.cleanup()
    assert [servo.values for servo in native_servos] == [
        [None, 1, None],
        [None, -1, None],
        [None, 0, None],
    ]


def test_ambient_uses_opposite_arm_profiles_and_resyncs_after_gesture(native_servos):
    import threading
    from blooglyblob.hardware.ambient_animator import AmbientAnimator
    from blooglyblob.hardware.conversation_state import ConversationState
    from blooglyblob.hardware.servo_controller import ServoController

    controller = ServoController()
    animator = AmbientAnimator(controller, ConversationState(), threading.Lock())
    try:
        animator._sync_from_servos()
        assert animator._left_arm_current == animator._right_arm_current == 0
        animator._left_arm_target = animator._right_arm_target = 100
        animator._apply_movements()
        # One ambient interpolation step raises both arms to 15%, using
        # opposite native directions on the mounted servos.
        assert native_servos[0].value == pytest.approx(0.7)
        assert native_servos[1].value == pytest.approx(-0.7)
        controller.left_arm.position = -0.5
        controller.right_arm.position = 0.5
        animator._sync_from_servos()
        assert animator._left_arm_current == animator._left_arm_target == 75
        assert animator._right_arm_current == animator._right_arm_target == 75
    finally:
        controller.cleanup()


def test_saved_calibration_cannot_override_fixed_positions(tmp_path, monkeypatch):
    import importlib
    from blooglyblob.hardware import servo_config

    saved = tmp_path / "servo_calibration.json"
    original = '{"left_arm":{"limit_min":-99,"position_a":0.5},"head":null}'
    saved.write_text(original)
    monkeypatch.setenv("SERVO_CALIBRATION_FILE", str(saved))
    profiles = importlib.reload(servo_config)
    assert (profiles.LEFT_ARM.rest, profiles.RIGHT_ARM.rest, profiles.HEAD.rest) == (
        1,
        -1,
        0,
    )
    assert saved.read_text() == original
    with pytest.raises((AttributeError, TypeError)):
        profiles.LEFT_ARM.rest = 0


@pytest.mark.parametrize("percent", [-10, 0, 50, 100, 110])
def test_arm_animation_maps_fixed_range_in_opposite_directions(
    native_servos, monkeypatch, percent
):
    from blooglyblob.hardware.servo_controller import ServoController

    monkeypatch.setattr(
        "blooglyblob.hardware.servo_controller.time.sleep", lambda _: None
    )
    controller = ServoController()
    expected_left = 1 - 2 * max(0, min(100, percent)) / 100
    expected_right = -expected_left
    for arm, expected in (
        (controller.left_arm, expected_left),
        (controller.right_arm, expected_right),
    ):
        arm.set_percent(percent)
        assert arm.position == pytest.approx(expected)
        assert arm.profile.at_percent(percent) == pytest.approx(expected)
        assert arm.profile.percent_at(expected) == pytest.approx(
            max(0, min(100, percent))
        )
    controller.head.position = 99
    assert controller.head.position == 1
    controller.head.move_to(-99)
    assert controller.head.position == -1
    controller.head.look_left()
    assert controller.head.position == 1
    controller.head.look_right()
    assert controller.head.position == -1
    assert all(
        -1 <= value <= 1
        for servo in native_servos
        for value in servo.values
        if value is not None
    )
    controller.cleanup()


def test_guide_fit_table_and_operating_ranges_match_native_outputs(native_servos):
    from blooglyblob.hardware.servo_controller import ServoController

    controller = ServoController()
    reference = (
        Path(__file__).resolve().parents[1]
        / "hardware/build-guide/src/downloads/servo-fit-reference.md"
    ).read_text()
    axes = dict(
        zip(("Robot-left arm", "Robot-right arm", "Head"), native_servos, strict=True)
    )
    seen = set()
    for line in reference.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells[0] not in axes:
            continue
        servo = axes[cells[0]]
        minimum = servo.kwargs["min_pulse_width"] * 1_000_000
        maximum = servo.kwargs["max_pulse_width"] * 1_000_000
        if len(cells) == 6:
            assert int(cells[1]) == servo.pin
            assert float(cells[4].removesuffix(" µs")) == pytest.approx(
                minimum + (servo.value + 1) / 2 * (maximum - minimum)
            )
            seen.add((cells[0], "fit"))
        elif len(cells) == 3:
            match = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)\s*µs", cells[1])
            assert match is not None
            assert tuple(map(int, match.groups())) == (minimum, maximum)
            seen.add((cells[0], "range"))
    assert seen == {(name, kind) for name in axes for kind in ("fit", "range")}
    controller.cleanup()


def test_servo_factory_uses_low_idle_pin_release(native_servos):
    from blooglyblob.hardware import servo_controller

    arm = servo_controller.ArmServo(12, servo_controller.LEFT_ARM, "Left")
    assert arm._servo.pin_factory.pin_class is servo_controller._ServoSignalPin
    arm.cleanup()


def test_servo_pin_release_enables_pull_down_before_becoming_input():
    from blooglyblob.hardware import servo_controller

    events = []

    class Pin:
        _number = 12
        GPIO_PULL_UPS = {"down": 1}
        factory = Mock()

        def __setattr__(self, name, value):
            events.append((name, value))
            object.__setattr__(self, name, value)

    pin = Pin()
    pin.factory.connection.set_pull_up_down.side_effect = lambda gpio, pull: (
        events.append(("pull_down", gpio, pull))
    )
    servo_controller._ServoSignalPin.close(pin)
    assert events == [
        ("frequency", None),
        ("when_changed", None),
        ("pull_down", 12, 1),
        ("function", "input"),
        ("pull", "down"),
    ]
    # Closing the owning factory closes the pin again; it must stay low.
    servo_controller._ServoSignalPin.close(pin)
    assert events[5:] == events[:5]
    pin.factory.connection = None
    servo_controller._ServoSignalPin.close(pin)
    assert len(events) == 10
