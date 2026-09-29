import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock


class FakeConnection:
    def __init__(self):
        self.events = asyncio.Queue()
        self.session = SimpleNamespace(
            start=AsyncMock(),
            close=AsyncMock(side_effect=self.finalize),
            input_audio=SimpleNamespace(append=AsyncMock()),
            commentary=SimpleNamespace(append=AsyncMock()),
            instructions=SimpleNamespace(append=AsyncMock()),
        )

    async def finalize(self):
        await self.events.put(
            SimpleNamespace(
                type="session.closed",
                usage=SimpleNamespace(seconds=0),
                reason="close_requested",
            )
        )

    def __aiter__(self):
        return self

    async def __anext__(self):
        return await self.events.get()
