from tests.support.conversation import Live, session
import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("ending", ["complete", "button", "expiry", "failure"])
async def test_galactic_scan_owns_local_sound_until_search_finishes(ending):
    from blooglyblob.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.load_from_configs()
    host, _hardware, audio = session(
        registry=registry,
        inactivity_seconds=0.04,
        max_session_seconds=0.1 if ending == "expiry" else 600,
    )
    entered = asyncio.Event()
    finish = asyncio.Event()

    async def search(query):
        assert query == "weather"
        assert host.media.searching
        entered.set()
        await finish.wait()
        return "Sunny"

    async def run(context, owns):
        return await host.responses.bridge.execute(
            "scan", "galacticScan", '{"query":"weather"}', owns
        )

    host.responses.search = search
    host.responses.run = run
    host.request(True)
    await asyncio.sleep(0.02)
    live = Live.instances[-1]
    host._delegate(host.generation, "delegation")
    task = host._job
    await asyncio.wait_for(entered.wait(), 0.5)
    await host.input_audio(bytes(960))
    live.input_audio.assert_awaited_once()  # Background effect preserves continuous capture.
    live.input_audio.reset_mock()
    live.append_result.assert_not_awaited()
    if ending != "complete":
        if ending == "button":
            host.button()
        elif ending == "failure":
            await live.callbacks["on_error"](RuntimeError("voice failed"))
        await asyncio.wait_for(host._runner, 0.5)
        await asyncio.gather(task, return_exceptions=True)
        live.append_result.assert_not_awaited()
    else:
        finish.set()
        await task
        live.append_result.assert_awaited_once_with("delegation", "Sunny")
        live.discard_output.assert_not_called()
        assert not host.media.searching
        await host.input_audio(bytes(960))
        live.input_audio.assert_awaited_once()
    sent = audio.trace
    start = next(i for i, c in enumerate(sent) if c["type"] == "start_background")
    assert any(c["type"] == "stop_background" for c in sent[start + 1 :])
    await host.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("replacement_search", [False, True])
@pytest.mark.parametrize("during_startup", [False, True])
async def test_replacing_search_keeps_same_conversation_audible(
    replacement_search, during_startup
):
    from blooglyblob.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.load_from_configs()
    host, _hardware, audio = session(registry=registry)
    entered = asyncio.Event()
    count = 0

    async def delayed_start(activity, generation):
        await audio._start_background(activity, generation)
        if during_startup and count == 1:
            entered.set()
            await asyncio.Event().wait()

    audio.start_background.side_effect = delayed_start

    async def search(query):
        if query == "first":
            entered.set()
            await asyncio.Event().wait()
        return "replacement answer"

    async def run(context, owns):
        nonlocal count
        count += 1
        if count == 1 or replacement_search:
            return await host.responses.bridge.execute(
                str(count),
                "galacticScan",
                json.dumps({"query": "first" if count == 1 else "second"}),
                owns,
            )
        return "replacement answer"

    host.responses.search = search
    host.responses.run = run
    host.request(True)
    await asyncio.sleep(0.02)
    live = Live.instances[-1]
    host._delegate(host.generation, "old")
    old_job = host._job
    await asyncio.wait_for(entered.wait(), 0.5)
    host._delegate(host.generation, "new")
    await host._job
    await asyncio.gather(old_job, return_exceptions=True)
    assert host.media.generation is not None
    assert not host.media.searching
    live.append_result.assert_awaited_once_with("new", "replacement answer")
    await live.callbacks["on_audio"](bytes(960))
    command = audio.trace[-1]
    assert command["type"] == "audio"
    await host.close()


@pytest.mark.asyncio
async def test_stop_closes_cloud_and_rejects_old_audio_after_restart():
    host, _hardware, audio = session()
    host.request(True)
    await asyncio.sleep(0.02)
    old = Live.instances[-1]
    host.request(False)
    host.request(True)
    await asyncio.sleep(0.02)
    assert len(Live.instances) == 2
    old.close.assert_awaited_once()
    before = len(audio.trace)
    await old.callbacks["on_audio"](bytes(960))
    assert len(audio.trace) == before
    await host.close()
    Live.instances[-1].close.assert_awaited_once()


