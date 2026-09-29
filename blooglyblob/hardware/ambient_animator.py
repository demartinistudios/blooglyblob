"""Ambient animation system for Blooglyblob.

Provides subtle, automatic servo movements while speaking:
- Head turns and gestures while talking
- Arms move with punctuated gestures (not continuous oscillation)
- No movement without audible voice playback, or during sleep/dance/alerts
"""

import random
import threading
import time
from typing import TYPE_CHECKING

from blooglyblob.hardware.conversation_state import ConversationMode

if TYPE_CHECKING:
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
    ):
        """Initialize the ambient animator.

        Args:
            servo_controller: Controller for head and arm servos
            conversation_state: Shared state for mode and audio level
            animation_lock: Lock used by LLM animations (we check if locked)
        """
        self._servo_controller = servo_controller
        self._conversation_state = conversation_state
        self._animation_lock = animation_lock

        # Internal position tracking (for smooth interpolation)
        self._head_target = 0.0
        self._head_current = 0.0
        self._left_arm_target = 0.0
        self._left_arm_current = 0.0
        self._right_arm_target = 0.0
        self._right_arm_current = 0.0

        # Track if LLM animation was running (to resync after)
        self._was_locked = False

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
        self._thread = threading.Thread(target=self._guarded_loop, daemon=True)
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
        self._head_hold_until = time.time() + duration

    def hold_arms(self, duration: float = 5.0):
        """Prevent ambient arm movement for a duration (seconds)."""
        self._arms_hold_until = time.time() + duration

    def hold_all(self, duration: float = 5.0):
        """Prevent all ambient movement for a duration (seconds).

        Called after LLM playAnimation to keep body in final position.
        """
        self._head_hold_until = time.time() + duration
        self._arms_hold_until = time.time() + duration

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
            start = time.time()

            # Check if LLM animation is running
            is_locked = self._animation_lock.locked()

            if is_locked:
                # Don't interfere with LLM animations
                self._was_locked = True
            else:
                # If we just came out of a lock, resync positions
                if self._was_locked:
                    self._sync_from_servos()
                    self._was_locked = False

                # Update based on current mode
                self._update()

            # Maintain frame rate
            elapsed = time.time() - start
            if elapsed < self.FRAME_TIME:
                time.sleep(self.FRAME_TIME - elapsed)

    def _update(self):
        """Update animations based on current conversation mode."""
        mode = self._conversation_state.mode
        audio_level = self._conversation_state.audio_level

        # Duplex conversation stays in LISTENING while the speaker plays.
        # Use local playback energy, not cloud turn events or microphone input.
        if mode not in {ConversationMode.SPEAKING, ConversationMode.LISTENING} or audio_level < 0.1:
            return

        self._update_speaking(audio_level)

        # Apply interpolation and update servos
        self._apply_movements()

    def _update_speaking(self, audio_level: float):
        """SPEAKING mode: Natural gesturing while talking.

        Both arms independently gesture from a raised speaking posture.
        Movements are gradual and fluid, not snapping up/down.
        """
        # Only animate when there's actual audio (suppress during pauses)
        if audio_level < 0.1:
            return

        # Each arm independently has a chance to gesture (unless held by LLM animation)
        if time.time() >= self._arms_hold_until:
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
        if time.time() < self._head_hold_until:
            # Head is held in LLM-requested position, don't move it
            pass
        elif random.random() < self.SPEAKING_HEAD_TURN_CHANCE:
            self._head_target = random.uniform(
                -self.SPEAKING_HEAD_RANGE, self.SPEAKING_HEAD_RANGE
            )
        else:
            # Slow drift back toward center
            self._head_target = lerp(self._head_target, 0, 0.02)

    def _apply_movements(self):
        """Apply interpolated movements to servos."""
        now = time.time()
        sc = self._servo_controller
        if sc is None:
            return

        # Calculate speed-varied lerp factor
        # Faster for arm gestures, slower for head returns
        head_lerp = self.LERP_FACTOR
        arm_lerp = self.LERP_FACTOR

        # Ease head movements more
        if abs(self._head_target - self._head_current) > 0.1:
            head_lerp *= 0.7  # Slower for larger movements

        # Apply head movement
        new_head = lerp(self._head_current, self._head_target, head_lerp)
        if now >= self._head_hold_until and abs(new_head - self._head_current) > self.MIN_DELTA:
            self._head_current = new_head
            sc.head.position = self._head_current

        # Apply left arm movement
        new_left = lerp(self._left_arm_current, self._left_arm_target, arm_lerp)
        left_delta = abs(new_left - self._left_arm_current)
        if now >= self._arms_hold_until and left_delta > self.MIN_ARM_DELTA:
            self._left_arm_current = new_left
            pos = sc.left_arm.profile.at_percent(self._left_arm_current)
            sc.left_arm.position = pos

        # Apply right arm movement
        new_right = lerp(self._right_arm_current, self._right_arm_target, arm_lerp)
        right_delta = abs(new_right - self._right_arm_current)
        if now >= self._arms_hold_until and right_delta > self.MIN_ARM_DELTA:
            self._right_arm_current = new_right
            pos = sc.right_arm.profile.at_percent(self._right_arm_current)
            sc.right_arm.position = pos
