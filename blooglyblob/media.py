"""Direct, generation-bound speech and local-media ownership barriers."""

from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import TYPE_CHECKING

from contextlib import asynccontextmanager
import math
import uuid


if TYPE_CHECKING:
    from blooglyblob.audio.controller import AudioController
    from blooglyblob.hardware.controller import HardwareController


class MediaError(RuntimeError):
    """An owned media operation did not complete."""


class MediaCoordinator:
    def __init__(
        self, audio: AudioController, hardware: HardwareController, timeout: float = 3.0
    ) -> None:
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("Media timeout must be positive and finite")
        self.audio_owner, self.hardware = audio, hardware
        self.timeout = timeout
        self.generation: str | None = None
        self._ended = True
        self._release_lock = asyncio.Lock()
        self._search_activity: str | None = None
        self._operations: set[asyncio.Task[None]] = set()

    @property
    def ownership_uncertain(self) -> bool:
        return self.audio_owner.ownership_uncertain or self.hardware.ownership_uncertain

    @property
    def searching(self) -> bool:
        return self._search_activity is not None

    async def _complete(self, operation: Coroutine[object, object, None]) -> None:
        task = asyncio.create_task(operation)
        self._operations.add(task)

        def finished(done: asyncio.Task[None]) -> None:
            self._operations.discard(done)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(finished)
        try:
            done, _ = await asyncio.wait({task}, timeout=self.timeout)
        except asyncio.CancelledError:
            task.cancel()
            raise
        if not done:
            # Controller lifecycles are themselves shielded and continue cleanup.
            task.cancel()
            raise MediaError("Media completion unconfirmed")
        try:
            return task.result()
        except Exception:
            raise MediaError("Media operation failed") from None

    async def wait_for_local_sound(self) -> None:
        try:
            await asyncio.wait_for(self._release_lock.acquire(), self.timeout)
        except TimeoutError:
            raise MediaError("Search cleanup did not complete") from None
        else:
            self._release_lock.release()

    @asynccontextmanager
    async def search_sound(self, is_current: Callable[[], bool]) -> AsyncIterator[None]:
        async with self._release_lock:
            if not is_current() or self.generation is None or self._ended:
                raise MediaError("Search no longer owns playback")
            activity = uuid.uuid4().hex
            self._search_activity = activity
            try:
                await self._complete(
                    self.audio_owner.start_background(activity, self.generation)
                )
                yield
            finally:
                try:
                    await self._complete(self.audio_owner.stop_background(activity))
                finally:
                    self._search_activity = None

    async def begin(self, generation: str) -> None:
        if self.generation is not None:
            raise MediaError("Previous generation must finish first")
        self.generation, self._ended = generation, False
        await self.audio_owner.begin(generation)

    async def audio(self, generation: str, pcm: bytes) -> None:
        if generation == self.generation and not self._ended:
            await self.audio_owner.audio(generation, pcm)

    async def drain(self, generation: str) -> None:
        if generation != self.generation or self._ended:
            raise MediaError("Audio generation is no longer active")
        self._ended = True
        await self._complete(self.audio_owner.drain(generation))
        if self.generation != generation:
            raise MediaError("Playback was canceled")
        self.generation = None

    async def flush(self) -> None:
        """Retire speaker playback while retaining the microphone and driver."""
        generation, self.generation, self._ended = self.generation, None, True
        try:
            await asyncio.wait_for(self._release_lock.acquire(), self.timeout)
        except TimeoutError:
            raise MediaError("Search cleanup unconfirmed") from None
        try:
            if generation is not None:
                await self._complete(self.audio_owner.flush(generation))
        finally:
            self._release_lock.release()

    async def release(self) -> None:
        """Invalidate now; attempt every retiring owner even after a failure."""
        generation, self.generation, self._ended = self.generation, None, True
        errors: list[Exception] = []
        locked = False
        try:
            try:
                await asyncio.wait_for(self._release_lock.acquire(), self.timeout)
                locked = True
            except TimeoutError:
                errors.append(MediaError("Search cleanup unconfirmed"))
            if generation is not None:
                try:
                    await self._complete(self.audio_owner.flush(generation))
                except Exception as error:
                    errors.append(error)
            for operation in (self.hardware.stop_media, self.audio_owner.release):
                try:
                    await self._complete(operation())
                except Exception as error:
                    errors.append(error)
        finally:
            if locked:
                self._release_lock.release()
        if errors:
            raise MediaError("Media release unconfirmed")

    async def chime(self, activity_id: str) -> None:
        await self._complete(self.hardware.chime(activity_id))
