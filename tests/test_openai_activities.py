from tests.support.asyncio import wait_until
import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from tests.support.conversation import Live, session


class Speech:
    def __init__(self):
        self.words = []

    async def speak(self, text, output, **kwargs):
        self.words.append(text)
        await output(bytes(960))


@pytest.mark.asyncio
async def test_greeting_waits_for_connection_before_accepting_speech():
    connected = asyncio.Event()
    host, hardware, _ = session(speech=Speech(), greeting="Hello")

    class SlowLive(Live):
        async def start(self, greeting=""):
            await connected.wait()

    host.live_factory = SlowLive
    host.request(True)
    try:
        await wait_until(lambda: host.live is not None)
        assert not host._accept_live_input
        assert not any(x.get("state") == "speaking" for x in hardware.trace)
        # Eyes acknowledge the press immediately, but media/motion still waits
        # for the connection. A lighting mode is not microphone readiness.
        assert hardware.lighting.snapshot(time.monotonic() + 2).mode == "listening"
        hardware.present.assert_not_called()
        connected.set()
        await wait_until(lambda: host._accept_live_input)
        assert hardware.lighting.snapshot(time.monotonic() + 2).mode == "listening"
    finally:
        connected.set()
        await host.close()


@pytest.mark.asyncio
async def test_late_startup_cannot_relight_button_stopped_conversation():
    entered, canceled, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()
    host, hardware, _ = session()

    class LateLive(Live):
        async def start(self, greeting=""):
            entered.set()
            try:
                await finish.wait()
            except asyncio.CancelledError:
                canceled.set()
                await finish.wait()

    host.live_factory = LateLive
    host.request(True)
    await entered.wait()
    host.button()
    await canceled.wait()
    hardware.light = Mock(wraps=hardware.light)
    finish.set()
    await host._runner
    # The current idle transition may repeat sleeping, but retired startup
    # must not introduce even a transient listening frame.
    assert all(call.args == ("sleeping",) for call in hardware.light.call_args_list)
    assert hardware.lighting.snapshot(time.monotonic()).mode == "sleeping"
    await host.close()


@pytest.mark.asyncio
async def test_delegation_uses_transcripts_and_barge_in_keeps_work():
    entered, finish = asyncio.Event(), asyncio.Event()

    async def run(context, owns):
        assert context == [{"role": "user", "content": "set a timer"}]
        entered.set()
        await finish.wait()
        assert owns()
        return "Timer set."

    responses = SimpleNamespace(run=AsyncMock(side_effect=run))
    host, hardware, _ = session(responses=responses)
    host.request(True)
    await wait_until(lambda: host.live is not None)
    live = host.live
    await live.callbacks["on_transcript"]("user", "set a ", 0, 100)
    await live.callbacks["on_transcript"]("user", "timer", 100, 200)
    await live.callbacks["on_delegation"]("d1", 200)
    await entered.wait()
    await live.callbacks["on_transcript"]("user", "hello?", 200, 300)
    assert host.backend_busy
    assert hardware.lighting.snapshot(time.monotonic()).mode == "waiting"
    finish.set()
    await wait_until(lambda: not host.backend_busy)
    live.append_result.assert_awaited_once_with("d1", "Timer set.")
    assert hardware.lighting.snapshot(time.monotonic()).mode == "listening"
    await host.close()


