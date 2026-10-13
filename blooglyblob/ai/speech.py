"""Bounded, paced finite speech; speaker completion belongs to the caller."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import threading
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from pathlib import Path

from blooglyblob.ai.announcements import ANNOUNCEMENT_SLOTS, fixed_announcements
from blooglyblob.ai.voice_profile import default_speech_voice, speech_instructions
from blooglyblob.audio.stream import PCMPacer
from blooglyblob.connectivity import failure_category

_BYTES_PER_SECOND = 48000
_FRAME_BYTES = 960
_CACHE_MAGIC = b"BLOOGLY-SPEECH-1\n"
_CACHE_HEADER_BYTES = len(_CACHE_MAGIC) + 64 + 1 + 64 + 1
logger = logging.getLogger(__name__)


class SpeechError(RuntimeError):
    """Finite speech could not be fully delivered to the audio callback."""

    def __init__(self, message: str, *, category: str | None = None):
        super().__init__(message)
        self.category = category


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
        cache_dir: Path | None = None,
        announcements: dict[str, tuple[str, float]] | None = None,
        work=None,
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
        if max_audio_seconds > 30:
            raise ValueError("Speech audio limit cannot exceed 30 seconds")
        self.client = client
        self.model = model
        self.voice = default_speech_voice() if voice is None else voice
        self.instructions = (
            speech_instructions() if instructions is None else instructions
        )
        self.timeout_seconds = timeout_seconds
        self.max_audio_bytes = int(max_audio_seconds * 24000) * 2
        self.max_input_chars = max_input_chars
        self.cache_dir = Path(cache_dir) if cache_dir is not None else None
        self.announcements = dict(
            fixed_announcements() if announcements is None else announcements
        )
        if self.announcements.keys() != ANNOUNCEMENT_SLOTS:
            raise ValueError("Speech preparation requires the four registered slots")
        self._work = work or asyncio.to_thread
        self._prepared: dict[str, tuple[str, tuple[bytes, ...]]] = {}
        self._locks = {slot: asyncio.Lock() for slot in ANNOUNCEMENT_SLOTS}
        self._disk_locks = {slot: threading.Lock() for slot in ANNOUNCEMENT_SLOTS}
        self._request = 0

    async def prepare(self, text: str, *, speed: float = 1.0) -> None:
        """Prepare a registered announcement without taking speaker ownership.

        Concurrent preparation/playback shares a slot lock; different phrases
        remain independent. Only completely validated, delivered PCM is retained.
        """
        self._validate(text, speed)
        if self._slot(text, speed) is None:
            raise ValueError("Only registered announcements can be prepared")
        await self._deliver(text, None, speed=speed)

    def _slot(self, text, speed):
        return next(
            (
                slot
                for slot, phrase in self.announcements.items()
                if phrase == (text, speed)
            ),
            None,
        )

    def _fingerprint(self, text, speed):
        settings = [
            text,
            self.model,
            self.voice,
            self.instructions,
            float(speed),
            "pcm",
            "audio",
        ]
        return hashlib.sha256(
            json.dumps(settings, ensure_ascii=True).encode()
        ).hexdigest()

    def _read_slot(self, slot, fingerprint):
        assert self.cache_dir is not None
        try:
            with (self.cache_dir / f"{slot}.pcm").open("rb") as stream:
                data = stream.read(_CACHE_HEADER_BYTES + self.max_audio_bytes + 1)
        except OSError:
            return None
        if not data.startswith(_CACHE_MAGIC):
            return None
        header = data[len(_CACHE_MAGIC) : _CACHE_HEADER_BYTES].split(b"\n")
        pcm = data[_CACHE_HEADER_BYTES:]
        if (
            len(header) != 3
            or header[0] != fingerprint.encode()
            or not pcm
            or len(pcm) % 2
            or len(pcm) > self.max_audio_bytes
            or header[1] != hashlib.sha256(pcm).hexdigest().encode()
        ):
            return None
        return tuple(
            pcm[i : i + _FRAME_BYTES] for i in range(0, len(pcm), _FRAME_BYTES)
        )

    async def _save_slot(self, slot, fingerprint, frames):
        if self.cache_dir is None:
            return
        temporary = self.cache_dir / f"{slot}.tmp"
        cancelled = threading.Event()

        def stage():
            # A canceled worker can outlive its await. Serialize staging by slot
            # and check cancellation before opening or leaving a temporary file.
            with self._disk_locks[slot]:
                if cancelled.is_set():
                    return
                try:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    pcm = b"".join(frames)
                    with temporary.open("wb") as stream:
                        stream.write(_CACHE_MAGIC + fingerprint.encode() + b"\n")
                        stream.write(hashlib.sha256(pcm).hexdigest().encode() + b"\n")
                        stream.write(pcm)
                        stream.flush()
                        os.fsync(stream.fileno())
                finally:
                    if cancelled.is_set():
                        with suppress(OSError):
                            temporary.unlink(missing_ok=True)

        try:
            await self._work(stage)
            # Publish only after the await succeeds. Cancellation/deadline during
            # staging cannot turn unfinished preparation into a reusable entry.
            temporary.replace(self.cache_dir / f"{slot}.pcm")
        except OSError:
            logger.warning("Speech cache write failed: slot=%s", slot)
        finally:
            cancelled.set()
            with suppress(OSError):
                temporary.unlink(missing_ok=True)

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
        self._validate(text, speed)
        return await self._deliver(text, on_audio, speed=speed)

    def _validate(self, text, speed):
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

    async def _deliver(self, text, on_audio, *, speed):
        self._request += 1
        request = self._request
        started = time.monotonic()
        first_pcm = False

        async def output(pcm):
            nonlocal first_pcm
            if not first_pcm:
                first_pcm = True
                logger.info(
                    "Speech stage=first_pcm request=%s elapsed_ms=%.3f",
                    request,
                    (time.monotonic() - started) * 1000,
                )
            if on_audio is not None:
                await on_audio(pcm)

        try:
            async with asyncio.timeout(self.timeout_seconds):
                slot = self._slot(text, speed)
                if slot is None:
                    return await self._generate(text, output, speed, request, started)
                async with self._locks[slot]:
                    fingerprint = self._fingerprint(text, speed)
                    cached = self._prepared.get(slot)
                    frames = cached[1] if cached and cached[0] == fingerprint else None
                    source = "memory"
                    if frames is None and self.cache_dir is not None:
                        frames = await self._work(
                            lambda: self._read_slot(slot, fingerprint)
                        )
                        source = "disk"
                    if frames is not None:
                        self._prepared[slot] = (fingerprint, frames)
                        logger.info(
                            "Speech stage=source request=%s source=%s", request, source
                        )
                        if on_audio is None:
                            if source == "memory":
                                await self._save_slot(slot, fingerprint, frames)
                            return sum(map(len, frames)) / _BYTES_PER_SECOND
                        return await self._replay(frames, output)
                    collected = []

                    async def collect(pcm):
                        await output(pcm)
                        collected.append(pcm)

                    duration = await self._generate(
                        text,
                        collect,
                        speed,
                        request,
                        started,
                        paced=on_audio is not None,
                    )
                    frames = tuple(collected)
                    # Optional persistence belongs to background preparation, never
                    # between successful foreground delivery and physical action.
                    if on_audio is None:
                        await self._save_slot(slot, fingerprint, frames)
                    self._prepared[slot] = (fingerprint, frames)
                    return duration
        except asyncio.TimeoutError:
            raise SpeechTimeout("Finite speech exceeded its deadline") from None
        except SpeechError:
            raise
        except Exception as error:  # noqa: BLE001 - provider/callback failures cross a public boundary
            raise SpeechError(
                "Finite speech delivery failed", category=failure_category(error)
            ) from None

    async def _generate(self, text, output, speed, request, started, *, paced=True):
        logger.info("Speech stage=source request=%s source=provider", request)
        logger.info(
            "Speech stage=request request=%s elapsed_ms=%.3f",
            request,
            (time.monotonic() - started) * 1000,
        )
        return await self._stream(text, output, speed=speed, paced=paced)

    async def _stream(self, text, on_audio, *, speed=1.0, paced=True):
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
                    if paced:
                        await pacer.wait(0.02)
                    await on_audio(frame)
            if not received or len(pending) % 2:
                raise SpeechError("Finite speech returned empty or incomplete PCM")
            if pending:
                if paced:
                    await pacer.wait(len(pending) / _BYTES_PER_SECOND)
                await on_audio(bytes(pending))
        return received / _BYTES_PER_SECOND
