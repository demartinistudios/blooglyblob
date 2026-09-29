from tests.support.live import FakeConnection
import asyncio
import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import numpy as np
import pytest

from blooglyblob.ai.live import LiveSessionError, OpenAILiveSession


def make_session(**kwargs):
    connection = FakeConnection()
    manager = AsyncMock()
    manager.__aenter__.return_value = connection
    client = SimpleNamespace(live=SimpleNamespace(connect=Mock(return_value=manager)))
    audio, transcript, delegation = AsyncMock(), AsyncMock(), AsyncMock()
    session = OpenAILiveSession(
        client=client,
        instructions="Be curious.",
        on_audio=audio,
        on_transcript=transcript,
        on_delegation=delegation,
        **kwargs,
    )
    return session, connection, manager, audio, transcript, delegation


@pytest.mark.asyncio
async def test_ready_then_fragments_and_exactly_once_close():
    session, connection, manager, audio, transcript, delegation = make_session()
    starting = asyncio.create_task(session.start())
    await asyncio.sleep(0.01)
    assert not starting.done()
    await connection.events.put(SimpleNamespace(type="session.started"))
    await starting
    pcm = bytes(960)
    await connection.events.put(
        SimpleNamespace(
            type="session.output_audio.delta", delta=base64.b64encode(pcm).decode()
        )
    )
    await connection.events.put(
        SimpleNamespace(
            type="session.input_transcript.delta",
            delta="Set a timer",
            start_ms=100,
            end_ms=500,
        )
    )
    await connection.events.put(
        SimpleNamespace(
            type="session.delegation.created",
            delegation=SimpleNamespace(id="job1", target="client"),
            offset_ms=500,
        )
    )
    await asyncio.sleep(0.03)
    audio.assert_awaited_once_with(pcm)
    transcript.assert_awaited_once_with("user", "Set a timer", 100, 500)
    delegation.assert_awaited_once_with("job1", 500)
    await session.close()
    await session.close()
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_readiness_timeout_closes_transport():
    session, _connection, manager, *_ = make_session(readiness_timeout=0.01)
    with pytest.raises(TimeoutError):
        await session.start()
    await session.close()
    manager.__aexit__.assert_awaited_once()


async def ready(session, connection):
    starting = asyncio.create_task(session.start())
    await asyncio.sleep(0.001)
    await connection.events.put(SimpleNamespace(type="session.started"))
    await starting


@pytest.mark.asyncio
async def test_configuration_and_append_lifecycle():
    session, connection, _manager, *_ = make_session(model="custom-live", voice="marin")
    with pytest.raises(RuntimeError):
        await session.append_result("job", "Done")
    await ready(session, connection)
    config = connection.session.start.call_args.kwargs["session"]
    assert config["model"] == "custom-live"
    assert config["audio"] == {
        "format": {"type": "audio/pcm", "rate": 24000},
        "output": {"voice": "marin"},
    }
    assert config["delegation"] == {"type": "client"}
    assert config["store"] is False
    await session.append_result("job", "Verified done")
    connection.session.commentary.append.assert_awaited_once_with(
        delegation_id="job", content="Verified done"
    )
    await session.append_instruction("Wait for the result")
    connection.session.instructions.append.assert_awaited_once_with(
        delegation_id=None, content="Wait for the result"
    )
    with pytest.raises(ValueError):
        await session.append_result("job", "x" * 2001)
    await session.stop()
    with pytest.raises(RuntimeError):
        await session.append_result("job", "Late result")


@pytest.mark.asyncio
async def test_cancel_readiness_closes_and_disables_reconnection():
    session, _connection, manager, *_ = make_session()
    starting = asyncio.create_task(session.start())
    await asyncio.sleep(0.01)
    starting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await starting
    await session.close()
    manager.__aexit__.assert_awaited_once()
    session.client.live.connect.assert_called_once_with(
        max_retries=0, websocket_connection_options={"close_timeout": 0.5}
    )


@pytest.mark.asyncio
async def test_input_frames_are_paced():
    session, connection, _manager, *_ = make_session()
    times = []

    async def sent(**kwargs):
        times.append(asyncio.get_running_loop().time())
        assert len(base64.b64decode(kwargs["audio"])) == 960

    connection.session.input_audio.append.side_effect = sent
    await ready(session, connection)
    await session.input_audio(bytes(4800))
    await asyncio.sleep(0.095)
    assert 3 <= len(times) <= 5
    assert times[-1] - times[0] >= 0.02 * (len(times) - 1) - 0.025
    await session.close()


