"""Ambient animation system for Blooglyblob.

Provides subtle, automatic servo movements while speaking:
- Head turns and gestures while talking
- Arms move with punctuated gestures (not continuous oscillation)
- Brief pause smoothing and one relaxed return after speech
- No ambient continuation after playback retirement or during sleep/dance/alerts
"""

import random
import threading
import time
from typing import TYPE_CHECKING

from blooglyblob.hardware.conversation_state import ConversationMode

if TYPE_CHECKING:
    from blooglyblob.audio.presentation import OutputPresentation
    from blooglyblob.hardware.servo_controller import ServoController
    from blooglyblob.hardware.conversation_state import ConversationState


def lerp(current: float, target: float, factor: float) -> float:
    """Linear interpolation with easing."""
    return current + (target - current) * factor


class AmbientAnimator:
    """Background animator for subtle, automatic servo movements.

    Runs in a background thread (like LEDController), polling conversation
    state and applying mode-appropriate movements. Respects animation_lock
    to avoid conflicting with explicit LLM-triggered animations.
    """

    # Frame rate and timing
    FRAME_RATE = 20  # FPS
    FRAME_TIME = 1.0 / FRAME_RATE  # 50ms per frame

    SPEECH_FLOOR = 0.01
    PAUSE_GRACE = 0.250
    RELAX_DURATION = 0.600

    # Movement thresholds
    MIN_DELTA = 0.01  # Don't update if change is smaller than this (head)
    MIN_ARM_DELTA = 0.5  # Arm threshold in percent (lower than MIN_DELTA*100=1.0)
    LERP_FACTOR = 0.15  # Base interpolation speed

    # SPEAKING mode settings
    SPEAKING_HEAD_RANGE = 0.5  # Head turn range while speaking
    SPEAKING_HEAD_TURN_CHANCE = 0.02  # Per-frame chance of head turn
    SPEAKING_ARM_BASE = 15  # Base arm position while speaking (slightly raised)
    SPEAKING_ARM_GESTURE_MIN = 25  # Min gesture height
    SPEAKING_ARM_GESTURE_MAX = 50  # Max gesture height
    SPEAKING_GESTURE_CHANCE = 0.025  # Per-frame chance per arm (~every 2s at 20fps)
    SPEAKING_ARM_RETURN_SPEED = 0.03  # How fast arms drift back to base

    def __init__(
        self,
        servo_controller: "ServoController",
        conversation_state: "ConversationState",
        animation_lock: threading.Lock,
        output: "OutputPresentation",
    ):
        """Initialize the ambient animator.

        Args:
            servo_controller: Controller for head and arm servos
            conversation_state: Shared conversation mode
            animation_lock: Shared ownership lock for each ambient frame and gesture
            output: Successful speaker writes shared with the lights
        """
        self._servo_controller = servo_controller
        self._conversation_state = conversation_state
        self._animation_lock = animation_lock
        self._output = output

        # Internal position tracking (for smooth interpolation)
        self._head_target = 0.0
        self._head_current = 0.0
        self._left_arm_target = 0.0
        self._left_arm_current = 0.0
        self._right_arm_target = 0.0
        self._right_arm_current = 0.0

        # Track if LLM animation was running (to resync after)
        self._was_locked = False
        self._last_positions = None

        self._speech_owner = None
        self._last_speech = None
        self._speech_axes = (False, False)
        self._relaxation = None

        # Hold timers - don't move until this time (set by LLM tool calls)
        self._head_hold_until = 0.0
        self._arms_hold_until = 0.0

        # Thread control
        self._running = False
        self._thread = None

    def start(self):
        """Start the background animation thread."""
        if self._running:
            return

        # Sync initial positions from servos
        self._sync_from_servos()

        self._running = True
        self._thread = threading.Thread(target=self._guarded_loop, name="ambient-motion", daemon=True)
        self._thread.start()
        print("  Ambient animator started!")

    def stop(self):
        """Stop the animation thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            if self._thread.is_alive():
                raise RuntimeError("Hardware worker release not confirmed")
        print("  Ambient animator stopped")

    def hold_head(self, duration: float = 5.0):
        """Prevent ambient head movement for a duration (seconds).

        Called after LLM moveHead tool to keep head in requested position.
        """
        self._clear_speech()
        self._head_hold_until = time.monotonic() + duration

    def hold_arms(self, duration: float = 5.0):
        """Prevent ambient arm movement for a duration (seconds)."""
        self._clear_speech()
        self._arms_hold_until = time.monotonic() + duration

    def hold_all(self, duration: float = 5.0):
        """Prevent all ambient movement for a duration (seconds).

        Called after LLM playAnimation to keep body in final position.
        """
        self._clear_speech()
        until = time.monotonic() + duration
        self._head_hold_until = self._arms_hold_until = until

    def _sync_from_servos(self):
        """Sync internal state from actual servo positions.

        Called after LLM animations finish to ensure smooth continuation.
        """
        sc = self._servo_controller
        if sc is None:
            return

        # Read current positions
        self._head_current = sc.head.position
        self._head_target = self._head_current

        # Convert arm positions to percent (0=down, 100=up)
        self._left_arm_current = sc.left_arm.profile.percent_at(sc.left_arm.position)
        self._left_arm_target = self._left_arm_current

        self._right_arm_current = sc.right_arm.profile.percent_at(sc.right_arm.position)
        self._right_arm_target = self._right_arm_current
        self._last_positions = self._positions()

    def _positions(self):
        sc = self._servo_controller
        if sc is None:
            return None
        return sc.head.position, sc.left_arm.position, sc.right_arm.position

    def _guarded_loop(self):
        try:
            self._animation_loop()
        except Exception:
            self._running = False
            callback = getattr(self, 'on_failure', None)
            if callback:
                callback('ambient_worker_failed')
            else:
                print('ambient_worker_failed')

    def _animation_loop(self):
        """Main animation loop running in background thread."""
        while self._running:
            start = time.monotonic()

            # Own the lock through the write, not just an earlier observation.
            if not self._animation_lock.acquire(blocking=False):
                self._was_locked = True
                self._clear_speech()
            else:
                try:
                    # A short gesture can start and finish between our frames.
                    if self._was_locked or self._positions() != self._last_positions:
                        self._clear_speech()
                        self._sync_from_servos()
                    self._was_locked = False
                    self._update()
                    self._last_positions = self._positions()
                finally:
                    self._animation_lock.release()

            # Maintain frame rate
            elapsed = time.monotonic() - start
            if elapsed < self.FRAME_TIME:
                time.sleep(self.FRAME_TIME - elapsed)

    def _clear_speech(self):
        """Discard continuation; explicit motion owns any repositioning."""
        self._last_speech = self._relaxation = None
        self._speech_axes = (False, False)

    def _update(self):
        """Observe committed speech without influencing audio or capture."""
        now = time.monotonic()
        sample = self._output.sample(now)
        if sample.owner is not self._speech_owner:
            self._clear_speech()
            self._sync_from_servos()
            self._speech_owner = sample.owner
        if sample.owner is None or self._conversation_state.mode not in {
            ConversationMode.SPEAKING, ConversationMode.LISTENING
        }:
            self._clear_speech()
            return

        if sample.kind == "speech" and sample.level >= self.SPEECH_FLOOR:
            self._last_speech = now
            self._relaxation = None
            self._speech_axes = (now >= self._head_hold_until, now >= self._arms_hold_until)
            self._update_speaking()
            self._apply_movements()
        elif self._last_speech is not None:
            if now - self._last_speech < self.PAUSE_GRACE:
                # Continue the current target, but make no new random decisions.
                self._apply_movements(*self._speech_axes)
            else:
                self._relax(now)

    def _relax(self, now):
        if self._relaxation is None:
            start = self._last_speech + self.PAUSE_GRACE
            if now >= start + self.RELAX_DURATION:
                # A stalled worker must not replay expired motion.
                self._clear_speech()
                self._sync_from_servos()
                return
            self._relaxation = (start, self._head_current, self._left_arm_current, self._right_arm_current)
        start, head, left, right = self._relaxation
        fraction = min(1.0, (now - start) / self.RELAX_DURATION)
        ease = fraction * fraction * (3 - 2 * fraction)
        self._write_positions(
            lerp(head, 0.0, ease),
            lerp(left, self.SPEAKING_ARM_BASE, ease),
            lerp(right, self.SPEAKING_ARM_BASE, ease),
            *self._speech_axes, final=fraction == 1.0,
        )
        if fraction == 1.0:
            self._clear_speech()
            self._sync_from_servos()

    def _update_speaking(self):
        """SPEAKING mode: Natural gesturing while talking.

        Both arms independently gesture from a raised speaking posture.
        Movements are gradual and fluid, not snapping up/down.
        """
        # Each arm independently has a chance to gesture (unless held by LLM animation)
        if time.monotonic() >= self._arms_hold_until:
            # Left arm
            if random.random() < self.SPEAKING_GESTURE_CHANCE:
                # New gesture - random height
                self._left_arm_target = random.uniform(
                    self.SPEAKING_ARM_GESTURE_MIN, self.SPEAKING_ARM_GESTURE_MAX
                )
            else:
                # Gradually drift back toward base speaking posture
                self._left_arm_target = lerp(
                    self._left_arm_target, self.SPEAKING_ARM_BASE, self.SPEAKING_ARM_RETURN_SPEED
                )

            # Right arm
            if random.random() < self.SPEAKING_GESTURE_CHANCE:
                self._right_arm_target = random.uniform(
                    self.SPEAKING_ARM_GESTURE_MIN, self.SPEAKING_ARM_GESTURE_MAX
                )
            else:
                self._right_arm_target = lerp(
                    self._right_arm_target, self.SPEAKING_ARM_BASE, self.SPEAKING_ARM_RETURN_SPEED
            )

        # Occasional head turns while speaking (unless held by LLM moveHead)
        if time.monotonic() < self._head_hold_until:
            # Head is held in LLM-requested position, don't move it
            pass
        elif random.random() < self.SPEAKING_HEAD_TURN_CHANCE:
            self._head_target = random.uniform(
                -self.SPEAKING_HEAD_RANGE, self.SPEAKING_HEAD_RANGE
            )
        else:
            # Slow drift back toward center
            self._head_target = lerp(self._head_target, 0, 0.02)

    def _apply_movements(self, head=True, arms=True):
        """Apply interpolated movements to servos."""
        # Calculate speed-varied lerp factor
        # Faster for arm gestures, slower for head returns
        head_lerp = self.LERP_FACTOR
        arm_lerp = self.LERP_FACTOR

        # Ease head movements more
        if abs(self._head_target - self._head_current) > 0.1:
            head_lerp *= 0.7  # Slower for larger movements

        self._write_positions(
            lerp(self._head_current, self._head_target, head_lerp),
            lerp(self._left_arm_current, self._left_arm_target, arm_lerp),
            lerp(self._right_arm_current, self._right_arm_target, arm_lerp),
            head, arms,
        )

    def _write_positions(self, new_head, new_left, new_right, head=True, arms=True, *, final=False):
        now = time.monotonic()
        sc = self._servo_controller
        if sc is None:
            return
        head_delta = abs(new_head - self._head_current)
        if head and now >= self._head_hold_until and head_delta > (0 if final else self.MIN_DELTA):
            self._head_current = new_head
            sc.head.position = new_head
        for side, value in (("left", new_left), ("right", new_right)):
            current = getattr(self, f"_{side}_arm_current")
            if arms and now >= self._arms_hold_until and abs(value - current) > (0 if final else self.MIN_ARM_DELTA):
                setattr(self, f"_{side}_arm_current", value)
                servo = getattr(sc, f"{side}_arm")
                servo.position = servo.profile.at_percent(value)
