"""Pure three-zone lighting, independent of servo state and physical drivers."""

from colorsys import hsv_to_rgb
from dataclasses import dataclass
import math
import random
import threading
import time

from blooglyblob.audio.presentation import OutputPresentation, OutputSample

RGB = tuple[int, int, int]
BLACK = (0, 0, 0)
EYE_COLOR = (255, 185, 75)
SPEECH_COLORS = ((183, 161, 245), (195, 148, 227), (231, 164, 198), (247, 187, 141))
MUSIC_COLORS = (
    (4, 239, 168),
    (0, 187, 255),
    (57, 77, 255),
    (137, 11, 255),
    (217, 0, 218),
    (255, 31, 124),
    (255, 114, 8),
    (255, 208, 28),
)
MODES = {
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
}
BLINK_MODES = {"listening", "waiting", "speaking", "dancing", "goodbye"}


class _EyeBlink:
    """One paired blink schedule, sampled by the existing LED writer."""

    def __init__(self, rng):
        self._rng = rng
        self.reset()

    def reset(self):
        self._next = self._double = None
        self._start = -math.inf
        self._duration = 0.25

    def sample(self, now):
        if self._next is None:
            self._next = now + self._rng.uniform(3.4, 8.6)
        elif now >= self._next:
            # Start one new blink after a missed frame, never replay a backlog.
            self._start = now
            self._duration = self._rng.uniform(0.225, 0.290)
            self._next = now + self._rng.uniform(3.4, 8.6)
            self._double = (
                now + self._duration + 0.13 if self._rng.random() < 0.1 else None
            )
        if self._double is not None and now >= self._double:
            self._start, self._duration = self._double, 0.21
            self._double = None
        elapsed = now - self._start
        if elapsed < 0.055:
            x = max(0.0, elapsed / 0.055)
            return 1 - x * x * (3 - 2 * x)
        if elapsed < 0.09:
            return 0.0
        x = min(1.0, (elapsed - 0.09) / (self._duration - 0.09))
        return x * x * (3 - 2 * x)


@dataclass(frozen=True)
class LightingSnapshot:
    mode: str
    previous: str
    changed: float
    output: OutputSample
    music: tuple[float, ...] = ()
    eye_openness: float = 1.0
    eye_gain: float = 1.0


class LightingState:
    """One locked snapshot for LEDs; contains no control or servo authority."""

    def __init__(self, output=None, *, rng=None):
        self.output = output if output is not None else OutputPresentation()
        self._lock = threading.Lock()
        self._mode = self._previous = "sleeping"
        self._changed = time.monotonic()
        self._pending = set()
        self._music = None
        self._stopped = False
        self._unavailable = False
        self._eye_wake_started = None
        self._blink = _EyeBlink(rng if rng is not None else random.Random())

    def set_mode(self, mode, *, now=None):
        if mode not in MODES:
            raise ValueError("Unknown lighting mode")
        with self._lock:
            if self._stopped or (self._mode == "fault" and mode != "stopped"):
                return
            if mode != self._mode:
                self._previous, self._mode = self._mode, mode
                self._changed = time.monotonic() if now is None else now
                if mode == "waking":
                    self._eye_wake_started = self._changed
            if mode in {"sleeping", "stopped", "fault"}:
                self._eye_wake_started = None
            if mode in {"sleeping", "stopped"}:
                self._pending.clear()
            if mode not in BLINK_MODES:
                self._blink.reset()
            if mode == "stopped":
                self._stopped = True

    def set_unavailable(self, unavailable):
        with self._lock:
            self._unavailable = unavailable
            self._eye_wake_started = None
            self._pending.clear()
            self._blink.reset()
            if self._mode not in {"fault", "stopped"}:
                self._previous = self._mode = "sleeping"
                self._changed = time.monotonic()

    def pending(self, identity, active):
        with self._lock:
            if not self._stopped and identity is not None:
                if active:
                    self._pending.add(identity)
                else:
                    self._pending.discard(identity)

    def music(self, analysis):
        with self._lock:
            self._music = analysis

    def stop(self):
        with self._lock:
            self._stopped = True
            self._mode = "stopped"
            self._eye_wake_started = None
            self._pending.clear()
            self._music = None
            self._blink.reset()

    def snapshot(self, now):
        with self._lock:
            mode = self._mode
            if self._unavailable and mode not in {"fault", "stopped"}:
                mode = "unavailable"
            if mode == "waking" and now - self._changed >= 0.6:
                mode = "listening"
            if mode == "listening" and self._pending:
                mode = "waiting"
            output = self.output.sample(now)
            drives = ()
            if mode == "dancing" and output.kind == "music" and self._music is not None:
                drives = self._music.at(output.position)
            openness = self._blink.sample(now) if mode in BLINK_MODES else 1.0
            # A quick connection must not cut the button's eye fade short.
            gain = (
                1.0 if self._eye_wake_started is None else
                min(1.0, max(0.0, (now - self._eye_wake_started) / 0.6))
            )
            return LightingSnapshot(
                mode, self._previous, self._changed, output, drives, openness, gain
            )


