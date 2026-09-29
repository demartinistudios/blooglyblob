"""Bound PCM before crossing into asyncio; one consumer and one wakeup."""

import asyncio
from collections import deque
import threading


class CaptureHandoff:
    def __init__(
        self, consume, on_failure, *, capacity=128, batch_size=8, retirement_timeout=1.0
    ):
        self._loop = asyncio.get_running_loop()
        self._consume, self._on_failure = consume, on_failure
        self._capacity, self._batch_size = capacity, batch_size
        self._lock = threading.Lock()
        self._packets = deque()
        self._epoch = None
        self._failure = None
        self._pending = False
        self._closed = False
        self._event = asyncio.Event()
        self.wakeups = 0
        self._task = None
        self._retirement_timeout = retirement_timeout

    @property
    def pending_count(self):
        with self._lock:
            return len(self._packets)

    async def begin(self, epoch):
        # One consumer per epoch, never one task per PCM frame. Old cloud sends
        # must finish cancellation before fresh capture can reach a new session.
        self.stop()
        await self.retire()
        with self._lock:
            if self._closed:
                raise RuntimeError("Capture handoff closed")
            self._epoch = epoch
            self._failure = None
            self._packets.clear()
            self._pending = False
            self._event.clear()
        self._task = self._loop.create_task(self._run(), name="capture-handoff")

    def stop(self):
        """Invalidate synchronously on the owning loop; retire confirms exit."""
        with self._lock:
            self._epoch = None
            self._failure = None
            self._packets.clear()
        if (
            self._task is not None
            and not self._task.done()
            and not self._task.cancelling()
        ):
            self._task.cancel()

    async def retire(self):
        if self._task is None:
            return
        done, _ = await asyncio.wait({self._task}, timeout=self._retirement_timeout)
        if not done:
            raise RuntimeError("Audio capture consumer release not confirmed")
        if not self._task.cancelled():
            self._task.result()
        self._task = None

    def submit(self, epoch, pcm):
        with self._lock:
            if self._closed or epoch != self._epoch or self._failure:
                return
            if len(self._packets) == self._capacity:
                self._packets.clear()
                self._failure = epoch, "capture_overflow"
            else:
                self._packets.append((epoch, pcm))
            if not self._pending:
                self._pending = True
                self.wakeups += 1
                self._loop.call_soon_threadsafe(self._event.set)

    async def _run(self):
        while True:
            with self._lock:
                if self._epoch is None or self._closed:
                    return
            await self._event.wait()
            with self._lock:
                failure = self._failure
                self._failure = None
                if failure:
                    self._epoch = None
                batch = [
                    self._packets.popleft()
                    for _ in range(min(self._batch_size, len(self._packets)))
                ]
                if not self._packets:
                    self._pending = False
                    self._event.clear()
            if failure:
                self._on_failure(*failure)
            for epoch, pcm in batch:
                with self._lock:
                    current = epoch == self._epoch and not self._closed
                if current:
                    try:
                        await self._consume(pcm)
                    except asyncio.CancelledError:
                        raise
                    except Exception:
                        self.stop()
                        self._on_failure(epoch, "capture_delivery_failed")
                        break
            await asyncio.sleep(0)

    async def close(self):
        with self._lock:
            self._closed = True
        self.stop()
        await self.retire()
