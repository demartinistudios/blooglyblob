"""Numeric diagnostics must remain bounded and never retain conversation content."""

import json
import logging
import threading

import numpy as np

from blooglyblob.audio.diagnostics import AudioDiagnostics


def test_interval_summary_contains_only_numeric_measurements(caplog):
    stats = AudioDiagnostics()
    pcm = np.array([0, 1000, -1000, 32767, -32768], dtype="<i2").tobytes()
    stats.pcm("mic_raw", pcm)
    stats.count("capture_samples", 5)
    stats.maximum("input_age_ms", 25)
    stats.maximum("input_age_ms", 10)
    with caplog.at_level(logging.INFO):
        stats.report()
        stats.report()
    assert len(caplog.records) == 1
    record = json.loads(caplog.records[0].message.removeprefix("Audio diagnostics: "))
    assert record["counts"]["capture_samples"] == 5
    assert record["max"]["input_age_ms"] == 25
    assert record["levels"]["mic_raw"]["samples"] == 5
    assert record["levels"]["mic_raw"]["clipped"] == 2
    assert record["levels"]["mic_raw"]["peak"] == 32768
    assert record["levels"]["mic_raw"]["rms"] > 20000
    assert len(caplog.records[0].message) < 4096
    assert stats.snapshot() == {"counts": {}, "max": {}, "levels": {}}


def test_threaded_counts_are_exact_and_windows_reset():
    stats = AudioDiagnostics()

    def producer():
        for _ in range(1000):
            stats.count("capture_samples", 2048)

    threads = [threading.Thread(target=producer) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert stats.snapshot()["counts"] == {"capture_samples": 8192000}
    assert not stats.snapshot()["counts"]


def test_metric_names_cannot_become_unbounded_or_contain_content():
    stats = AudioDiagnostics()
    for i in range(1000):
        stats.count(f"private transcript {i}")
        stats.maximum(f"private search {i}", i)
        stats.pcm(f"private name {i}", bytes(2))
    assert stats.snapshot() == {"counts": {}, "max": {}, "levels": {}}


async def test_reporting_has_no_idle_output_and_has_a_fixed_cadence(monkeypatch):
    import asyncio
    import pytest
    import blooglyblob.audio.diagnostics as module
    from unittest.mock import Mock

    stats = AudioDiagnostics()
    logger = Mock()
    monkeypatch.setattr(module, "_LOG", logger)
    calls = []

    async def tick(seconds):
        calls.append(seconds)
        if len(calls) == 2:
            stats.count("input_sent_samples", 480)
        elif len(calls) == 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(module.asyncio, "sleep", tick)
    with pytest.raises(asyncio.CancelledError):
        await stats.run()
    assert calls == [10, 10, 10]
    logger.info.assert_called_once()
    assert "input_sent_samples" in logger.info.call_args.args[1]


async def test_real_conversation_reports_gated_output_without_recording_text():
    from tests.support.conversation import session
    from tests.support.asyncio import wait_until
    from types import SimpleNamespace
    import asyncio

    finish = asyncio.Event()

    async def backend(context, owns):
        await finish.wait()
        return "private result text"

    stats = AudioDiagnostics()
    host, _, audio = session(diagnostics=stats, responses=SimpleNamespace(run=backend))
    try:
        await host.input_audio(bytes(960))
        host.request(True)
        await wait_until(lambda: host._accept_live_input)
        live = host.live
        await host.input_audio(bytes(960))
        await live.callbacks["on_transcript"]("user", "Can you dance for me?", 0, 1000)
        await live.callbacks["on_delegation"]("private-delegation-id", 1000)
        await live.callbacks["on_audio"](bytes(960))
        assert not any(item["type"] == "audio" for item in audio.trace)
        summary = stats.snapshot()
        assert summary["counts"]["input_not_listening_samples"] == 480
        assert summary["counts"]["input_accepted_samples"] == 480
        assert summary["counts"]["output_gated_samples"] == 480
        assert summary["counts"]["gate_starts"] == 1
        assert "private" not in json.dumps(summary)
        assert "dance" not in json.dumps(summary)
    finally:
        finish.set()
        await host.close()


def test_full_schema_fits_a_small_summary():
    from blooglyblob.audio.diagnostics import _COUNTS, _MAXIMA, _LEVELS

    stats = AudioDiagnostics()
    for name in _COUNTS:
        stats.count(name, 10**9)
    for name in _MAXIMA:
        stats.maximum(name, 10**6)
    for name in _LEVELS:
        stats.pcm(name, bytes(4096))
    assert len(json.dumps(stats.snapshot())) < 4096


async def test_transport_ceiling_records_one_exit_after_delayed_shutdown():
    import asyncio
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock
    from blooglyblob.ai.live import OpenAILiveSession
    from tests.support.live import FakeConnection
    from tests.support.conversation import session
    from tests.support.asyncio import wait_until

    stats = AudioDiagnostics()
    host, _, _ = session(diagnostics=stats, max_session_seconds=0.1)
    connection = FakeConnection()
    manager = AsyncMock()
    manager.__aenter__.return_value = connection
    host.api = SimpleNamespace(live=SimpleNamespace(connect=Mock(return_value=manager)))
    host.live_factory = OpenAILiveSession

    async def delayed_close():
        # Keep shutdown pending long enough for the conversation's polling path
        # to observe the same failure before on_error runs.
        await asyncio.sleep(0.35)
        await connection.finalize()

    connection.session.close.side_effect = delayed_close
    try:
        host.request(True)
        await wait_until(lambda: connection.session.start.await_count == 1)
        assert host.live.diagnostics is stats
        await asyncio.sleep(0.02)
        await connection.events.put(SimpleNamespace(type="session.started"))
        await wait_until(lambda: manager.__aexit__.await_count == 1, timeout=2)
        await wait_until(lambda: host.live is None)
        counts = stats.snapshot()["counts"]
        assert counts.get("exit_ceiling") == 1
        assert counts.get("exit_failed", 0) == 0
        assert counts.get("exit_cancelled", 0) == 0
    finally:
        await host.close()
