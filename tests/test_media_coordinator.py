"""Direct barriers preserve speech, cancellation and physical release semantics."""

import asyncio

import pytest
from tests.support.conversation import Audio, Hardware

from blooglyblob.media import MediaCoordinator, MediaError


def media_pair(timeout=0.1):
    audio = Audio()
    hardware = Hardware(audio)
    return MediaCoordinator(audio, hardware, timeout=timeout), audio, hardware


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
async def test_search_sound_preserves_voice_and_stops_on_each_outcome(outcome):
    media, audio, _ = media_pair()
    await media.begin("voice")
    entered = asyncio.Event()

    async def search():
        async with media.search_sound(lambda: True):
            entered.set()
            await media.audio("voice", b"voice continues")
            if outcome == "error":
                raise ValueError("search failed")
            if outcome == "cancel":
                await asyncio.Event().wait()

    task = asyncio.create_task(search())
    await entered.wait()
    if outcome == "cancel":
        task.cancel()
    if outcome == "success":
        await task
    else:
        with pytest.raises(
            ValueError if outcome == "error" else asyncio.CancelledError
        ):
            await task
    assert [item["type"] for item in audio.trace] == [
        "begin",
        "start_background",
        "audio",
        "stop_background",
    ]
    assert not media.searching
    await media.audio("voice", b"answer")
    assert audio.trace[-1]["type"] == "audio"


@pytest.mark.asyncio
async def test_search_stop_timeout_fails_without_reopening_or_flushing_speech():
    media, audio, _ = media_pair(0.01)

    async def stuck(*args):
        await asyncio.Event().wait()

    audio.stop_background.side_effect = stuck
    await media.begin("voice")
    with pytest.raises(MediaError):
        async with media.search_sound(lambda: True):
            pass
    await media.audio("voice", b"voice continues")
    audio.begin.assert_awaited_once()
    audio.flush.assert_not_awaited()
    audio.audio.assert_awaited_once()


@pytest.mark.asyncio
async def test_replaced_search_stops_its_effect_without_changing_voice_generation():
    media, audio, _ = media_pair()
    current = True
    await media.begin("voice")
    async with media.search_sound(lambda: current):
        current = False
    assert audio.trace[-1]["type"] == "stop_background"
    assert media.generation == "voice"


@pytest.mark.asyncio
async def test_search_start_timeout_still_stops_unconfirmed_playback():
    media, audio, _ = media_pair(0.01)

    async def stuck(*args):
        await asyncio.Event().wait()

    audio.start_background.side_effect = stuck
    await media.begin("voice")
    with pytest.raises(MediaError):
        async with media.search_sound(lambda: True):
            pytest.fail("Search must wait for actual attachment")
    audio.stop_background.assert_awaited_once()
    assert media.generation == "voice"


@pytest.mark.asyncio
async def test_retiring_search_still_releases_effect_without_reopening_voice():
    media, audio, _ = media_pair()
    entered = asyncio.Event()
    await media.begin("voice")

    async def search():
        async with media.search_sound(lambda: True):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(search())
    await entered.wait()
    task.cancel()
    releasing = asyncio.create_task(media.release())
    await asyncio.gather(task, return_exceptions=True)
    await releasing
    audio.stop_background.assert_awaited_once()
    audio.release.assert_awaited_once()
    assert media.generation is None
    audio.begin.assert_awaited_once()


@pytest.mark.asyncio
async def test_end_requires_actual_matching_drain():
    media, audio, _ = media_pair()
    finished = asyncio.Event()
    audio.drain.side_effect = lambda generation: finished.wait()

    # AsyncMock does not await a coroutine returned by a synchronous callback.
    async def drain(generation):
        assert generation == "g"
        await finished.wait()

    audio.drain.side_effect = drain
    await media.begin("g")
    with pytest.raises(MediaError):
        await media.drain("old")
    task = asyncio.create_task(media.drain("g"))
    await asyncio.sleep(0.005)
    assert not task.done()
    finished.set()
    await task
    assert media.generation is None