@pytest.mark.asyncio
async def test_new_delegation_and_stop_fence_late_results():
    entered, canceled, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def run(context, owns):
        entered.set()
        try:
            await finish.wait()
        except asyncio.CancelledError:
            canceled.set()
            await finish.wait()  # A misbehaving integration cannot deliver after stop.
        return "Old result."

    host, _, _ = session(responses=SimpleNamespace(run=run))
    host.request(True)
    await wait_until(lambda: host.live is not None)
    live = host.live
    await live.callbacks["on_delegation"]("old", 0)
    await entered.wait()
    await live.callbacks["on_delegation"]("new", 1)
    await canceled.wait()
    await host.close()
    finish.set()
    await asyncio.sleep(0.01)
    live.append_result.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "activity,tool", [("sleep", "goToSleep"), ("dance", "danceMode")]
)
async def test_terminal_action_waits_for_actual_drain(activity, tool):
    host, hardware, audio = session(speech=Speech())
    sent_end, finish = asyncio.Event(), asyncio.Event()

    async def drain(generation):
        sent_end.set()
        await finish.wait()

    audio.drain.side_effect = drain
    hardware.execute = AsyncMock(
        return_value="Dance mode starting" if activity == "dance" else "Going to sleep"
    )
    host._request_activity(activity)
    await sent_end.wait()
    assert hardware.lighting.snapshot(time.monotonic()).mode == (
        "goodbye" if activity == "sleep" else "waiting"
    )
    hardware.execute.assert_not_awaited()
    await asyncio.sleep(0)
    hardware.execute.assert_not_awaited()
    finish.set()
    await wait_until(lambda: hardware.execute.await_count == 1)
    assert hardware.execute.call_args.args[0] == tool
    if activity == "dance":
        assert hardware.lighting.snapshot(time.monotonic()).mode == "dancing"
    await host.close()


@pytest.mark.asyncio
async def test_button_during_finite_speech_cancels_without_action():
    entered, canceled = asyncio.Event(), asyncio.Event()

    async def speak(text, output):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            canceled.set()

    host, hardware, _ = session(speech=SimpleNamespace(speak=speak))
    hardware.execute = AsyncMock()
    host._request_activity("sleep")
    await entered.wait()
    host.button()
    await canceled.wait()
    await host._runner
    hardware.execute.assert_not_awaited()
    assert not host.active
    assert hardware.lighting.snapshot(time.monotonic()).mode == "sleeping"
    await host.close()


@pytest.mark.asyncio
async def test_missing_drain_prevents_action_and_old_failure_does_not_kill_new_session():
    host, hardware, audio = session(speech=Speech(), media_timeout=0.01)
    audio.drain.side_effect = lambda generation: None

    async def stuck_drain(generation):
        await asyncio.Event().wait()

    audio.drain.side_effect = stuck_drain
    hardware.execute = AsyncMock()
    host._request_activity("sleep")
    await host._runner
    hardware.execute.assert_not_awaited()
    host.request(True)
    await wait_until(lambda: host.live is not None)
    host.media_failed("stale", "playback_failed")
    assert host.active
    await host.close()


@pytest.mark.asyncio
async def test_dance_resumes_only_on_matching_activity_and_releases_first():
    host, hardware, _ = session(speech=Speech())
    hardware.execute = AsyncMock(return_value="Dance mode starting")
    host._request_activity("dance")
    await wait_until(lambda: host._dance_id is not None)
    identifier = host._dance_id
    host.dance_finished("old")
    assert host.live is None
    host.dance_finished(identifier)
    await wait_until(lambda: host.live is not None)
    assert host.activity == "conversation"
    await host.close()


@pytest.mark.asyncio
async def test_alert_preempts_live_and_drops_second_alert_then_only_acknowledges():
    speech = Speech()
    ack = SimpleNamespace(acknowledge=AsyncMock(return_value=True))
    responses = SimpleNamespace(run=AsyncMock())
    host, _, audio = session(speech=speech, responses=responses, acknowledge=ack)
    host.request(True)
    await wait_until(lambda: host.live is not None)
    old = host.live
    assert host.alert("Timer done!")
    assert not host.alert("Doorbell")
    await wait_until(lambda: len(Live.instances) == 2)
    old.close.assert_awaited_once()
    assert speech.words == ["Timer done!"]
    trace = audio.trace
    chime = next(i for i, c in enumerate(trace) if c["type"] == "chime")
    assert any(c["type"] == "flush" for c in trace[:chime])
    alert_live = host.live
    await alert_live.callbacks["on_transcript"]("user", "thanks", 0, 100)
    await alert_live.callbacks["on_delegation"]("ack", 100)
    await wait_until(lambda: not host.active)
    await host._runner
    ack.acknowledge.assert_awaited_once()
    responses.run.assert_not_awaited()
    assert host.live is None
    assert host.activity == "idle"
    await host.close()


