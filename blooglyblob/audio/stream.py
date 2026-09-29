"""Pace speech frames without turning transport stalls into bursts."""

import asyncio
import time


class PCMPacer:
    """Anchor frame deadlines while allowing at most 40 ms of catch-up.

    Ordinary transport overhead is absorbed into the next wait. Longer stalls
    reset the deadline, preventing a backlog from becoming an unpaced burst.
    """

    def __init__(self, *, clock=None, sleep=None):
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._next = None

    async def wait(self, duration):
        now = self._clock()
        deadline = now if self._next is None else self._next
        if now - deadline > 0.04:
            deadline = now
        await self._sleep(max(0, deadline - now))
        now = self._clock()
        if now - deadline > 0.04:
            deadline = now
        self._next = deadline + duration
