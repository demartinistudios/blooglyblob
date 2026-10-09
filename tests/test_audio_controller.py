from tests.support.audio import Driver, Stream
import asyncio
import threading
import wave

import pytest

from blooglyblob.audio.controller import AudioController


async def wait_set(event):
    for _ in range(200):
        if event.is_set():
            return
        await asyncio.sleep(0.005)
    raise AssertionError("worker did not reach boundary")


@pytest.mark.asyncio
async def test_drain_waits_for_driver_and_cancellation_does_not_lose_cleanup():
    driver = Driver()
    audio = AudioController(driver_factory=lambda: driver)
    await audio.begin(1)
    driver.out_stream.allow_drain.clear()
    await audio.audio(1, bytes(960))
    draining = asyncio.create_task(audio.drain(1))
    await wait_set(driver.out_stream.draining)
    assert not draining.done()
    draining.cancel()
    with pytest.raises(asyncio.CancelledError):
        await draining
    driver.out_stream.allow_drain.set()
    await audio.flush(1)
    await audio.release()
    assert driver.stopped
    assert sum(map(len, driver.out_stream.frames)) == 1920
    await audio.close()


@pytest.mark.asyncio
async def test_mute_during_blocked_write_stops_later_frames():
    driver = Driver()
    audio = AudioController(driver_factory=lambda: driver)
    await audio.begin(1)
    driver.out_stream.allow_write.clear()
    await audio.audio(1, bytes(960 * 4))
    await wait_set(driver.out_stream.writing)
    audio.mute()
    await asyncio.sleep(0)  # control loop is independent of the blocked driver
    flushing = asyncio.create_task(audio.flush(1))
    assert not flushing.done()
    driver.out_stream.allow_write.set()
    await flushing
    assert len(driver.out_stream.frames) == 1
    await audio.begin(2)
    await audio.audio(1, bytes(960))
    await audio.drain(2)  # immediate empty completion is still observed
    await audio.close()


@pytest.mark.asyncio
async def test_worker_failure_reaches_waiter_sanitized_and_prevents_replacement():
    driver = Driver()
    failures = []
    failure_received = asyncio.Event()

    def on_failure(*args):
        failures.append(args)
        failure_received.set()

    audio = AudioController(driver_factory=lambda: driver, on_failure=on_failure)
    await audio.begin(1)
    driver.out_stream.allow_write.clear()
    await audio.audio(1, bytes(960 * 4))
    await wait_set(driver.out_stream.writing)
    await audio.audio(1, bytes(960 * 2))
    queued_samples = sum(
        len(command.data) // 2
        for command in audio._writer._commands
        if command.kind == "chunk"
    )
    assert queued_samples >= 960
    driver.out_stream.fail = True
    driver.out_stream.allow_write.set()
    with pytest.raises(RuntimeError, match="playback_failed"):
        await audio.drain(1)
    await asyncio.wait_for(failure_received.wait(), timeout=1)
    assert failures == [(1, "playback_failed")]
    # The failed in-flight write has uncertain delivery; queued chunks are
    # definitely discarded by failure cleanup.
    assert (
        audio.diagnostics.snapshot()["counts"]["playback_discarded_samples"]
        == queued_samples
    )
    with pytest.raises(RuntimeError):
        await audio.begin(2)
    await audio.close()


@pytest.mark.asyncio
async def test_scanner_and_stale_stop_preserve_capture_and_speech(tmp_path):
    path = tmp_path / "scanner.wav"
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, 48000, 0, "NONE", ""))
        out.writeframes(b"\x01\x00" * 4800)
    driver = Driver()
    captured, levels = [], []

    async def capture(pcm):
        captured.append(pcm)

    audio = AudioController(
        driver_factory=lambda: driver, on_input=capture, on_level=levels.append
    )
    await audio.prepare(path)
    await audio.begin(1)
    await audio.start_background("search", 1)
    await audio.stop_background("old")
    driver.on_input(b"mic")
    await audio.audio(1, b"\x00\x04" * 480)
    await audio.stop_background("search")
    await audio.drain(1)
    assert captured == [b"mic"]
    assert any(level > 0 for level in levels)
    await audio.close()