@pytest.mark.asyncio
async def test_alert_outage_keeps_button_dismissal_and_never_opens_live():
    speech = SimpleNamespace(
        speak=AsyncMock(side_effect=RuntimeError("provider offline"))
    )
    host, _, audio = session(speech=speech, alert_total_seconds=0.2)
    host.alert("Doorbell")
    await wait_until(lambda: speech.speak.await_count == 1)
    assert host.activity == "alert"
    assert not Live.instances
    host.button()
    await host._runner
    assert not host.active
    assert any(item["type"] == "chime" for item in audio.trace)
    assert audio.trace[-1] == {"type": "present", "state": "idle"}
    assert audio.trace.count({"type": "present", "state": "idle"}) == 1
    await host.close()


@pytest.mark.asyncio
async def test_alert_voice_ceiling_closes_cloud_and_total_ceiling_returns_idle():
    host, _, audio = session(
        speech=Speech(),
        alert_voice_seconds=0.015,
        alert_total_seconds=0.065,
        inactivity_seconds=0.005,
    )
    host.alert("Timer done!")
    await wait_until(lambda: len(Live.instances) == 1)
    live = Live.instances[0]
    await wait_until(lambda: host.live is None)
    assert host.activity == "alert"
    live.close.assert_awaited_once()
    await host._runner
    assert not host.active
    assert audio.trace.count({"type": "present", "state": "idle"}) == 1
    await host.close()


@pytest.mark.asyncio
async def test_terminal_from_owned_tool_job_cancels_reasoning_before_playback():
    host, hardware, _ = session(speech=Speech())

    async def terminal_execute(call_id, name, params, owns):
        assert owns()
        return host.terminal(name, params)

    host.executor = SimpleNamespace(execute=terminal_execute)

    async def run(context, owns):
        await host._execute_tool("call1", "goToSleep", {})
        await asyncio.sleep(0)
        return "Should never be delivered"

    host.responses = SimpleNamespace(run=run)
    hardware.execute = AsyncMock(return_value="Going to sleep")
    host.request(True)
    await wait_until(lambda: host.live is not None)
    live = host.live
    await live.callbacks["on_delegation"]("d1", 0)
    await wait_until(lambda: hardware.execute.await_count == 1)
    await host._runner
    live.append_result.assert_not_awaited()
    assert not host.active
    await host.close()


@pytest.mark.asyncio
async def test_noncooperative_jobs_remain_bounded_across_repeated_delegations():
    finish = asyncio.Event()

    async def run(context, owns):
        while not finish.is_set():
            try:
                await finish.wait()
            except asyncio.CancelledError:
                pass
        return "late"

    host, _, _ = session(responses=SimpleNamespace(run=run))
    host.request(True)
    await wait_until(lambda: host.live is not None)
    live = host.live
    for index in range(20):
        await live.callbacks["on_delegation"](str(index), index)
        await asyncio.sleep(0)
    assert len(host._jobs) <= 4
    assert not host.active
    finish.set()
    await host.close()
    live.append_result.assert_not_awaited()


@pytest.mark.asyncio
async def test_stalled_cloud_close_releases_device_and_blocks_replacement():
    host, _, audio = session(cloud_close_timeout=0.01)
    host.request(True)
    await wait_until(lambda: host.live is not None)
    old = host.live
    finish = asyncio.Event()
    old.close.side_effect = finish.wait
    try:
        await asyncio.wait_for(host.stop(), 0.2)
        assert host._faulted
        trace = audio.trace
        assert any(command["type"] == "flush" for command in trace)
        assert trace[-1]["state"] == "idle"
        host.request(True)
        await host._runner
        assert len(Live.instances) == 1
        old.close.assert_awaited_once()
    finally:
        finish.set()
        await asyncio.sleep(0)
        await host.close()


@pytest.mark.asyncio
async def test_cancelled_provider_close_still_flushes_device():
    host, _, audio = session()
    host.request(True)
    await wait_until(lambda: host.live is not None)
    host.live.close.side_effect = asyncio.CancelledError()
    await host.stop()
    assert host._faulted
    assert host.live is None
    trace = audio.trace
    assert any(command["type"] == "flush" for command in trace)
    await host.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("result", ["Dance mode starting", "acknowledgement pending"])
