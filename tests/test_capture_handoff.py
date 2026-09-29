import asyncio

import pytest

from blooglyblob.audio.capture import CaptureHandoff


@pytest.mark.asyncio
async def test_bounded_overflow_is_coalesced_and_faults_only_current_epoch():
    received, failures = [], []

    async def consume(pcm):
        received.append(pcm)

    bridge = CaptureHandoff(
        consume,
        lambda epoch, reason: failures.append((epoch, reason)),
        capacity=2,
        batch_size=1,
    )
    await bridge.begin(1)
    for _ in range(1000):
        bridge.submit(1, b"12")
    assert bridge.pending_count <= 2
    assert bridge.wakeups == 1
    await asyncio.sleep(0.01)
    assert failures == [(1, "capture_overflow")]
    assert received == []
    await bridge.begin(2)
    bridge.submit(1, b"old")
    bridge.submit(2, b"new")
    await asyncio.sleep(0.01)
    assert received == [b"new"]
    await bridge.close()


@pytest.mark.asyncio
async def test_batched_capture_yields_to_controls_and_stop_rejects_old_packets():
    seen = []

    async def consume(pcm):
        seen.append(pcm)

    bridge = CaptureHandoff(consume, lambda *_: None, capacity=100, batch_size=2)
    await bridge.begin(1)
    for _ in range(20):
        bridge.submit(1, b"a")
    asyncio.get_running_loop().call_soon(lambda: seen.append(b"control"))
    await asyncio.sleep(0.01)
    assert seen.index(b"control") < 20
    bridge.stop()
    bridge.submit(1, b"old")
    await asyncio.sleep(0.01)
    assert b"old" not in seen
    await bridge.close()


@pytest.mark.asyncio
async def test_epoch_switch_cancels_old_inflight_delivery_before_new_delivery():
    entered, retired = asyncio.Event(), asyncio.Event()
    received = []

    async def consume(pcm):
        if pcm == b"old":
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                retired.set()
        else:
            assert retired.is_set()
            received.append(pcm)

    bridge = CaptureHandoff(consume, lambda *_: None)
    await bridge.begin(1)
    bridge.submit(1, b"old")
    await entered.wait()
    await bridge.begin(2)
    bridge.submit(2, b"new")
    await asyncio.sleep(0.01)
    assert received == [b"new"]
    await bridge.close()


@pytest.mark.asyncio
async def test_cancellation_resistant_delivery_times_out_without_replacement():
    entered, release = asyncio.Event(), asyncio.Event()
    received = []

    async def consume(pcm):
        received.append(pcm)
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()

    bridge = CaptureHandoff(consume, lambda *_: None, retirement_timeout=0.01)
    await bridge.begin(1)
    bridge.submit(1, b"old")
    await entered.wait()
    with pytest.raises(RuntimeError, match="capture consumer"):
        await bridge.begin(2)
    bridge.submit(2, b"new")
    assert received == [b"old"]
    release.set()
    await bridge.close()