@pytest.mark.asyncio
async def test_conversion_tail_resets_and_reuses_one_driver_between_generations():
    import numpy as np
    from blooglyblob.audio.resampler import PCMResampler

    driver = Driver()
    created = []

    def factory():
        created.append(driver)
        return driver

    audio = AudioController(driver_factory=factory)
    expected = b""
    for generation, value in ((1, 8000), (2, -4000)):
        pcm = np.full(1301, value, dtype="<i2").tobytes()
        expected += PCMResampler(24000, 48000).process(pcm, last=True)
        await audio.begin(generation)
        await audio.audio(generation, pcm)
        drain = asyncio.create_task(audio.drain(generation))
        await asyncio.sleep(0)
        await audio.audio(generation, bytes(960))  # post-end audio is rejected
        await drain
    assert created == [driver]
    assert b"".join(driver.out_stream.frames) == expected
    assert all(len(frame) <= 1920 for frame in driver.out_stream.frames)
    await audio.close()


@pytest.mark.asyncio
async def test_cancelled_start_is_joined_by_release_without_resurrection():
    driver = Driver()
    entered, resume = threading.Event(), threading.Event()
    original = driver.start

    def blocked_start(*args):
        entered.set()
        resume.wait(2)
        original(*args)

    driver.start = blocked_start
    audio = AudioController(driver_factory=lambda: driver)
    starting = asyncio.create_task(audio.begin(1))
    await wait_set(entered)
    starting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await starting
    releasing = asyncio.create_task(audio.release())
    await asyncio.sleep(0.01)
    assert not releasing.done()
    resume.set()
    await releasing
    assert driver.stopped
    assert audio._driver is None
    await audio.release()
    await audio.close()


@pytest.mark.asyncio
async def test_release_timeout_keeps_ownership_and_does_not_close_under_writer():
    driver = Driver()
    failures = []
    audio = AudioController(
        driver_factory=lambda: driver,
        operation_timeout=0.05,
        on_failure=lambda *args: failures.append(args),
    )
    await audio.begin(1)
    driver.out_stream.allow_write.clear()
    await audio.audio(1, bytes(960 * 2))
    await wait_set(driver.out_stream.writing)
    with pytest.raises(RuntimeError, match="not confirmed"):
        await audio.release()
    assert not driver.stopped
    assert audio._physical.locked()
    with pytest.raises(RuntimeError):
        await audio.begin(2)
    driver.out_stream.allow_write.set()
    audio._timeout = 1
    await audio.close()
    assert failures == [(1, "audio_ownership_timeout")]


@pytest.mark.asyncio
async def test_output_overflow_fails_without_claiming_drain():
    driver = Driver()
    failures = []
    failure_received = asyncio.Event()

    def on_failure(*args):
        failures.append(args)
        failure_received.set()

    audio = AudioController(
        driver_factory=lambda: driver,
        on_failure=on_failure,
    )
    await audio.begin(1)
    await audio.audio(1, bytes(960 * 100))
    with pytest.raises(RuntimeError, match="output_overflow"):
        await audio.drain(1)
    # Drain completion and the loop's failure callback are separate signals.
    await asyncio.wait_for(failure_received.wait(), timeout=1)
    assert failures == [(1, "output_overflow")]
    await audio.close()
    summary = audio.diagnostics.snapshot()
    assert summary["counts"]["playback_submitted_samples"] == 48000
    assert summary["counts"]["playback_discarded_samples"] == 48000
    assert summary["counts"].get("playback_written_samples", 0) == 0
    assert summary["max"]["playback_queue_frames"] == 20


@pytest.mark.asyncio
async def test_failed_driver_drain_never_confirms_completion_and_clears_level():
    driver = Driver()
    levels = []

    def fail_drain():
        raise RuntimeError("private native detail")

    driver.out_stream.stop_stream = fail_drain
    audio = AudioController(
        driver_factory=lambda: driver,
        on_level=levels.append,
    )
    await audio.begin(1)
    await audio.audio(1, bytes(960))
    with pytest.raises(RuntimeError, match="playback_failed"):
        await audio.drain(1)
    assert levels[-1] == 0
    await audio.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mute", [False, True])
