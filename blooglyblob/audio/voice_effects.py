"""Streaming voice coloration for Live and finite speech."""

import math
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray


class RingModulator:
    """Blend dry speech with a carrier-modulated copy of 24 kHz PCM16LE.

    Oscillator position persists across packets. A new instance starts each
    playback generation, so cancellation leaves no buffered audio or effect tail.
    The convex mix never amplifies a sample beyond its original magnitude.
    """

    SAMPLE_RATE = 24000

    def __init__(self, *, mix=0.0, carrier_hz=70):
        if (
            type(mix) not in (int, float)
            or not math.isfinite(mix)
            or not 0 <= mix <= 1
            or type(carrier_hz) is not int
            or not 1 <= carrier_hz <= 400
        ):
            raise ValueError(
                "Invalid voice effect: mix must be 0..1, carrier_hz 1..400"
            )
        self.mix = mix
        period = self.SAMPLE_RATE // math.gcd(self.SAMPLE_RATE, carrier_hz)
        self._gain = np.empty(0)
        if mix:
            self._gain = (
                1
                - mix
                + mix
                * np.cos(2 * np.pi * carrier_hz * np.arange(period) / self.SAMPLE_RATE)
            )
        self._position = 0
        self._finished = False

    def process(self, pcm: bytes) -> bytes:
        if self._finished:
            raise ValueError("Voice output generation has already finished")
        if not isinstance(pcm, bytes) or len(pcm) % 2:
            raise ValueError("Voice effect requires complete PCM16LE samples")
        if not self.mix or not pcm:
            return pcm
        samples: NDArray[np.int16] = np.frombuffer(pcm, dtype="<i2")
        positions = (np.arange(len(samples)) + self._position) % len(self._gain)
        output = np.clip(
            np.rint(samples * self._gain[positions]), -32768, 32767
        ).astype("<i2")
        self._position = (self._position + len(samples)) % len(self._gain)
        return output.tobytes()

    def finish(self) -> None:
        """Retire this generation; sample-wise coloration has no buffered tail."""
        self._finished = True