@pytest.mark.asyncio
async def test_output_does_not_block_reader_and_stop_discards_queued_audio():
    session, connection, manager, audio, _, _ = make_session()
    blocked = asyncio.Event()

    async def slow(_):
        await blocked.wait()

    audio.side_effect = slow
    await ready(session, connection)
    event = SimpleNamespace(
        type="session.output_audio.delta", delta=base64.b64encode(bytes(960)).decode()
    )
    await connection.events.put(event)
    await connection.events.put(event)
    await connection.events.put(
        SimpleNamespace(
            type="session.usage.updated", usage=SimpleNamespace(seconds=2.5)
        )
    )
    await asyncio.sleep(0.01)
    assert session.usage_seconds == 2.5
    await session.event({"type": "stop"})
    blocked.set()
    await asyncio.sleep(0.01)
    assert audio.await_count == 1
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "event",
    [
        SimpleNamespace(
            type="error",
            error=SimpleNamespace(message="sk-secret private provider error"),
        ),
        SimpleNamespace(type="session.output_audio.delta", delta="not base64!"),
        SimpleNamespace(
            type="session.output_audio.delta", delta=base64.b64encode(b"x").decode()
        ),
        SimpleNamespace(
            type="session.input_transcript.delta", delta="x", start_ms=20, end_ms=10
        ),
        SimpleNamespace(
            type="session.delegation.created",
            delegation=SimpleNamespace(id="", target="client"),
            offset_ms=0,
        ),
    ],
)
async def test_known_errors_fail_closed_and_are_sanitized(event, caplog):
    errors = AsyncMock()
    session, connection, manager, *_ = make_session(on_error=errors)
    await ready(session, connection)
    await connection.events.put(event)
    await asyncio.sleep(0.02)
    manager.__aexit__.assert_awaited_once()
    errors.assert_awaited_once()
    assert "sk-secret" not in str(errors.call_args.args[0])
    assert "sk-secret" not in caplog.text
    assert "Live session failed:" in caplog.text
    await session.close()


@pytest.mark.asyncio
async def test_callback_failure_closes_and_unknown_events_are_ignored():
    errors = AsyncMock()
    session, connection, manager, audio, transcript, _ = make_session(on_error=errors)
    await ready(session, connection)
    await connection.events.put(
        SimpleNamespace(type="session.future.added", payload="unknown")
    )
    await connection.events.put(
        SimpleNamespace(
            type="session.output_transcript.delta", delta="Hey", start_ms=1, end_ms=2
        )
    )
    await asyncio.sleep(0.01)
    transcript.assert_awaited_once_with("assistant", "Hey", 1, 2)
    audio.side_effect = RuntimeError("private device details")
    await connection.events.put(
        SimpleNamespace(
            type="session.output_audio.delta",
            delta=base64.b64encode(bytes(960)).decode(),
        )
    )
    await asyncio.sleep(0.02)
    manager.__aexit__.assert_awaited_once()
    errors.assert_awaited_once()


@pytest.mark.asyncio
async def test_bounded_input_overflow_closes():
    session, connection, manager, *_ = make_session()
    await ready(session, connection)
    with pytest.raises(RuntimeError, match="queue"):
        for _ in range(session.INPUT_QUEUE_FRAMES + 5):
            await session.input_audio(bytes(960))
    await session.close()
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_finite_ceiling_closes_connection():
    session, connection, manager, *_ = make_session(max_session_seconds=0.02)
    await ready(session, connection)
    await asyncio.sleep(0.04)
    manager.__aexit__.assert_awaited_once()
    assert 0 < session.connected_seconds < 0.04


@pytest.mark.asyncio
async def test_input_before_readiness_is_dropped_without_cloud_send():
    session, connection, _manager, *_ = make_session()
    await session.input_audio(bytes(960))
    connection.session.input_audio.append.assert_not_awaited()
    await ready(session, connection)
    await asyncio.sleep(0.025)
    connection.session.input_audio.append.assert_not_awaited()
    await session.close()


@pytest.mark.asyncio
async def test_provider_error_before_ready_raises_sanitized_failure():
    session, connection, manager, *_ = make_session()
    starting = asyncio.create_task(session.start())
    await asyncio.sleep(0.001)
    await connection.events.put(SimpleNamespace(type="error"))
    with pytest.raises(RuntimeError, match="Live"):
        await starting
    await session.close()
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_output_queue_pressure_closes_even_when_device_is_blocked():
    errors = AsyncMock()
    session, connection, manager, audio, *_ = make_session(on_error=errors)
    block = asyncio.Event()

    async def slow(_):
        await block.wait()

    audio.side_effect = slow
    await ready(session, connection)
    event = SimpleNamespace(
        type="session.output_audio.delta", delta=base64.b64encode(bytes(960)).decode()
    )
    for _ in range(100):
        await connection.events.put(event)
    await asyncio.sleep(0.02)
    manager.__aexit__.assert_awaited_once()
    errors.assert_awaited_once()
    assert session._output.qsize() == 0