@pytest.mark.asyncio
async def test_flush_drops_stale_audio_and_waits_for_all_media():
    media, audio, hardware = media_pair()
    flushed, stopped = asyncio.Event(), asyncio.Event()

    async def flush(generation):
        await flushed.wait()

    async def stop():
        await stopped.wait()

    audio.flush.side_effect, hardware.stop_media.side_effect = flush, stop
    await media.begin("g")
    releasing = asyncio.create_task(media.release())
    await asyncio.sleep(0.005)
    await media.audio("g", bytes(960))
    audio.audio.assert_not_awaited()
    assert not releasing.done()
    flushed.set()
    await asyncio.sleep(0.005)
    hardware.stop_media.assert_awaited_once()
    assert not releasing.done()
    stopped.set()
    await releasing
    audio.release.assert_awaited_once()


@pytest.mark.asyncio
async def test_playback_failure_and_missing_completion_are_not_success():
    media, audio, _ = media_pair(0.01)
    audio.drain.side_effect = RuntimeError("driver failed")
    await media.begin("g")
    with pytest.raises(MediaError):
        await media.drain("g")

    async def stuck():
        await asyncio.Event().wait()

    audio.release.side_effect = stuck
    with pytest.raises(MediaError):
        await media.release()


@pytest.mark.asyncio
async def test_release_invalidates_pending_drain_even_if_late_completion_arrives():
    media, audio, _ = media_pair()
    finish = asyncio.Event()

    async def drain(generation):
        await finish.wait()

    async def flush(generation):
        finish.set()

    audio.drain.side_effect, audio.flush.side_effect = drain, flush
    await media.begin("g")
    draining = asyncio.create_task(media.drain("g"))
    await asyncio.sleep(0.005)
    await media.release()
    with pytest.raises(MediaError):
        await draining


@pytest.mark.asyncio
async def test_noncooperative_search_cannot_block_independent_media_release():
    media, audio, hardware = media_pair(0.01)
    await media.begin("voice")
    entered, finish = asyncio.Event(), asyncio.Event()

    async def search():
        async with media.search_sound(lambda: True):
            entered.set()
            await finish.wait()

    task = asyncio.create_task(search())
    await entered.wait()
    try:
        with pytest.raises(MediaError):
            await asyncio.wait_for(media.release(), 0.15)
        hardware.stop_media.assert_awaited_once()
        audio.release.assert_awaited_once()
    finally:
        finish.set()
        await task


@pytest.mark.asyncio
async def test_speaker_flush_waits_for_search_cleanup_without_releasing_capture():
    media, audio, hardware = media_pair()
    entered, finish = asyncio.Event(), asyncio.Event()
    await media.begin("old")

    async def search():
        async with media.search_sound(lambda: True):
            entered.set()
            await finish.wait()

    searching = asyncio.create_task(search())
    await entered.wait()
    flushing = asyncio.create_task(media.flush())
    await asyncio.sleep(0)
    await media.audio("old", b"stale")
    audio.audio.assert_not_awaited()
    audio.flush.assert_not_awaited()
    finish.set()
    await searching
    await flushing
    audio.flush.assert_awaited_once_with("old")
    audio.release.assert_not_awaited()
    hardware.stop_media.assert_not_awaited()
    await media.begin("new")
    await media.audio("new", b"current")
    audio.audio.assert_awaited_once_with("new", b"current")


@pytest.mark.asyncio
async def test_failed_speaker_flush_propagates_and_full_cleanup_still_releases_driver():
    media, audio, _ = media_pair()
    audio.flush.side_effect = RuntimeError("writer stuck")
    await media.begin("old")
    with pytest.raises(MediaError):
        await media.flush()
    await media.release()
    audio.release.assert_awaited_once()