@pytest.mark.asyncio
async def test_silent_pcm_does_not_extend_inactivity():
    host, _hardware, _audio = session(inactivity_seconds=0.03)
    host.request(True)
    for _ in range(10):
        await host.input_audio(bytes(960))
        await asyncio.sleep(0.01)
    assert not host.active
    Live.instances[0].close.assert_awaited_once()
    await host.close()


@pytest.mark.asyncio
async def test_close_invalidates_new_activity_but_releases_retiring_audio():
    host, hardware, audio = session()
    host.request(True)
    await asyncio.sleep(0.01)
    audio.release.reset_mock()
    await host.close()
    host.button()
    assert not host.active
    assert len(Live.instances) == 1
    audio.release.assert_awaited()
    hardware.stop_media.assert_awaited()


@pytest.mark.asyncio
async def test_stop_during_connection_wait_closes_before_restart():
    host, _hardware, _audio = session()
    entered = asyncio.Event()
    released = asyncio.Event()

    class Connecting(Live):
        async def start(self, greeting=""):
            entered.set()
            await released.wait()

    host.live_factory = Connecting
    host.request(True)
    await entered.wait()
    old = Live.instances[0]
    host.request(False)
    host.request(True)
    await asyncio.sleep(0.02)
    old.close.assert_awaited_once()
    assert len(Live.instances) == 2
    released.set()
    await host.close()


@pytest.mark.asyncio
async def test_repeated_toggles_do_not_interrupt_cloud_cleanup():
    host, _hardware, _audio = session()
    host.request(True)
    await asyncio.sleep(0.01)
    entered, finish = asyncio.Event(), asyncio.Event()

    async def close_slowly():
        entered.set()
        await finish.wait()

    old = Live.instances[0]
    old.close.side_effect = close_slowly
    host.request(False)
    await entered.wait()
    for _ in range(6):
        host.request(True)
        await asyncio.sleep(0)
    assert len(Live.instances) == 1
    finish.set()
    await asyncio.sleep(0.02)
    assert len(Live.instances) == 2
    await host.close()
    old.close.assert_awaited_once()


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
@pytest.mark.asyncio
async def test_session_limits_must_be_positive_and_finite(value):
    with pytest.raises(ValueError):
        session(inactivity_seconds=value)


@pytest.mark.asyncio
async def test_owned_backend_work_suspends_idle_but_not_session_ceiling():
    host, _hardware, _audio = session(inactivity_seconds=0.01, max_session_seconds=0.05)
    host.request(True)
    host.backend_busy = True
    await asyncio.sleep(0.025)
    assert host.active
    await asyncio.sleep(0.06)
    assert not host.active
    await host.close()


@pytest.mark.asyncio
async def test_close_failure_still_invalidates_audio_and_releases_device():
    host, _hardware, audio = session()
    host.request(True)
    await asyncio.sleep(0.01)
    old = Live.instances[0]
    old.close.side_effect = RuntimeError("transport close failed")
    await host.close()
    assert not host.active
    assert host.live is None
    trace = audio.trace
    assert any(command["type"] == "flush" for command in trace)


@pytest.mark.asyncio
async def test_button_greeting_plays_before_live_even_when_live_never_speaks():
    from types import SimpleNamespace

    spoken = []

    async def speak(text, output, **options):
        spoken.append(text)
        assert options == {"speed": 1.25}
        await output(b"\x01\x00" * 480)
        return 0.02

    host, _hardware, audio = session(
        greeting="Hey! I am here.", speech=SimpleNamespace(speak=speak)
    )
    try:
        host.button()
        await asyncio.sleep(0.20)
        assert spoken == ["Hey! I am here."]
        trace = audio.trace
        assert trace.index(
            next(item for item in trace if item.get("state") == "listening")
        ) < trace.index(next(item for item in trace if item["type"] == "audio"))
        assert "already played" in Live.instances[-1].callbacks["instructions"]
    finally:
        await host.close()


