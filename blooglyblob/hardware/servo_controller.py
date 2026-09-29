"""High-level servo controller for Blooglyblob.

Provides semantic control of servos using fixed positions:
- ArmServo: up(), down(), wave(), set_percent()
- HeadServo: look_left(), look_right(), center(), shake_no(), nod_yes()
- ServoController: Unified control of all servos with preset animations

All movements are smooth by default and respect the fixed operating window.
Fit parts with `make pi-servo-fit` before checking assembled clearance.
"""

from contextlib import contextmanager
import signal
import threading
import time
from typing import Optional

# Only import GPIO libraries when running on Pi
try:
    from gpiozero import Servo
    from gpiozero.pins.pigpio import PiGPIOFactory
    ON_PI = True
except ImportError:
    ON_PI = False
    Servo = None

from blooglyblob.hardware.config import gpio_config
from blooglyblob.hardware.local_media import HardwareReleaseError
from blooglyblob.hardware.servo_config import (
    LEFT_ARM, RIGHT_ARM, HEAD, ServoProfile,
    MIN_PULSE_WIDTH, MAX_PULSE_WIDTH, FRAME_WIDTH,
)

# Default movement settings
DEFAULT_STEP = 0.02
DEFAULT_DELAY = 0.015  # 15ms between steps for smooth movement


@contextmanager
def _protect_release():
    """Let main-thread teardown finish before restoring interrupt handlers."""
    handlers = {}
    try:
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
                handlers[sig] = signal.signal(sig, signal.SIG_IGN)
        yield
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def _create_servo(pin: int) -> Optional["Servo"]:
    """Create a gpiozero Servo with pigpio backend."""
    if not ON_PI:
        return None

    factory = None
    try:
        factory = PiGPIOFactory()
        return Servo(
            pin,
            initial_value=None,
            min_pulse_width=MIN_PULSE_WIDTH,
            max_pulse_width=MAX_PULSE_WIDTH,
            frame_width=FRAME_WIDTH,
            pin_factory=factory,
        )
    except BaseException as error:
        if factory is not None:
            try:
                with _protect_release():
                    factory.close()
            except Exception:
                raise HardwareReleaseError("Servo factory release failed") from None
        if not isinstance(error, Exception):
            raise
        print(f"Failed to create servo on GPIO {pin}")
        return None


class BaseServo:
    """Base class for servo control with smooth movement."""

    def __init__(self, pin: int, profile: ServoProfile, name: str):
        self.pin = pin
        self.profile = profile
        self.name = name
        self._servo = _create_servo(pin)
        if ON_PI and self._servo is None:
            raise RuntimeError(f"Servo output unavailable on GPIO {pin}")
        self._position = profile.rest

        # Don't move on individual servo init - ServoController.fit_pose() handles startup position

    @property
    def position(self) -> float:
        """Current position (-1.0 to 1.0)."""
        return self._position

    @position.setter
    def position(self, value: float):
        """Set position immediately (no smoothing)."""
        value = self.profile.clamp(value)
        self._position = value
        if self._servo:
            self._servo.value = value

    def move_to(self, target: float, speed: float = 1.0):
        """Move smoothly to target position.

        Args:
            target: Target position (-1.0 to 1.0)
            speed: Movement speed multiplier (0.5 = half speed, 2.0 = double)
        """
        target = self.profile.clamp(target)

        if self._servo is None:
            self._position = target
            return

        step = DEFAULT_STEP * speed
        delay = DEFAULT_DELAY / speed

        current = self._position
        direction = 1 if target > current else -1

        while abs(current - target) > step:
            current += step * direction
            self._servo.value = current
            time.sleep(delay)

        self._servo.value = target
        self._position = target

    def neutral(self, speed: float = 1.0):
        """Return to the fixed rest position."""
        self.move_to(self.profile.rest, speed)

    def detach(self):
        """Stop sending PWM signal (servo goes limp)."""
        if self._servo:
            self._servo.detach()

    def cleanup(self):
        """Close the servo and its owned pigpio connection, observing failures."""
        if self._servo:
            servo = self._servo
            errors = []
            for close in (servo.detach, servo.close, servo.pin_factory.close):
                try:
                    close()
                except Exception:
                    errors.append('close')
            if errors:
                raise HardwareReleaseError('Servo release failed')
            self._servo = None