@pytest.mark.asyncio
async def test_reader_eof_closes():
    class EndConnection(FakeConnection):
        async def __anext__(self):
            event = await self.events.get()
            if event is None:
                raise StopAsyncIteration
            return event

    errors = AsyncMock()
    session, _, manager, *_ = make_session(on_error=errors)
    connection = EndConnection()
    manager.__aenter__.return_value = connection
    await ready(session, connection)
    await connection.events.put(None)
    await asyncio.sleep(0.02)
    manager.__aexit__.assert_awaited_once()
    errors.assert_awaited_once()


@pytest.mark.asyncio
async def test_usage_is_cumulative_not_summed():
    session, connection, _manager, *_ = make_session()
    await ready(session, connection)
    for seconds in (1, 2, 2.5):
        await connection.events.put(
            {"type": "session.usage.updated", "usage": {"seconds": seconds}}
        )
    await asyncio.sleep(0.01)
    assert session.usage_seconds == 2.5
    await session.close()


@pytest.mark.asyncio
async def test_pcm_pacer_compensates_normal_send_time_and_resets_after_stall():
    from blooglyblob.audio.stream import PCMPacer

    now = [0.0]

    async def sleep(delay):
        now[0] += delay

    pacer = PCMPacer(clock=lambda: now[0], sleep=sleep)
    sent = []
    for _ in range(100):
        await pacer.wait(0.02)
        sent.append(now[0])
        now[0] += 0.006  # Transport overhead must not extend every frame period.
    assert sent[-1] == pytest.approx(1.98)
    now[0] += 0.25
    await pacer.wait(0.02)
    recovered = now[0]
    await pacer.wait(0.02)
    assert now[0] - recovered == pytest.approx(0.02)


@pytest.mark.asyncio
async def test_large_output_chunk_is_split_and_paced():
    session, connection, _manager, audio, *_ = make_session()
    sent = []

    async def output(pcm):
        assert len(pcm) == 960
        sent.append(asyncio.get_running_loop().time())

    audio.side_effect = output
    await ready(session, connection)
    await connection.events.put(
        SimpleNamespace(
            type="session.output_audio.delta",
            delta=base64.b64encode(bytes(960 * 4)).decode(),
        )
    )
    await asyncio.sleep(0.085)
    assert len(sent) == 4
    # Real schedulers may briefly catch up; the fake-clock test above verifies
    # exact cadence and stall reset independently of scheduling jitter.
    assert sent[-1] - sent[0] >= 0.04
    await session.close()


@pytest.mark.asyncio
async def test_control_callbacks_do_not_wait_for_blocked_audio_device():
    session, connection, _manager, audio, transcript, delegation = make_session()
    block = asyncio.Event()

    async def slow(_):
        await block.wait()

    audio.side_effect = slow
    await ready(session, connection)
    await connection.events.put(
        SimpleNamespace(
            type="session.output_audio.delta",
            delta=base64.b64encode(bytes(960)).decode(),
        )
    )
    await asyncio.sleep(0.001)
    await connection.events.put(
        SimpleNamespace(
            type="session.input_transcript.delta", delta="Stop", start_ms=1, end_ms=2
        )
    )
    await connection.events.put(
        SimpleNamespace(
            type="session.delegation.created",
            delegation=SimpleNamespace(id="job", target="client"),
            offset_ms=2,
        )
    )
    await asyncio.sleep(0.01)
    transcript.assert_awaited_once()
    delegation.assert_awaited_once()
    await session.close()