@pytest.mark.asyncio
async def test_button_stop_during_greeting_closes_concurrent_live():
    from types import SimpleNamespace

    entered = asyncio.Event()

    async def speak(text, output, **options):
        await output(bytes(960))
        entered.set()
        await asyncio.Event().wait()

    host, _hardware, _audio = session(
        greeting="Hello!", speech=SimpleNamespace(speak=speak)
    )
    try:
        host.button()
        await entered.wait()
        host.button()
        await host._runner
        assert not host.active
        assert len(Live.instances) == 1
        Live.instances[0].close.assert_awaited_once()
    finally:
        await host.close()


@pytest.mark.asyncio
async def test_stop_during_eye_wakeup_prevents_greeting_and_closes_live():
    from types import SimpleNamespace

    speech = SimpleNamespace(speak=AsyncMock())
    host, _hardware, audio = session(greeting="Hello!", speech=speech)
    try:
        host.button()
        await asyncio.sleep(0.03)
        trace = audio.trace
        assert any(item.get("state") == "listening" for item in trace)
        host.button()
        await host._runner
        speech.speak.assert_not_awaited()
        assert len(Live.instances) == 1
        Live.instances[0].close.assert_awaited_once()
    finally:
        await host.close()


@pytest.mark.asyncio
async def test_stop_during_real_live_startup_bounds_stalled_transport_close():
    from types import SimpleNamespace

    from tests.support.live import FakeConnection

    from blooglyblob.ai.live import OpenAILiveSession

    host, _, audio = session(cloud_close_timeout=0.03)
    connection = FakeConnection()
    manager = AsyncMock()
    manager.__aenter__.return_value = connection
    release, closing = asyncio.Event(), asyncio.Event()

    async def stalled(*args):
        closing.set()
        await release.wait()

    manager.__aexit__.side_effect = stalled
    host.api = SimpleNamespace(live=SimpleNamespace(connect=Mock(return_value=manager)))
    host.live_factory = OpenAILiveSession
    try:
        host.button()
        await asyncio.sleep(0.02)
        host.button()
        await closing.wait()
        await asyncio.sleep(0.08)
        assert host._runner.done()
        assert host._faulted
        assert host.live is None
        trace = audio.trace
        assert trace[-1].get("state") == "idle"
    finally:
        release.set()
        await host.close()


@pytest.mark.asyncio
async def test_live_connects_during_greeting_but_echo_is_not_forwarded_and_stop_cancels_both():
    from types import SimpleNamespace

    entered = asyncio.Event()

    async def speak(text, output, **kwargs):
        entered.set()
        await asyncio.Event().wait()

    host, _, _ = session(
        greeting="Hello from space!", speech=SimpleNamespace(speak=speak)
    )
    try:
        host.button()
        await entered.wait()
        assert host.live is not None
        live = host.live
        await host.input_audio(bytes(640))
        live.input_audio.assert_not_awaited()
        host.button()
        await asyncio.wait_for(host._runner, 0.2)
        live.close.assert_awaited_once()
        assert not host.active
    finally:
        await host.close()


@pytest.mark.asyncio
async def test_microphone_resumes_after_greeting_without_another_connection_wait():
    from types import SimpleNamespace

    entered, finish = asyncio.Event(), asyncio.Event()

    async def speak(text, output, **kwargs):
        entered.set()
        await finish.wait()

    host, _, _ = session(greeting="Hello!", speech=SimpleNamespace(speak=speak))
    try:
        host.request(True)
        await entered.wait()
        live = host.live
        await host.input_audio(bytes(640))
        live.input_audio.assert_not_awaited()
        finish.set()
        await asyncio.sleep(0.01)
        assert host.live is live
        assert len(Live.instances) == 1
        await host.input_audio(bytes(640))
        live.input_audio.assert_awaited_once()
    finally:
        finish.set()
        await host.close()


