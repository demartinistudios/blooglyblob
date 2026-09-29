"""Bound integration work until its actual thread completion, including cancellation."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from blooglyblob.ai.tool_bridge import StaleResponse
from .registry import HARDWARE_TOOLS


class ToolExecutor:
    def __init__(self, *, hardware, handlers, terminal, concurrency=4, pool=None):
        self.hardware, self.handlers, self.terminal = hardware, handlers, terminal
        self._slots = asyncio.Semaphore(concurrency)
        self._owns_pool = pool is None
        self._pool = pool or ThreadPoolExecutor(
            max_workers=concurrency, thread_name_prefix="robot-tools"
        )
        self._pending = set()
        self._closed = False

    async def execute(self, call_id, name, params, is_current):
        if self._closed or not is_current():
            raise StaleResponse("Request no longer owns this action")
        if name == "galacticScan":
            raise ValueError("General search must use the OpenAI search bridge")
        if name in {"goToSleep", "danceMode"}:
            return await self.terminal(name, params)
        if name in HARDWARE_TOOLS:
            return await self.hardware.execute(name, params)
        handler = self.handlers.get_handler(name)
        if handler is None:
            raise ValueError("Unknown integration")
        await self._slots.acquire()
        if self._closed or not is_current():
            self._slots.release()
            raise StaleResponse("Request superseded before execution")
        loop = asyncio.get_running_loop()

        def guarded_call():
            if self._closed or not is_current():
                raise StaleResponse("Request superseded before execution")
            return handler(params)

        try:
            future = self._pool.submit(guarded_call)
        except RuntimeError:
            self._slots.release()
            raise
        self._pending.add(future)

        def completed(future):
            self._pending.discard(future)
            if not future.cancelled():
                future.exception()
            if not loop.is_closed():
                loop.call_soon_threadsafe(self._slots.release)

        future.add_done_callback(completed)
        result = await asyncio.wrap_future(future)
        if not is_current():
            raise StaleResponse("Request changed while the action was running")
        return result

    @property
    def pending(self):
        return bool(self._pending)

    async def wait_closed(self, timeout):
        futures = [asyncio.wrap_future(future) for future in tuple(self._pending)]
        for future in futures:
            future.add_done_callback(
                lambda done: done.exception() if not done.cancelled() else None
            )
        if futures:
            await asyncio.wait(futures, timeout=timeout)

    def close(self):
        self._closed = True
        if self._owns_pool:
            self._pool.shutdown(wait=False, cancel_futures=True)