class ArmServo(BaseServo):
    """Arm servo with semantic up/down control."""

    def up(self, speed: float = 1.0):
        """Raise arm to fixed 'up' position."""
        self.move_to(self.profile.end, speed)

    def down(self, speed: float = 1.0):
        """Lower arm to fixed 'down' position."""
        self.move_to(self.profile.start, speed)

    def set_percent(self, percent: float, speed: float = 1.0):
        """Set arm position as percentage (0=down, 100=up).

        Args:
            percent: Position from 0 (down) to 100 (up)
            speed: Movement speed multiplier
        """
        self.move_to(self.profile.at_percent(percent), speed)

    def wave(self, cycles: int = 2, speed: float = 1.5):
        """Wave the arm up and down.

        Args:
            cycles: Number of wave cycles
            speed: Movement speed multiplier
        """
        for _ in range(cycles):
            self.up(speed)
            time.sleep(0.1)
            self.down(speed)
            time.sleep(0.1)

        self.neutral(speed)


class HeadServo(BaseServo):
    """Head servo with semantic look left/right control."""

    def look_left(self, speed: float = 1.0):
        """Turn head to fixed 'left' position."""
        self.move_to(self.profile.start, speed)

    def look_right(self, speed: float = 1.0):
        """Turn head to fixed 'right' position."""
        self.move_to(self.profile.end, speed)

    def center(self, speed: float = 1.0):
        """Center head (alias for neutral)."""
        self.neutral(speed)

    def shake_no(self, cycles: int = 2, speed: float = 2.0):
        """Shake head side to side (saying 'no').

        Args:
            cycles: Number of shake cycles
            speed: Movement speed multiplier
        """
        # Use partial range for quick shake
        left = self.profile.start * 0.6
        right = self.profile.end * 0.6

        for _ in range(cycles):
            self.move_to(left, speed)
            time.sleep(0.05)
            self.move_to(right, speed)
            time.sleep(0.05)

        self.center(speed)

    def nod_yes(self, cycles: int = 2, speed: float = 2.0):
        """Nod head (simulate 'yes' with slight movements).

        Note: This is limited since the head servo only swivels left/right.
        This creates a subtle forward motion effect by centering quickly.

        Args:
            cycles: Number of nod cycles
            speed: Movement speed multiplier
        """
        # Subtle movement to simulate nod
        for _ in range(cycles):
            self.move_to(self.profile.rest - 0.1, speed)
            time.sleep(0.1)
            self.move_to(self.profile.rest + 0.1, speed)
            time.sleep(0.1)

        self.center(speed)


