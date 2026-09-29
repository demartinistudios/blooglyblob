"""In-memory scanner loop mixed into the device's existing 48 kHz output.

The audio writer owns this object. It supplies speech (or silence while idle),
and serializes mix/stop calls; this component opens no devices or threads.
"""

from pathlib import Path
import wave

import numpy as np

from .resampler import DEVICE_SAMPLE_RATE, PCMResampler


class BackgroundSound:
    """A quiet looping effect with speech ducking and click-free fades."""

    _NORMAL_GAIN = 0.12
    _DUCK_GAIN = 0.018
    _VOICE_RMS = 160  # About -46 dBFS; digital silence must not trigger ducking.
    _ATTACK = round(0.020 * DEVICE_SAMPLE_RATE)
    _HOLD = round(0.200 * DEVICE_SAMPLE_RATE)
    _RELEASE = round(0.350 * DEVICE_SAMPLE_RATE)
    _START = round(0.100 * DEVICE_SAMPLE_RATE)
    _STOP = round(0.040 * DEVICE_SAMPLE_RATE)
    _MAX_SECONDS = 60

    def __init__(self, pcm: bytes):
        if (
            not pcm
            or len(pcm) % 2
            or len(pcm) > self._MAX_SECONDS * DEVICE_SAMPLE_RATE * 2
        ):
            raise ValueError(
                "Background sound must be nonempty mono PCM16, at most 60 seconds"
            )
        self._clip = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
        self._clip.setflags(write=False)
        self._reset_playback()

    def _reset_playback(self) -> None:
        self._position = 0
        self._gain = self._NORMAL_GAIN
        self._hold = 0
        self._started = 0
        self._stop_remaining: int | None = None
        self._stop_gain = 0.0

    def fresh(self) -> "BackgroundSound":
        """Start independent playback using the already loaded, read-only clip."""
        playback = object.__new__(type(self))
        playback._clip = self._clip
        playback._reset_playback()
        return playback

    @classmethod
    def from_wav(cls, path: str | Path) -> "BackgroundSound":
        """Validate and load a bounded PCM recording, converting it once."""
        try:
            with wave.open(str(path), "rb") as source:
                rate, count = source.getframerate(), source.getnframes()
                if (
                    source.getnchannels() != 1
                    or source.getsampwidth() != 2
                    or source.getcomptype() != "NONE"
                    or not 0 < rate <= 192000
                    or not 0 < count <= rate * cls._MAX_SECONDS
                ):
                    raise ValueError(
                        "Background WAV must be mono PCM16 and 0–60 seconds"
                    )
                pcm = source.readframes(count)
                if len(pcm) != count * 2:
                    raise ValueError("Background WAV is truncated")
        except (wave.Error, EOFError) as exc:
            raise ValueError("Invalid background WAV") from exc
        return cls(PCMResampler(rate, DEVICE_SAMPLE_RATE).process(pcm, last=True))

    @property
    def finished(self) -> bool:
        return self._stop_remaining == 0

    def stop(self) -> None:
        """Request a short fade; repeated stop requests do not extend it."""
        if self._stop_remaining is None:
            self._stop_remaining = self._STOP
            self._stop_gain = self._gain * min(self._started / self._START, 1)

    def _envelope(self, count: int, target: float) -> np.ndarray:
        distance = self._NORMAL_GAIN - self._DUCK_GAIN
        step = distance / (self._ATTACK if target < self._gain else self._RELEASE)
        change = np.minimum(np.arange(1, count + 1) * step, abs(target - self._gain))
        gains = self._gain + np.sign(target - self._gain) * change
        if count:
            self._gain = float(gains[-1])
        return gains

    def mix(self, voice_pcm: bytes) -> bytes:
        """Add the effect without attenuating speech or overflowing PCM16."""
        if len(voice_pcm) % 2:
            raise ValueError("Voice must contain complete PCM16 samples")
        if not voice_pcm or self.finished:
            return voice_pcm
        voice = np.frombuffer(voice_pcm, dtype="<i2").astype(np.float64)
        count = len(voice)
        indices = np.arange(count)
        if self._stop_remaining is not None:
            gains = (
                self._stop_gain
                * np.maximum(self._stop_remaining - indices - 1, 0)
                / self._STOP
            )
            self._stop_remaining = max(0, self._stop_remaining - count)
        else:
            if np.mean(voice * voice) >= self._VOICE_RMS**2:
                self._hold = self._HOLD
                gains = self._envelope(count, self._DUCK_GAIN)
            else:
                held = min(count, self._hold)
                self._hold -= held
                gains = np.concatenate(
                    (
                        self._envelope(held, self._DUCK_GAIN),
                        self._envelope(count - held, self._NORMAL_GAIN),
                    )
                )
            gains *= np.minimum((self._started + indices + 1) / self._START, 1)
            self._started = min(self._START, self._started + count)
        effect = self._clip[(self._position + indices) % len(self._clip)] * gains
        self._position = (self._position + count) % len(self._clip)
        # Only the added effect is limited: speech is never scaled or clipped.
        effect = np.clip(np.rint(effect), -32768 - voice, 32767 - voice)
        return (voice + effect).astype("<i2").tobytes()