@pytest.mark.asyncio
async def test_search_preserves_speech_and_input_while_background_stop_is_pending():
    from blooglyblob.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.load_from_configs()
    host, _, audio = session(registry=registry)
    host.responses.search = AsyncMock(return_value="Sunny")

    async def run(context, owns):
        return await host.responses.bridge.execute(
            "scan", "galacticScan", '{"query":"weather"}', owns
        )

    host.responses.run = run
    host.request(True)
    await asyncio.sleep(0.02)
    live = Live.instances[-1]
    releasing, resume = asyncio.Event(), asyncio.Event()

    async def delayed_release(activity):
        releasing.set()
        await resume.wait()
        await audio._stop_background(activity)

    audio.stop_background.side_effect = delayed_release
    host._delegate(host.generation, "delegation")
    await asyncio.wait_for(releasing.wait(), 0.5)
    await live.callbacks["on_audio"](bytes(960))
    assert audio.trace[-1]["type"] == "audio"
    await host.input_audio(bytes(640))
    live.input_audio.assert_awaited_once()
    live.discard_output.assert_not_called()
    live.append_result.assert_not_awaited()
    resume.set()
    await host._job
    live.discard_output.assert_not_called()
    live.append_result.assert_awaited_once_with("delegation", "Sunny")
    audio.stop_background.side_effect = audio._stop_background
    await host.close()


@pytest.mark.asyncio
async def test_input_overflow_during_startup_returns_to_idle_without_ownership_fault():
    from types import SimpleNamespace

    from blooglyblob.ai.live import OpenAILiveSession
    from tests.support.live import FakeConnection

    host, _, audio = session()
    connection = FakeConnection()
    manager = AsyncMock()
    manager.__aenter__.return_value = connection
    closing = asyncio.Event()
    finish_close = asyncio.Event()

    async def close_transport(*args):
        closing.set()
        await finish_close.wait()

    manager.__aexit__.side_effect = close_transport
    host.api = SimpleNamespace(live=SimpleNamespace(connect=Mock(return_value=manager)))
    host.live_factory = OpenAILiveSession
    try:
        host.request(True)
        for _ in range(100):
            if connection.session.start.await_count:
                break
            await asyncio.sleep(0.001)
        assert connection.session.start.await_count == 1
        live = host.live
        for _ in range(live._input.maxsize):
            await host.input_audio(bytes(960))
        overflowing = asyncio.create_task(host.input_audio(bytes(960)))
        await asyncio.wait_for(closing.wait(), 0.5)
        # Startup has failed and its finally block is already joining close.
        await asyncio.sleep(0.01)
        finish_close.set()
        await overflowing
        await asyncio.wait_for(host._runner, 0.5)
        assert not host.active
        assert not host._faulted
        assert live.close_confirmed
        audio.release.assert_awaited()
        manager.__aexit__.assert_awaited_once()
    finally:
        finish_close.set()
        await host.close()


@pytest.mark.asyncio
async def test_failed_input_from_old_session_does_not_stop_replacement():
    host, _, _ = session()
    entered, fail = asyncio.Event(), asyncio.Event()

    async def delayed_failure(pcm):
        entered.set()
        await fail.wait()
        raise RuntimeError("old session failed")

    try:
        host.request(True)
        await asyncio.sleep(0.01)
        old = host.live
        old.input_audio.side_effect = delayed_failure
        delivery = asyncio.create_task(host.input_audio(bytes(960)))
        await entered.wait()
        host.request(True)
        await asyncio.sleep(0.01)
        replacement = host.live
        assert replacement is not old
        fail.set()
        await delivery
        assert host.active
        assert host.live is replacement
        assert not host._faulted
        await host.input_audio(bytes(960))
        replacement.input_audio.assert_awaited_once()
    finally:
        fail.set()
        await host.close()