def scale(rgb, amount):
    return tuple(round(max(0.0, min(255.0, channel * amount))) for channel in rgb)


def _body(mode, now):
    if mode == "stopped":
        return [BLACK] * 6
    if mode == "fault":
        return [(90, 24, 18)] * 6
    if mode == "unavailable":
        return [(48, 20, 0)] * 6
    if mode == "alert":
        phase = now % 2.4
        pulse = sum(
            math.exp(-(((phase - center) / 0.15) ** 2)) for center in (0.3, 0.75)
        )
        return [scale((255, 132, 20), 0.12 + 0.5 * pulse)] * 6
    if mode == "sleeping":
        return [
            scale((125, 55, 220), 0.10 + 0.025 * math.sin(now * math.tau / 8 + i * 0.4))
            for i in range(6)
        ]
    # Awake colors drift independently of voice energy, including the greeting.
    period, brightness = (36, 0.38) if mode == "dancing" else (60, 0.25)
    return [
        scale(
            tuple(c * 255 for c in hsv_to_rgb((now / period + i / 8) % 1, 0.78, 1)),
            brightness,
        )
        for i in range(6)
    ]


def render(state: LightingSnapshot, now: float) -> tuple[RGB, ...]:
    mode = state.mode
    if mode == "stopped":
        return (BLACK,) * 16
    body = _body(mode, now)
    eyes = (
        [BLACK] * 2
        if mode in {"sleeping", "unavailable"}
        else [scale(EYE_COLOR, 0.45 * state.eye_openness * state.eye_gain)] * 2
    )
    mouth = [BLACK] * 8
    # Output energy alone cannot wake the robot, escape a fault or talk over music.
    if mode not in {"sleeping", "fault", "dancing", "unavailable"} and state.output.kind == "speech":
        level = state.output.level
        if level >= 0.025:
            for i in range(4):
                amount = max(0.0, min(1.0, level * 4 - (3 - i)))
                mouth[i] = mouth[7 - i] = scale(SPEECH_COLORS[i], amount * 0.75)
    elif mode == "dancing" and state.output.kind == "music":
        mouth = (
            [
                scale(color, drive * 0.75)
                for color, drive in zip(MUSIC_COLORS, state.music)
            ]
            if state.music
            else mouth
        )
    if mode not in {"fault", "stopped", "unavailable"}:
        elapsed = max(0.0, now - state.changed)
        blend = min(1.0, elapsed / 0.6)
        previous = _body(state.previous, now)
        if mode in {"waking", "listening", "waiting", "speaking"} and state.eye_gain < 1:
            # Connection/pending changes must not snap the button's body fade.
            blend = state.eye_gain
            previous = _body("sleeping", now)
        body = [
            tuple(round(a + (b - a) * blend) for a, b in zip(old, new))
            for old, new in zip(previous, body)
        ]
    return tuple(body + eyes + mouth)