async def test_terminal_reservation_clears_only_on_confirmed_device_outcome(result):
    host, hardware, _ = session(speech=Speech())
    hardware.execute = AsyncMock(return_value=result)
    host._request_activity("dance")
    await wait_until(lambda: hardware.execute.await_count == 1)
    await asyncio.sleep(0)
    if result == "Dance mode starting":
        assert not host._uncertain_terminals
        assert host.actions[-1]["outcome"] == result
    else:
        await host._runner
        assert host._uncertain_terminals == {"danceMode"}
        assert "unknown" in host.actions[-1]["outcome"]
    await host.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["danceMode", "goToSleep"])
@pytest.mark.parametrize("cancel_after_dispatch", [False, True])
async def test_uncertain_terminal_completion_blocks_new_call_id(
    name, cancel_after_dispatch
):
    from blooglyblob.ai.tool_bridge import OpenAIToolBridge
    from blooglyblob.tools.registry import ToolRegistry

    host, hardware, audio = session(speech=Speech())
    registry = ToolRegistry()
    registry.load_from_configs()
    bridge = OpenAIToolBridge(registry, host._execute_tool)
    results = []

    async def terminal_execute(call_id, tool, params, owns):
        return host.terminal(tool, params)

    async def run(context, owns):
        result = await bridge.execute(str(len(results)), name, "{}", owns)
        results.append(result)
        return result

    dispatched = asyncio.Event()

    async def unconfirmed(name, params):
        dispatched.set()
        await asyncio.sleep(0.015)
        raise RuntimeError("Action outcome unconfirmed")

    hardware.execute = AsyncMock(side_effect=unconfirmed)
    host.executor = SimpleNamespace(execute=terminal_execute)
    host.responses = SimpleNamespace(run=run)
    host.request(True)
    await wait_until(lambda: host.live is not None)
    await host.live.callbacks["on_delegation"]("first", 0)
    await dispatched.wait()
    if cancel_after_dispatch:
        host.request(False)
    await host._runner
    assert "unknown" in host.actions[-1]["outcome"].lower()
    host.request(True)
    await wait_until(lambda: host.live is not None)
    await host.live.callbacks["on_delegation"]("second", 0)
    await wait_until(lambda: len(results) == 2)
    assert json.loads(results[-1])["error"] == "execution_unknown"
    hardware.execute.assert_awaited_once()
    await host.close()


@pytest.mark.asyncio
async def test_terminal_requires_fresh_media_release_after_speech_drain():
    host, hardware, audio = session(speech=Speech(), media_timeout=0.03)
    drained = False
    held_release = asyncio.Event()

    async def drain(generation):
        nonlocal drained
        drained = True

    async def stop_media():
        if drained:
            held_release.set()
            await asyncio.Event().wait()

    audio.drain.side_effect = drain
    hardware.stop_media.side_effect = stop_media
    hardware.execute = AsyncMock(return_value="Going to sleep")
    host._request_activity("sleep")
    await held_release.wait()
    hardware.execute.assert_not_awaited()
    await host._runner
    hardware.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_button_stops_dance_then_speaks_and_resumes_after_media_release():
    speech = Speech()
    host, hardware, audio = session(speech=speech)
    hardware.execute = AsyncMock(return_value="Dance mode starting")
    try:
        host._request_activity("dance")
        await wait_until(lambda: host._dance_id is not None)
        old_dance = host._dance_id
        release_requested = asyncio.Event()
        release = asyncio.Event()

        async def stop_media():
            release_requested.set()
            await release.wait()

        hardware.stop_media.side_effect = stop_media
        host.button()
        await release_requested.wait()
        assert speech.words == ["Let's dance! Time to party!"]
        assert host.live is None
        release.set()
        await wait_until(lambda: host.live is not None)
        await wait_until(lambda: speech.words[-1] == "That was fun! What's next?")
        assert host.activity == "conversation"
        generation = host.generation
        host.dance_finished(old_dance)
        assert host.generation == generation
        host.button()
        await host._runner
        host.dance_finished(old_dance)
        assert host.activity == "idle"
    finally:
        await host.close()