async def test_file_playback_uses_shared_selector_rate_conversion_and_local_mute(
    tmp_path, monkeypatch, mute
):
    import sys
    import types

    path = tmp_path / "alert.wav"
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, 16000, 0, "NONE", ""))
        out.writeframes(b"\x00\x20" * 2049)
    stream = Stream()
    stream.close = lambda: None
    opened = []

    class PortAudio:
        def get_device_count(self):
            return 1

        def get_device_info_by_index(self, index):
            return {"name": "USB speaker", "maxOutputChannels": 1}

        def get_format_from_width(self, width):
            return width

        def open(self, **kwargs):
            opened.append(kwargs)
            return stream

        def terminate(self):
            pass

    monkeypatch.setitem(
        sys.modules, "pyaudio", types.SimpleNamespace(PyAudio=PortAudio)
    )
    audio = AudioController()
    stop = threading.Event()
    stream.allow_write.clear()
    work = asyncio.create_task(
        asyncio.to_thread(audio.play_file, path, stop, output_rate=48000)
    )
    await wait_set(stream.writing)
    if mute:
        audio.mute()
        assert stop.is_set()
    with pytest.raises(RuntimeError, match="Local media still owns"):
        await audio.begin(1)
    stream.allow_write.set()
    await work
    assert opened[0]["rate"] == 48000
    assert opened[0]["output_device_index"] == 0
    if mute:
        # Muting discards the filter tail and all remaining file samples.
        assert len(stream.frames) == 1
        assert 0 < len(stream.frames[0]) <= 1024 * 2 * 3
    else:
        from blooglyblob.audio.resampler import PCMResampler

        output = b"".join(stream.frames)
        assert len(output) == 2049 * 2 * 3
        assert output == PCMResampler(16000, 48000).process(
            b"\x00\x20" * 2049, last=True
        )
    await audio.close()


@pytest.mark.asyncio
async def test_scanner_only_frames_do_not_drive_talking_and_stale_stop_keeps_new_effect(
    tmp_path,
):
    path = tmp_path / "scanner.wav"
    with wave.open(str(path), "wb") as out:
        out.setparams((1, 2, 48000, 0, "NONE", ""))
        out.writeframes(b"\x00\x10" * 4800)
    driver = Driver()
    original = driver.out_stream.write

    def paced(pcm):
        original(pcm)
        threading.Event().wait(0.002)

    driver.out_stream.write = paced
    levels = []
    audio = AudioController(
        driver_factory=lambda: driver,
        on_level=levels.append,
    )
    await audio.prepare(path)
    await audio.begin(1)
    await audio.start_background("old", 1)
    await audio.stop_background("old")
    await audio.start_background("new", 1)
    await audio.stop_background("old")
    count = len(driver.out_stream.frames)
    await asyncio.sleep(0.02)
    assert len(driver.out_stream.frames) > count  # stale stop did not stop new effect
    assert all(level == 0 for level in levels)
    await audio.audio(1, b"\x00\x20" * 4800)
    await audio.stop_background("new")
    await audio.drain(1)
    assert any(level > 0 for level in levels)
    await audio.close()


@pytest.mark.asyncio
async def test_capture_epoch_rejects_old_driver_after_release_and_reopen():
    drivers, captured = [], []

    def factory():
        drivers.append(Driver())
        return drivers[-1]

    async def capture(pcm):
        captured.append(pcm)

    audio = AudioController(driver_factory=factory, on_input=capture)
    await audio.begin(1)
    old_input = drivers[0].on_input
    await audio.release()
    await audio.begin(2)
    old_input(b"old")
    drivers[1].on_input(b"new")
    await asyncio.sleep(0.01)
    assert captured == [b"new"]
    await audio.close()