class ServoController:
    """Unified controller for all Blooglyblob servos.

    Provides:
    - Individual servo access: left_arm, right_arm, head
    - Preset animations: wave_hello(), celebrate(), etc.
    """

    def __init__(self):
        """Open inactive outputs, then command each fixed rest position once."""
        try:
            self.left_arm = ArmServo(
                gpio_config.LEFT_ARM_PIN,
                LEFT_ARM,
                "Left Arm",
            )
            self.right_arm = ArmServo(
                gpio_config.RIGHT_ARM_PIN,
                RIGHT_ARM,
                "Right Arm",
            )
            self.head = HeadServo(
                gpio_config.HEAD_PIN,
                HEAD,
                "Head",
            )

            # Start in resting position (arms down, head center)
            self.fit_pose()
        except BaseException:
            # Only attributes whose constructors completed exist here. Cleanup
            # attempts each one; an unconfirmed release supersedes the startup
            # error with HardwareReleaseError so optional startup cannot hide it.
            self.cleanup()
            raise

    def fit_pose(self):
        """Command rest directly, without an assumed starting angle or sweep."""
        for servo in (self.left_arm, self.right_arm, self.head):
            servo.position = servo.profile.rest

    def all_neutral(self, speed: float = 1.0):
        """Move all servos to neutral position."""
        self.left_arm.neutral(speed)
        self.right_arm.neutral(speed)
        self.head.center(speed)

    def rest(self, speed: float = 1.0):
        """Return to resting position - arms down, head forward."""
        self.left_arm.down(speed)
        self.right_arm.down(speed)
        self.head.center(speed)

    def detach_all(self):
        """Detach all servos (emergency stop)."""
        self.left_arm.detach()
        self.right_arm.detach()
        self.head.detach()

    def cleanup(self):
        """Clean up all servo resources."""
        failed = False
        with _protect_release():
            for name in ('left_arm', 'right_arm', 'head'):
                servo = getattr(self, name, None)
                if servo is not None:
                    try:
                        servo.cleanup()
                    except Exception:
                        failed = True
        if failed:
            raise HardwareReleaseError('Servo release failed')

    # === Preset Animations ===

    def wave_hello(self, arm: str = "right"):
        """Wave hello with one arm.

        Args:
            arm: Which arm to wave ("left" or "right")
        """
        wave_arm = self.right_arm if arm == "right" else self.left_arm
        wave_arm.up(speed=1.5)
        wave_arm.wave(cycles=3, speed=2.0)
        self.rest()

    def wave_both_arms(self, cycles: int = 2):
        """Wave both arms in opposite directions."""
        for _ in range(cycles):
            # Left up, right down
            self.left_arm.up(speed=2.0)
            self.right_arm.down(speed=2.0)
            time.sleep(0.2)
            # Left down, right up
            self.left_arm.down(speed=2.0)
            self.right_arm.up(speed=2.0)
            time.sleep(0.2)

        self.all_neutral()

    def celebrate(self):
        """Celebration animation - arms up, head shake, wave."""
        # Arms up
        self.left_arm.up(speed=2.0)
        self.right_arm.up(speed=2.0)
        time.sleep(0.2)

        # Quick arm waves while shaking head
        for _ in range(3):
            self.left_arm.set_percent(70, speed=3.0)
            self.right_arm.set_percent(70, speed=3.0)
            self.head.look_left(speed=3.0)
            time.sleep(0.1)
            self.left_arm.set_percent(100, speed=3.0)
            self.right_arm.set_percent(100, speed=3.0)
            self.head.look_right(speed=3.0)
            time.sleep(0.1)

        self.rest()

    def think(self):
        """Thinking animation - head turns toward raised arm, then returns to rest."""
        self.head.look_right(speed=0.8)  # Look toward the raised arm
        self.right_arm.set_percent(60, speed=0.8)
        time.sleep(0.8)
        self.rest(speed=0.8)

    def shrug(self):
        """Shrug animation - both arms up briefly."""
        self.left_arm.up(speed=2.0)
        self.right_arm.up(speed=2.0)
        time.sleep(0.3)
        self.rest(speed=1.5)

    def attention(self):
        """Get attention - quick movements to alert."""
        self.head.shake_no(cycles=1, speed=3.0)
        self.left_arm.wave(cycles=1, speed=3.0)

    def sleep_pose(self):
        """Go to sleep pose - arms down, head center."""
        self.left_arm.down(speed=0.5)
        self.right_arm.down(speed=0.5)
        self.head.center(speed=0.5)

    def six_seven(self, cycles: int = 3):
        """6-7 gesture - the viral Gen Alpha 'weighing options' motion.

        Both arms at mid-level, alternating up and down like weighing
        two choices. Often used to express ambivalence or 'so-so'.

        Args:
            cycles: Number of alternating cycles
        """
        # Start with both arms at mid position
        self.left_arm.set_percent(50, speed=2.0)
        self.right_arm.set_percent(50, speed=2.0)
        time.sleep(0.15)

        # Alternate arms up and down (the weighing motion)
        for _ in range(cycles):
            # Left up, right down
            self.left_arm.set_percent(75, speed=2.5)
            self.right_arm.set_percent(25, speed=2.5)
            time.sleep(0.2)
            # Left down, right up
            self.left_arm.set_percent(25, speed=2.5)
            self.right_arm.set_percent(75, speed=2.5)
            time.sleep(0.2)

        # Return to rest
        self.rest(speed=1.5)


# Convenience function for quick access
def get_controller() -> ServoController:
    """Get a new ServoController instance."""
    return ServoController()
