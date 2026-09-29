"""Bounded, paced finite speech; speaker completion belongs to the caller."""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable

from blooglyblob.audio.stream import PCMPacer
from blooglyblob.ai.voice_profile import default_speech_voice, speech_instructions

_BYTES_PER_SECOND = 48000
_FRAME_BYTES = 960


class SpeechError(RuntimeError):
    """Finite speech could not be fully delivered to the audio callback."""


class SpeechTimeout(SpeechError):
    """The entire generation and delivery deadline expired."""


class OpenAISpeech:
    """Use the shared API client without owning its lifetime or device playback.

    A successful return means PCM was delivered to ``on_audio``. The caller must
    still end its audio generation and await the audio controller's physical drain before
    treating the announcement as heard or starting a hardware action.
    """

    def __init__(
        self,
        *,
        client,
        model: str = "gpt-4o-mini-tts",
        voice: str | None = None,
        instructions: str | None = None,
        timeout_seconds: float = 45,
        max_audio_seconds: float = 30,
        max_input_chars: int = 1000,
    ):
        for value in (timeout_seconds, max_audio_seconds):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError("Speech time limits must be finite and positive")
        if (
            isinstance(max_input_chars, bool)
            or not isinstance(max_input_chars, int)
            or not 1 <= max_input_chars <= 4096
        ):
            raise ValueError("Speech input limit must be an integer from 1 to 4096")
        self.client = client
        self.model = model
        self.voice = default_speech_voice() if voice is None else voice
        self.instructions = (
            speech_instructions() if instructions is None else instructions
        )
        self.timeout_seconds = timeout_seconds
        self.max_audio_bytes = int(max_audio_seconds * 24000) * 2
        self.max_input_chars = max_input_chars
        self._prepared: tuple[str, float, tuple[bytes, ...]] | None = None

    async def prepare(self, text: str, *, speed: float = 1.0) -> None:
        """Keep one bounded greeting in application memory for immediate replay."""
        frames: list[bytes] = []

        async def collect(pcm):
            frames.append(pcm)

        await self.speak(text, collect, speed=speed)
        self._prepared = (text, speed, tuple(frames))

    async def _replay(self, frames, on_audio):
        pacer = PCMPacer()
        total = 0
        for frame in frames:
            await pacer.wait(len(frame) / _BYTES_PER_SECOND)
            await on_audio(frame)
            total += len(frame)
        return total / _BYTES_PER_SECOND

    async def speak(
        self,
        text: str,
        on_audio: Callable[[bytes], Awaitable[None]],
        *,
        speed: float = 1.0,
    ) -> float:
        """Stream mono 24 kHz PCM16LE and return delivered audio seconds.

        Cancellation propagates and exits the provider streaming context. There
        are no retries, local speech fallback, hardware actions, or physical playback completion.
        """
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > self.max_input_chars
        ):
            raise ValueError("Speech text must be nonempty and within the input limit")
        if (
            type(speed) not in (int, float)
            or not math.isfinite(speed)
            or not 0.25 <= speed <= 4
        ):
            raise ValueError("Speech speed must be between 0.25 and 4.0")
        try:
            if self._prepared is not None and self._prepared[:2] == (text, speed):
                return await asyncio.wait_for(
                    self._replay(self._prepared[2], on_audio), self.timeout_seconds
                )
            return await asyncio.wait_for(
                self._stream(text, on_audio, speed=speed), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            raise SpeechTimeout("Finite speech exceeded its deadline") from None
        except SpeechError:
            raise
        except Exception:  # noqa: BLE001 - provider/callback failures cross a public boundary
            raise SpeechError("Finite speech delivery failed") from None

    async def _stream(self, text, on_audio, *, speed=1.0):
        pending = bytearray()
        received = 0
        pacer = PCMPacer()
        async with self.client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=self.voice,
            input=text,
            instructions=self.instructions,
            response_format="pcm",
            stream_format="audio",
            speed=speed,
            timeout=self.timeout_seconds,
        ) as response:
            async for chunk in response.iter_bytes(chunk_size=_FRAME_BYTES):
                if not isinstance(chunk, bytes):
                    raise SpeechError("Finite speech returned invalid PCM")
                received += len(chunk)
                if received > self.max_audio_bytes:
                    raise SpeechError("Finite speech exceeded its audio duration limit")
                pending.extend(chunk)
                while len(pending) >= _FRAME_BYTES:
                    frame = bytes(pending[:_FRAME_BYTES])
                    del pending[:_FRAME_BYTES]
                    await pacer.wait(0.02)
                    await on_audio(frame)
            if not received or len(pending) % 2:
                raise SpeechError("Finite speech returned empty or incomplete PCM")
            if pending:
                await pacer.wait(len(pending) / _BYTES_PER_SECOND)
                await on_audio(bytes(pending))
        return received / _BYTES_PER_SECOND