@pytest.mark.asyncio
async def test_real_driver_captures_while_writer_is_blocked(monkeypatch):
    import sys
    import types

    output = Stream()
    output.close = lambda: None
    opened = []

    class PortAudio:
        def get_device_count(self):
            return 1

        def get_device_info_by_index(self, index):
            return {
                "name": "USB PnP Sound Device",
                "maxInputChannels": 1,
                "maxOutputChannels": 1,
            }

        def open(self, **kwargs):
            opened.append(kwargs)
            if kwargs.get("input"):
                return types.SimpleNamespace(
                    stop_stream=lambda: None, close=lambda: None
                )
            return output

        def terminate(self):
            pass

    monkeypatch.setitem(
        sys.modules,
        "pyaudio",
        types.SimpleNamespace(PyAudio=PortAudio, paInt16=8, paContinue=0),
    )
    monkeypatch.setenv("MIC_GAIN", "1")
    received = []

    async def capture(pcm):
        received.append(pcm)

    audio = AudioController(on_input=capture)
    await audio.begin(1)
    output.allow_write.clear()
    await audio.audio(1, bytes(1920))
    await wait_set(output.writing)
    # A stalled reporter must not make the native callback wait on its lock.
    callback_done = threading.Event()

    def native_callback():
        opened[0]["stream_callback"](bytes(4096), 2048, None, 2)
        callback_done.set()

    with audio.diagnostics._lock:
        callback = threading.Thread(target=native_callback)
        callback.start()
        assert callback_done.wait(0.5)
    callback.join()
    for _ in range(100):
        if received:
            break
        await asyncio.sleep(0.005)
    assert received
    assert (
        0 < len(received[0]) <= 2048
    )  # Continuous 48-to-24 kHz filter may retain a tail.
    output.allow_write.set()
    await audio.close()
    summary = audio.diagnostics.snapshot()
    assert summary["counts"]["capture_overflows"] == 1
    assert summary["counts"]["capture_samples"] == 2048
    assert summary["counts"]["handoff_delivered_samples"] == len(received[0]) // 2
    assert summary["levels"]["mic_raw"]["samples"] == 2048
    assert summary["levels"]["mic_processed"]["samples"] == len(received[0]) // 2


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["output_overflow", "capture_overflow"])
async def test_activity_overflow_recovers_only_after_confirmed_release(failure):
    drivers = []

    def factory():
        drivers.append(Driver())
        return drivers[-1]

    audio = AudioController(driver_factory=factory)
    await audio.begin(1)
    if failure == "output_overflow":
        await audio.audio(1, bytes(960 * 100))
        with pytest.raises(RuntimeError, match=failure):
            await audio.drain(1)
    else:
        for _ in range(200):
            drivers[-1].on_input(b"mic")
        await asyncio.sleep(0.01)
    with pytest.raises(RuntimeError):
        await audio.begin(2)
    await audio.release()
    await audio.begin(2)
    await audio.audio(2, bytes(960))
    await audio.drain(2)
    assert len(drivers) == 2
    await audio.close()


@pytest.mark.asyncio
async def test_late_playback_failure_from_released_owner_cannot_fault_new_owner():
    drivers, failures = [], []

    def factory():
        drivers.append(Driver())
        return drivers[-1]

    audio = AudioController(
        driver_factory=factory, on_failure=lambda *args: failures.append(args)
    )
    await audio.begin(1)
    retiring_failure = audio._writer._failure
    await audio.release()
    await audio.begin(2)
    retiring_failure(1, "playback_failed")
    await asyncio.sleep(0)
    await audio.audio(2, bytes(960))
    await audio.drain(2)
    assert failures == []
    await audio.close()


@pytest.mark.asyncio
async def test_same_driver_old_generation_failure_cannot_fault_new_generation():
    failures = []
    audio = AudioController(
        driver_factory=Driver, on_failure=lambda *args: failures.append(args)
    )
    await audio.begin(1)
    old_failure = audio._writer._failure
    await audio.drain(1)
    await audio.begin(2)
    old_failure(1, "playback_failed")
    await asyncio.sleep(0)
    await audio.drain(2)
    assert failures == []
    await audio.close()


@pytest.mark.asyncio
async def test_mute_during_startup_blocks_speech_until_explicit_new_generation():
    driver = Driver()
    entered, resume = threading.Event(), threading.Event()
    original = driver.start

    def blocked_start(*args):
        entered.set()
        resume.wait(2)
        original(*args)

    driver.start = blocked_start
    audio = AudioController(driver_factory=lambda: driver)
    starting = asyncio.create_task(audio.begin(1))
    await wait_set(entered)
    audio.mute()
    with pytest.raises(RuntimeError, match="ownership is not active"):
        await audio.drain(1)
    with pytest.raises(RuntimeError, match="ownership is not active"):
        await audio.flush(1)
    resume.set()
    with pytest.raises(RuntimeError, match="startup muted"):
        await starting
    await audio.audio(1, bytes(1920))
    await asyncio.sleep(0.01)
    assert driver.out_stream.frames == []
    await audio.begin(2)
    await audio.audio(2, bytes(960))
    await audio.drain(2)
    assert driver.out_stream.frames
    await audio.close()


@pytest.mark.asyncio
async def test_ownership_timeout_remains_permanent_after_eventual_release():
    driver = Driver()
    audio = AudioController(driver_factory=lambda: driver, operation_timeout=0.02)
    await audio.begin(1)
    driver.out_stream.allow_write.clear()
    await audio.audio(1, bytes(1920))
    await wait_set(driver.out_stream.writing)
    with pytest.raises(RuntimeError, match="not confirmed"):
        await audio.release()
    driver.out_stream.allow_write.set()
    audio._timeout = 1
    await audio.release()
    assert driver.stopped
    with pytest.raises(RuntimeError, match="ownership_timeout"):
        await audio.begin(2)
    await audio.close()