@pytest.mark.asyncio
async def test_error_callback_can_close_its_session_without_deadlock():
    session, connection, manager, *_ = make_session()
    callback_entered = asyncio.Event()

    async def failure(_):
        callback_entered.set()
        await session.close()

    session.on_error = failure
    await ready(session, connection)
    await connection.events.put({"type": "error"})
    await asyncio.wait_for(callback_entered.wait(), 0.1)
    await asyncio.wait_for(session.close(), 0.1)
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_input_odd_pcm_after_ready_fails_closed():
    session, connection, manager, *_ = make_session()
    await ready(session, connection)
    with pytest.raises(ValueError):
        await session.input_audio(b"x")
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_connect_closes_manager_once():
    session, _, manager, *_ = make_session()
    entered = asyncio.Event()
    blocked = asyncio.Event()

    async def connect():
        entered.set()
        await blocked.wait()

    manager.__aenter__.side_effect = connect
    starting = asyncio.create_task(session.start())
    await entered.wait()
    starting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await starting
    await session.close()
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_during_delegation_result_append_does_not_deadlock():
    session, connection, manager, *_ = make_session()
    appending = asyncio.Event()
    blocked = asyncio.Event()

    async def append(**_):
        appending.set()
        await blocked.wait()

    async def delegation(identifier, _):
        await session.append_result(identifier, "Done")

    connection.session.commentary.append.side_effect = append
    session.on_delegation = delegation
    await ready(session, connection)
    await connection.events.put(
        {
            "type": "session.delegation.created",
            "delegation": {"id": "job", "target": "client"},
            "offset_ms": 0,
        }
    )
    await appending.wait()
    closing = asyncio.create_task(session.close())
    await asyncio.sleep(0.02)
    completed = closing.done()
    if not completed:
        # Clean up the intentionally reproduced cancellation cycle on red.
        session._close_task.cancel()
        await asyncio.gather(closing, return_exceptions=True)
    assert completed
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_transport_close_is_not_reported_as_confirmed_cleanup():
    session, connection, manager, *_ = make_session()
    await ready(session, connection)
    manager.__aexit__.side_effect = RuntimeError("close failed")
    with pytest.raises(LiveSessionError, match="close"):
        await session.close()
    assert session.close_confirmed is False
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_graceful_close_reads_final_usage_before_releasing_transport():
    session, connection, manager, *_ = make_session()
    connection.session.close = AsyncMock()

    async def finish():
        await connection.events.put(
            SimpleNamespace(
                type="session.closed",
                usage=SimpleNamespace(seconds=2.5),
                reason="close_requested",
            )
        )

    connection.session.close.side_effect = finish
    await ready(session, connection)
    await session.close()
    connection.session.close.assert_awaited_once()
    assert session.finalization_confirmed
    assert session.usage_seconds == 2.5
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_audio_is_bounded_paced_and_purged_on_stop():
    session, connection, _, *_ = make_session()
    starting = asyncio.create_task(session.start())
    await asyncio.sleep(0.001)
    await session.input_audio(bytes(9600))
    connection.session.input_audio.append.assert_not_awaited()
    assert 0 < session._input.qsize() <= session.INPUT_QUEUE_FRAMES
    await connection.events.put(SimpleNamespace(type="session.started"))
    await starting
    await asyncio.sleep(0.035)
    assert 1 <= connection.session.input_audio.append.await_count <= 3
    await session.close()
    assert session._input.empty()
    count = connection.session.input_audio.append.await_count
    await session.input_audio(bytes(960))
    await asyncio.sleep(0.025)
    assert connection.session.input_audio.append.await_count == count


@pytest.mark.asyncio
async def test_missing_final_event_does_not_claim_final_usage():
    session, connection, manager, *_ = make_session()
    connection.session.close = AsyncMock()
    await ready(session, connection)
    await session.close()
    assert session.close_confirmed
    assert not session.finalization_confirmed
    manager.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_discard_output_fences_paced_frame_without_stopping_microphone():
    session, connection, _, audio, *_ = make_session()
    await ready(session, connection)
    event = SimpleNamespace(
        type="session.output_audio.delta", delta=base64.b64encode(bytes(960)).decode()
    )
    for _ in range(10):
        await connection.events.put(event)
    await asyncio.sleep(0.005)
    session.discard_output()
    audio.reset_mock()
    await session.input_audio(bytes(4800))
    await asyncio.sleep(0.05)
    audio.assert_not_awaited()
    assert connection.session.input_audio.append.await_count > 0
    await session.close()


async def test_transport_frames_24khz_pcm_without_resampling():
    session, connection, *_ = make_session()
    await ready(session, connection)
    pcm = np.arange(960, dtype="<i2").tobytes()
    try:
        await session.input_audio(pcm[:138])
        await session.input_audio(pcm[138:])
        for _ in range(100):
            if connection.session.input_audio.append.await_count >= 2:
                break
            await asyncio.sleep(0.002)
        sent = b"".join(
            base64.b64decode(call.kwargs["audio"])
            for call in connection.session.input_audio.append.await_args_list
        )
        assert sent == pcm
    finally:
        await session.close()