@pytest.mark.asyncio
async def test_dance_stop_does_not_speak_if_device_cannot_release_music():
    speech = Speech()
    host, hardware, audio = session(speech=speech)
    hardware.execute = AsyncMock(return_value="Dance mode starting")
    try:
        host._request_activity("dance")
        await wait_until(lambda: host._dance_id is not None)
        hardware.stop_media.side_effect = RuntimeError("Music release unconfirmed")
        host.button()
        await wait_until(lambda: not host.active)
        assert host.live is None
        assert speech.words == ["Let's dance! Time to party!"]
    finally:
        await host.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "activity,tool", [("sleep", "goToSleep"), ("dance", "danceMode")]
)
async def test_conversation_handoff_stays_awake_until_terminal_action(activity, tool):
    speech = Speech()
    host, hardware, audio = session(speech=speech)
    hardware.execute = AsyncMock(
        return_value="Going to sleep" if activity == "sleep" else "Dance mode starting"
    )

    async def execute(call_id, name, params, owns):
        assert owns()
        return host.terminal(name, params)

    host.executor = SimpleNamespace(execute=execute)

    async def run(context, owns):
        await host._execute_tool("terminal-call", tool, {})
        return "This private result must not be spoken"

    host.responses = SimpleNamespace(run=run)
    host.request(True)
    await wait_until(lambda: host.live is not None)
    live = host.live
    audio.trace.clear()
    try:
        await live.callbacks["on_delegation"]("terminal-delegation", 0)
        await wait_until(lambda: hardware.execute.await_count == 1)
        if activity == "sleep":
            await host._runner
        trace = audio.trace
        states = [command["state"] for command in trace if command["type"] == "present"]
        assert states == ["speaking", "idle" if activity == "sleep" else "dancing"]
        assert speech.words == [
            "Goodnight! Catch you on the next orbit."
            if activity == "sleep"
            else "Let's dance! Time to party!"
        ]
        hardware.execute.assert_awaited_once()
        live.append_result.assert_not_awaited()
        live.close.assert_awaited_once()
        assert host.live is None
        assert len(Live.instances) == 1
        live.input_audio.reset_mock()
        for _ in range(3):
            await host.input_audio(bytes(640))
            await asyncio.sleep(0)
        live.input_audio.assert_not_awaited()
        before = len(audio.trace)
        await live.callbacks["on_audio"](bytes(960))
        await live.callbacks["on_delegation"]("stale-delegation", 0)
        assert len(audio.trace) == before
        assert host.activity == ("idle" if activity == "sleep" else "dance")
    finally:
        await host.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("activity", ["sleep", "dance"])
async def test_unconfirmed_live_close_blocks_terminal_speech_and_action(activity):
    speech = Speech()
    host, hardware, audio = session(speech=speech, cloud_close_timeout=0.01)
    host.request(True)
    await wait_until(lambda: host.live is not None)
    live = host.live
    finish = asyncio.Event()
    live.close.side_effect = finish.wait
    hardware.execute = AsyncMock()
    audio.trace.clear()
    try:
        host._request_activity(activity)
        await asyncio.wait_for(host._runner, 0.2)
        assert host._faulted
        assert host.activity == "idle"
        assert speech.words == []
        hardware.execute.assert_not_awaited()
        assert len(Live.instances) == 1
        trace = audio.trace
        assert any(command["type"] == "flush" for command in trace)
        assert [c["state"] for c in trace if c["type"] == "present"] == ["idle"]
    finally:
        finish.set()
        await asyncio.sleep(0)
        await host.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "utterance,muted",
    [
        ("Please go to sleep now", True),
        ("Let's have a dance party", True),
        ("Can you dance for me?", True),
        ("Don't go to sleep", False),
        ("Why do people go to sleep?", False),
        ("Go to sleep after setting a timer", False),
        ("Set a timer", False),
        ("Search for a dinosaur fact", False),
    ],
)
async def test_only_clear_terminal_delegations_suppress_pending_speech(
    utterance, muted
):
    entered, finish = asyncio.Event(), asyncio.Event()

    async def run(context, owns):
        entered.set()
        await finish.wait()
        return "Please clarify what you meant."

    host, _, audio = session(responses=SimpleNamespace(run=run))
    try:
        host.request(True)
        await wait_until(lambda: host.live is not None)
        live = host.live
        await live.callbacks["on_transcript"]("user", utterance, 0, 1000)
        await live.callbacks["on_delegation"]("d1", 1000)
        await entered.wait()
        audio.trace.clear()
        await live.callbacks["on_audio"](bytes(960))
        chunks = [c for c in audio.trace if c["type"] == "audio"]
        assert bool(chunks) is not muted
        finish.set()
        await wait_until(lambda: not host.backend_busy)
        await live.callbacks["on_audio"](bytes(960))
        assert any(c["type"] == "audio" for c in audio.trace)
    finally:
        finish.set()
        await host.close()