@pytest.mark.asyncio
async def test_unreleased_capture_consumer_is_permanent_ownership_failure():
    entered, allow_finish = asyncio.Event(), asyncio.Event()
    driver = Driver()
    failures = []

    async def capture(pcm):
        entered.set()
        try:
            await allow_finish.wait()
        except asyncio.CancelledError:
            await allow_finish.wait()

    audio = AudioController(
        driver_factory=lambda: driver,
        on_input=capture,
        on_failure=lambda *args: failures.append(args),
    )
    audio._capture._retirement_timeout = 0.01
    await audio.begin(1)
    driver.on_input(b"old")
    await entered.wait()
    with pytest.raises(RuntimeError, match="capture consumer"):
        await audio.release()
    assert not driver.stopped
    assert failures == [(1, "capture_retirement_timeout")]
    allow_finish.set()
    await audio.release()
    with pytest.raises(RuntimeError, match="capture_retirement_timeout"):
        await audio.begin(2)
    await audio.close()


@pytest.mark.asyncio
async def test_retired_driver_failure_while_idle_cannot_relatch_fault():
    drivers, failures = [], []

    def factory():
        drivers.append(Driver())
        return drivers[-1]

    audio = AudioController(
        driver_factory=factory, on_failure=lambda *args: failures.append(args)
    )
    await audio.begin(1)
    old_failure = drivers[0].on_failure
    await audio.release()
    old_failure("input_overflow")
    await asyncio.sleep(0)
    await audio.begin(2)
    await audio.drain(2)
    assert failures == []
    await audio.close()


async def test_resource_preparation_worker_is_bounded_and_retained_for_release(
    monkeypatch,
):
    from blooglyblob.audio.background import BackgroundSound

    finish = threading.Event()

    def stuck(path):
        finish.wait(1)
        return object()

    monkeypatch.setattr(BackgroundSound, "from_wav", stuck)
    audio = AudioController(operation_timeout=0.01)
    try:
        with pytest.raises(RuntimeError, match="ownership"):
            await asyncio.wait_for(audio.prepare("unused"), 0.1)
        assert audio.ownership_uncertain
    finally:
        finish.set()
        await asyncio.sleep(0.02)
        await audio.close()


async def test_muted_blocking_write_cannot_relight_mouth():
    import time
    from blooglyblob.hardware.lighting import LightingState, render

    driver = Driver()
    driver.out_stream.get_output_latency = lambda: 0.05
    audio = AudioController(driver_factory=lambda: driver)
    lights = LightingState(audio.presentation)
    lights.set_mode("listening", now=0)
    await audio.begin("first")
    driver.out_stream.allow_write.clear()
    await audio.audio("first", b"\xa0\x0f" * 960)
    await wait_set(driver.out_stream.writing)
    audio.mute()
    driver.out_stream.allow_write.set()
    await audio.flush("first")
    for offset in (0, 0.05, 0.1):
        now = time.monotonic() + offset
        assert render(lights.snapshot(now), now)[8:] == ((0, 0, 0),) * 8
    await audio.close()


async def test_real_output_drives_mouth_through_drain_without_touching_capture(
    monkeypatch,
):
    from blooglyblob.audio.presentation import OutputTimeline
    from blooglyblob.hardware.lighting import LightingState, render

    clock = [1.0]
    driver = Driver()
    original_write = driver.out_stream.write

    def write(pcm):
        original_write(pcm)
        clock[0] += len(pcm) / 96000

    driver.out_stream.write = write
    driver.out_stream.get_output_latency = lambda: 0.05
    monkeypatch.setattr(
        "blooglyblob.audio.playback.OutputTimeline",
        lambda *args: OutputTimeline(*args, clock=lambda: clock[0]),
    )
    captured = []

    async def capture(pcm):
        captured.append(pcm)

    audio = AudioController(driver_factory=lambda: driver, on_input=capture)
    lights = LightingState(audio.presentation)
    lights.set_mode("listening", now=0)
    await audio.begin("voice")
    driver.out_stream.allow_drain.clear()
    await audio.audio("voice", b"\xa0\x0f" * 2400)
    drain = asyncio.create_task(audio.drain("voice"))
    await wait_set(driver.out_stream.draining)
    now = clock[0] + 0.01
    assert any(rgb != (0, 0, 0) for rgb in render(lights.snapshot(now), now)[8:])
    driver.on_input(b"mic")
    await asyncio.sleep(0.01)
    assert captured == [b"mic"]
    assert not drain.done()
    driver.out_stream.allow_drain.set()
    await drain
    assert audio.presentation.sample(now).kind is None
    await audio.close()
