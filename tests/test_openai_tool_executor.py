import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from blooglyblob.ai.tool_bridge import StaleResponse
from blooglyblob.tools.executor import ToolExecutor


@pytest.mark.asyncio
async def test_queued_network_call_cannot_run_after_its_response_is_superseded():
    loop = asyncio.get_running_loop()
    entered, queued = asyncio.Event(), asyncio.Event()
    release = threading.Event()
    calls = []
    second_current = True

    class ObservedSemaphore(asyncio.Semaphore):
        async def acquire(self):
            if self.locked():
                queued.set()
            return await super().acquire()

    def handler(params):
        calls.append(params["request"])
        if params["request"] == "first":
            loop.call_soon_threadsafe(entered.set)
            assert release.wait(5), "First integration was never released"
        return "finished"

    executor = ToolExecutor(
        hardware=None,
        handlers=SimpleNamespace(get_handler=lambda _: handler),
        terminal=AsyncMock(),
        concurrency=1,
    )
    executor._slots = ObservedSemaphore(1)
    tasks = []
    try:
        first = asyncio.create_task(
            executor.execute("1", "findTimers", {"request": "first"}, lambda: True)
        )
        tasks.append(first)
        await asyncio.wait_for(entered.wait(), timeout=2)
        second = asyncio.create_task(
            executor.execute(
                "2", "findTimers", {"request": "second"}, lambda: second_current
            )
        )
        tasks.append(second)
        await asyncio.wait_for(queued.wait(), timeout=2)
        assert not second.done()
        assert calls == ["first"]

        second_current = False
        release.set()
        assert await asyncio.wait_for(first, timeout=2) == "finished"
        with pytest.raises(StaleResponse):
            await asyncio.wait_for(second, timeout=2)
        assert calls == ["first"]
    finally:
        release.set()
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True), timeout=2
        )
        executor.close()
        await executor.wait_closed(timeout=2)
    assert not executor.pending


@pytest.mark.asyncio
async def test_cancelled_network_call_holds_slot_until_actual_thread_finishes():
    entered, release = threading.Event(), threading.Event()
    calls = []

    def handler(params):
        calls.append(params)
        entered.set()
        release.wait(2)
        return "finished"

    executor = ToolExecutor(
        hardware=None,
        handlers=SimpleNamespace(get_handler=lambda _: handler),
        terminal=AsyncMock(),
        concurrency=1,
    )
    first = asyncio.create_task(executor.execute("1", "findTimers", {}, lambda: True))
    for _ in range(100):
        if entered.is_set():
            break
        await asyncio.sleep(0.001)
    assert entered.is_set()
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    second = asyncio.create_task(executor.execute("2", "findTimers", {}, lambda: True))
    await asyncio.sleep(0.01)
    assert len(calls) == 1
    release.set()
    await second
    executor.close()


@pytest.mark.asyncio
async def test_hardware_uses_direct_owner_and_search_uses_provider_bridge():
    hardware = SimpleNamespace(execute=AsyncMock(return_value="Movement started"))
    executor = ToolExecutor(hardware=hardware, handlers=None, terminal=AsyncMock())
    result = await executor.execute(
        "1", "moveHead", {"direction": "left"}, lambda: True
    )
    assert result == "Movement started"
    hardware.execute.assert_awaited_once_with("moveHead", {"direction": "left"})
    with pytest.raises(ValueError):
        await executor.execute("2", "galacticScan", {"query": "weather"}, lambda: True)
    executor.close()
