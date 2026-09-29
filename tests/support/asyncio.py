import asyncio


async def wait_until(condition, timeout=0.5):
    async def poll():
        while not condition():
            await asyncio.sleep(0.001)

    await asyncio.wait_for(poll(), timeout)