@pytest.mark.asyncio
async def test_new_speech_releases_terminal_gate_and_invalidates_old_work():
    entered, finish = asyncio.Event(), asyncio.Event()
    ownership = []

    async def run(context, owns):
        entered.set()
        try:
            await finish.wait()
        except asyncio.CancelledError:
            await finish.wait()
        ownership.append(owns())
        return "Old answer"

    host, _, audio = session(responses=SimpleNamespace(run=run))
    try:
        host.request(True)
        await wait_until(lambda: host.live is not None)
        live = host.live
        await live.callbacks["on_transcript"]("user", "Go to sleep", 0, 1000)
        await live.callbacks["on_delegation"]("d1", 1000)
        await entered.wait()
        await live.callbacks["on_transcript"](
            "user", "Actually, stay awake", 1200, 2000
        )
        finish.set()
        await wait_until(lambda: bool(ownership))
        assert ownership == [False]
        live.append_result.assert_not_awaited()
        audio.trace.clear()
        await live.callbacks["on_audio"](bytes(960))
        assert any(c["type"] == "audio" for c in audio.trace)
    finally:
        finish.set()
        await host.close()


@pytest.mark.asyncio
async def test_terminal_suppression_has_a_deadline_without_canceling_valid_work():
    finish = asyncio.Event()

    async def run(context, owns):
        await finish.wait()
        return "Please clarify."

    host, _, audio = session(responses=SimpleNamespace(run=run), inactivity_seconds=0.1)
    host.SPEECH_GATE_SECONDS = 0.02
    try:
        host.request(True)
        await wait_until(lambda: host.live is not None)
        live = host.live
        await live.callbacks["on_transcript"]("user", "Go to sleep", 0, 1000)
        await live.callbacks["on_delegation"]("d1", 1000)
        await wait_until(lambda: host._speech_gate is None)
        assert host.backend_busy
        audio.trace.clear()
        await live.callbacks["on_audio"](bytes(960))
        assert any(c["type"] == "audio" for c in audio.trace)
    finally:
        finish.set()
        await host.close()


@pytest.mark.asyncio
async def test_first_greeting_frame_lights_mouth_before_greeting_finishes():
    from blooglyblob.hardware.lighting import render

    emitted, finish = asyncio.Event(), asyncio.Event()

    class HeldSpeech:
        async def speak(self, text, output, **kwargs):
            await output(bytes(960))
            emitted.set()
            await finish.wait()

    host, hardware, audio = session(speech=HeldSpeech(), greeting="Hello")

    async def audible_frame(generation, pcm):
        # Model the speaker writer publishing its first audible PCM interval.
        now = time.monotonic()
        owner = audio.presentation.begin("speech")
        audio.presentation.commit(
            owner, start=now, end=now + 0.1, position=0, level=0.8
        )
        mouth = render(hardware.lighting.snapshot(now), now)[8:]
        assert any(pixel != (0, 0, 0) for pixel in mouth)
        assert not host._accept_live_input

    audio.audio.side_effect = audible_frame
    host.request(True)
    try:
        await wait_until(emitted.is_set)
        assert not host._accept_live_input
        finish.set()
        await wait_until(lambda: host._accept_live_input)
    finally:
        finish.set()
        await host.close()
