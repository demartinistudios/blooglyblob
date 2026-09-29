"""Continuous mono PCM16LE conversion at physical audio boundaries."""

import numpy as np
import soxr  # type: ignore[import-untyped]  # SoXR does not publish typing metadata.

DEVICE_SAMPLE_RATE = 48000
SPEECH_SAMPLE_RATE = 24000


class PCMResampler:
    """Keep filter state across packets; flush only when a finite stream ends.

    LQ retains the existing low-latency speech filter. Float processing avoids
    integer-output dithering, keeping output independent of packet boundaries.
    Equal rates pass through unchanged. A new physical capture or playback
    generation gets a new converter; cancellation discards its buffered tail.
    """

    def __init__(self, input_rate: int, output_rate: int):
        if input_rate <= 0 or output_rate <= 0:
            raise ValueError("Sample rates must be positive")
        self._stream = (
            soxr.ResampleStream(
                input_rate, output_rate, 1, dtype="float32", quality="LQ"
            )
            if input_rate != output_rate
            else None
        )
        self._finished = False

    def process(self, pcm: bytes, *, last: bool = False) -> bytes:
        if self._finished:
            raise RuntimeError("PCM stream is finished")
        if not isinstance(pcm, bytes) or len(pcm) % 2:
            raise ValueError("PCM must contain complete 16-bit samples")
        self._finished = last
        if self._stream is None:
            return pcm
        if not pcm and not last:
            return b""
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
        output = self._stream.resample_chunk(samples, last=last)
        return np.clip(np.rint(output), -32768, 32767).astype("<i2").tobytes()
