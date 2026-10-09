"""Direct composition and process-lifetime regressions; no real cloud or devices."""

from tests.support.application import app_rig as app_rig
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from blooglyblob.config import AIConfig


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "nonsense"])
async def test_bad_limits_fail_before_provider_or_hardware(monkeypatch, value):
    from blooglyblob.application import Application
    import openai

    factory = Mock()
    monkeypatch.setattr(openai, "AsyncOpenAI", factory)
    monkeypatch.setenv("OPENAI_INACTIVITY_SECONDS", value)
    app = Application(config=AIConfig(openai_api_key="fake"))
    with pytest.raises(ValueError):
        await app.start()
    factory.assert_not_called()
    assert app.audio is None and app.hardware is None


@pytest.mark.asyncio
async def test_shutdown_failure_still_closes_independent_owners():
    from blooglyblob.application import Application, OwnershipUncertain

    app = Application(config=AIConfig(openai_api_key="fake"))
    app.audio = SimpleNamespace(mute=Mock(), close=AsyncMock())
    app.hardware = SimpleNamespace(mute_media=Mock(), close=AsyncMock())
    app.session = SimpleNamespace(close=AsyncMock(side_effect=RuntimeError("secret")))
    app._api = SimpleNamespace(close=AsyncMock())
    api = app._api
    with pytest.raises(OwnershipUncertain):
        await app.stop()
    app.audio.close.assert_awaited_once()
    app.hardware.close.assert_awaited_once()
    api.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_accepts_worker_completion_before_tracking_removal(monkeypatch):
    from concurrent.futures import Future
    import threading
    import blooglyblob.application as application

    published, release = threading.Event(), threading.Event()

    class PausedAfterCompletion(Future):
        def set_result(self, result):
            published.set()
            super().set_result(result)
            release.wait(2)

    monkeypatch.setattr(application, "Future", PausedAfterCompletion)
    app = application.Application(config=AIConfig(openai_api_key="fake"))
    producer = SimpleNamespace(stop=Mock())
    app._timer_manager = producer
    try:
        await app.stop()
        assert published.is_set()
        producer.stop.assert_called_once()
        assert not app._faulted
    finally:
        release.set()


@pytest.mark.asyncio
async def test_media_release_attempts_all_owners_after_scanner_stop_failure():
    from blooglyblob.media import MediaCoordinator, MediaError

    audio = SimpleNamespace(release=AsyncMock(), flush=AsyncMock())
    hardware = SimpleNamespace(stop_media=AsyncMock(side_effect=RuntimeError("failed")))
    media = MediaCoordinator(audio, hardware)
    with pytest.raises(MediaError):
        await media.release()
    audio.release.assert_awaited_once()


@pytest.mark.asyncio
async def test_ready_does_not_start_conversation_and_greeting_is_owned_after_ready(
    app_rig,
):
    app, _, audio, hardware, ready = app_rig

    async def prepare(*args, **kwargs):
        ready.assert_called_once()
        assert app._ready
        await asyncio.Event().wait()

    app._speech.prepare.side_effect = prepare
    await app.start()
    ready.assert_called_once()
    assert app.session.live is None
    audio.begin.assert_not_awaited()
    await asyncio.sleep(0)
    assert app._tasks
    await app.stop()
    assert not app._tasks
    audio.close.assert_awaited_once()
    hardware.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_confirmed_provider_error_recovers_idle_but_uncertain_close_stops_app(
    app_rig,
):
    from tests.support.conversation import Live
    from tests.support.asyncio import wait_until
    from blooglyblob.application import OwnershipUncertain

    app, _, audio, _, _ = app_rig
    await app.start()
    app.session.greeting = ""
    app.session.live_factory = Live
    app._button()
    await wait_until(lambda: app.session.live is not None)
    first = app.session.live
    await first.callbacks["on_error"](RuntimeError("private"))
    await app.session._runner
    assert not app._faulted and app.session.activity == "idle"
    app._button()
    await wait_until(lambda: app.session.live is not None)
    app.session.live.close.side_effect = RuntimeError("private")
    app._button()
    await app.session._runner
    assert app._faulted and app._stopping and app._done.is_set()
    audio.mute.assert_called()
    with pytest.raises(OwnershipUncertain):
        await app.stop()


@pytest.mark.asyncio
async def test_missing_final_usage_with_confirmed_transport_is_warning(app_rig, caplog):
    from tests.support.conversation import Live
    from tests.support.asyncio import wait_until

    app, _, _, _, _ = app_rig
    await app.start()
    app.session.greeting = ""
    app.session.live_factory = Live
    app._button()
    await wait_until(lambda: app.session.live is not None)
    live = app.session.live
    live.session_started, live.close_confirmed, live.finalization_confirmed = (
        True,
        True,
        False,
    )
    app._button()
    await app.session._runner
    assert not app._faulted and not app.session._faulted
    assert "final usage unavailable" in caplog.text
    await app.stop()


@pytest.mark.asyncio
async def test_blocked_session_and_saturated_pool_still_attempt_independent_cleanup(
    app_rig,
):
    import threading
    from blooglyblob.application import OwnershipUncertain

    app, api, audio, hardware, _ = app_rig
    await app.start()
    app.shutdown_seconds = 0.25
    release = threading.Event()
    work = [asyncio.create_task(app._work(release.wait)) for _ in range(4)]
    session_release = asyncio.Event()
    app.session.close = AsyncMock(side_effect=session_release.wait)
    producer_stopped = threading.Event()
    app._timer_manager.stop = producer_stopped.set
    try:
        with pytest.raises(OwnershipUncertain):
            await asyncio.wait_for(app.stop(), 0.5)
        assert producer_stopped.is_set()
        hardware.close.assert_awaited_once()
        audio.close.assert_awaited_once()
        api.close.assert_awaited_once()
    finally:
        release.set()
        session_release.set()
        await asyncio.gather(*work)


@pytest.mark.asyncio
async def test_shutdown_rejects_button_alert_and_tool_work(app_rig):
    from blooglyblob.ai.tool_bridge import StaleResponse

    app, _, _, _, _ = app_rig
    await app.start()
    app._begin_shutdown()
    app.session.button = Mock()
    app.session.alert = Mock()
    app._button()
    app._alert("late timer")
    app.session.button.assert_not_called()
    app.session.alert.assert_not_called()
    with pytest.raises(StaleResponse):
        await app._executor.execute(
            "late", "moveHead", {"direction": "left"}, lambda: True
        )
    await app.stop()


@pytest.mark.asyncio
async def test_optional_scanner_missing_allows_local_readiness(app_rig):
    app, _, audio, _, ready = app_rig
    audio.prepare.side_effect = FileNotFoundError("private path")
    await app.start()
    ready.assert_called_once()
    await app.stop()


def test_stdlib_notify_uses_datagram_and_no_listener(monkeypatch, tmp_path):
    import socket
    from unittest.mock import MagicMock
    from blooglyblob.application import notify_ready

    channel = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = channel
    monkeypatch.setattr(socket, "socket", factory)
    monkeypatch.setenv("NOTIFY_SOCKET", "@systemd-test")
    notify_ready()
    factory.assert_called_once_with(socket.AF_UNIX, socket.SOCK_DGRAM)
    channel.settimeout.assert_called_once_with(1.0)
    channel.connect.assert_called_once_with("\0systemd-test")
    channel.sendall.assert_called_once_with(b"READY=1")
    channel.bind.assert_not_called()
    channel.listen.assert_not_called()


@pytest.mark.parametrize("service", [False, True])
@pytest.mark.parametrize("stuck", ["executor", "startup", "loop_teardown"])
def test_process_deadline_covers_stuck_python_workers_and_cancellation(
    tmp_path, service, stuck
):
    import os
    from pathlib import Path
    import subprocess
    import sys

    program = r"""
import asyncio, threading
from concurrent.futures import ThreadPoolExecutor
from blooglyblob.application import Application
from blooglyblob.config import AIConfig
from blooglyblob.__main__ import run_application
app = Application(config=AIConfig(openai_api_key='offline'), shutdown_seconds=.12)
async def forever():
    while True:
        try: await asyncio.Event().wait()
        except asyncio.CancelledError: pass
async def start():
    app._pool = ThreadPoolExecutor(max_workers=4)
    if MODE == 'executor':
        app._workers.add(app._pool.submit(threading.Event().wait))
        app._shutdown_requested()
    elif MODE == 'startup':
        asyncio.get_running_loop().call_later(.01, app._shutdown_requested)
        await forever()
    else:
        asyncio.create_task(asyncio.to_thread(threading.Event().wait))
        await asyncio.sleep(.01)
        app._shutdown_requested()
app.start = start
run_application(app, shutdown_seconds=.3)
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    if service:
        env["NOTIFY_SOCKET"] = str(tmp_path / "service-notify")
    else:
        env.pop("NOTIFY_SOCKET", None)
    result = subprocess.run(
        [sys.executable, "-c", "MODE=" + repr(stuck) + "\n" + program],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert result.returncode == 73, result.stderr
    assert "ownership unconfirmed" in result.stderr


@pytest.mark.asyncio
async def test_real_application_session_media_audio_chain(monkeypatch, app_rig):
    """Only native/cloud boundaries are fakes; the entire application chain runs."""
    from tests.support.audio import Driver
    from tests.support.conversation import Live
    from tests.support.asyncio import wait_until
    from blooglyblob.audio.controller import AudioController
    from blooglyblob.hardware.controller import HardwareController

    app, _, _, _, ready = app_rig
    drivers = []

    def driver():
        item = Driver()
        drivers.append(item)
        return item

    def audio_factory(**kwargs):
        audio = AudioController(driver_factory=driver, **kwargs)
        audio.check_devices = AsyncMock()  # Native PortAudio enumeration boundary.
        return audio

    button = SimpleNamespace(when_pressed=None, close=Mock())
    app._audio_factory = audio_factory
    app._hardware_factory = lambda audio, **kwargs: HardwareController(
        audio,
        servo_factory=lambda: None,
        led_factory=lambda **_: None,
        ambient_factory=lambda **_: None,
        button_factory=lambda: button,
        **kwargs,
    )
    await app.start()
    ready.assert_called_once()
    assert app.audio.diagnostics is app.diagnostics
    assert app.session.diagnostics is app.diagnostics
    assert not drivers
    app.session.live_factory = Live
    app.session.voice_effect_factory = lambda: SimpleNamespace(
        process=lambda pcm: pcm, finish=lambda: b""
    )
    app.session.greeting = "Hello!"
    greeting_started, greeting_finish = asyncio.Event(), asyncio.Event()

    async def speak(text, output, **options):
        assert options == {"speed": 1.25}
        greeting_started.set()
        await output(bytes(960))
        await greeting_finish.wait()

    app.session.speech.speak = speak
    button.when_pressed()
    await greeting_started.wait()
    live = app.session.live
    drivers[0].on_input(bytes(640))
    await asyncio.sleep(0.01)
    live.input_audio.assert_not_awaited()
    greeting_finish.set()
    await wait_until(lambda: app.session._accept_live_input)
    assert len(drivers) == 1  # Greeting drain hands off without restarting capture.
    drivers[0].on_input(bytes(640))
    await wait_until(lambda: live.input_audio.await_count == 1)
    async with app.session.media.search_sound(lambda: True):
        await live.callbacks["on_audio"](bytes(960))
        drivers[0].on_input(bytes(640))
        await wait_until(lambda: live.input_audio.await_count == 2)
    await live.callbacks["on_audio"](bytes(960))
    button.when_pressed()
    await wait_until(lambda: not app.session.active)
    await app.session._runner
    assert drivers[0].stopped
    before = len(drivers[0].out_stream.frames)
    await live.callbacks["on_audio"](bytes(960))
    assert len(drivers[0].out_stream.frames) == before
    await app.stop()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "activity", ["idle", "conversation", "dance", "alert", "sleep"]
)
async def test_shutdown_from_every_activity_closes_all_owners(app_rig, activity):
    from tests.support.conversation import Live

    app, api, audio, hardware, _ = app_rig
    await app.start()
    app.session.live_factory = Live
    app.session.greeting = ""
    hardware.execute.return_value = (
        "Dance mode starting" if activity == "dance" else "Going to sleep"
    )
    if activity == "alert":
        app._alert("Timer done!")
    elif activity != "idle":
        app.session._request_activity(activity)
    await asyncio.sleep(0.01)
    await app.stop()
    assert not app.session.active
    hardware.close.assert_awaited_once()
    audio.close.assert_awaited_once()
    api.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_audio_selection_never_prepares_hardware_or_notifies(app_rig):
    app, api, audio, hardware, ready = app_rig
    audio.check_devices.side_effect = RuntimeError("private device detail")
    with pytest.raises(RuntimeError):
        await app.start()
    hardware.prepare.assert_not_awaited()
    ready.assert_not_called()
    audio.close.assert_awaited_once()
    api.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_startup_deadline_fences_late_initializer_without_waiting_for_cancel(
    monkeypatch, app_rig
):
    import blooglyblob.application as module
    from blooglyblob.application import OwnershipUncertain

    app, api, audio, hardware, ready = app_rig
    monkeypatch.setattr(module, "STARTUP_SECONDS", 0.02)
    finish = asyncio.Event()
    entered = asyncio.Event()

    async def check():
        entered.set()
        try:
            await finish.wait()
        except asyncio.CancelledError:
            await finish.wait()

    audio.check_devices.side_effect = check
    app.shutdown_seconds = 0.1
    armed = Mock()
    app._on_shutdown = armed
    running = asyncio.create_task(app.run_forever())
    await entered.wait()
    try:
        with pytest.raises(OwnershipUncertain):
            await asyncio.wait_for(running, 0.4)
        armed.assert_called_once()
        hardware.prepare.assert_not_awaited()
        ready.assert_not_called()
        api.close.assert_awaited_once()
    finally:
        finish.set()
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_optional_roku_discovery_runs_off_loop_before_readiness(
    monkeypatch, app_rig
):
    import threading
    import blooglyblob.tools.roku_controller as roku

    app, _, _, _, ready = app_rig
    loop_thread = threading.get_ident()
    entered = threading.Event()
    release = threading.Event()

    class Discovery:
        def __init__(self, address):
            assert threading.get_ident() != loop_thread, (
                "Roku discovery blocked the application loop"
            )
            entered.set()
            assert release.wait(1)

    monkeypatch.setenv("ROKU_IP", "192.0.2.1")
    monkeypatch.setattr(roku, "RokuController", Discovery)
    starting = asyncio.create_task(app.start())
    try:
        for _ in range(100):
            if entered.is_set() or starting.done():
                break
            await asyncio.sleep(0.001)
        if starting.done():
            await starting
        assert entered.is_set()
        ready.assert_not_called()
        release.set()
        await starting
        ready.assert_called_once()
    finally:
        release.set()
        await app.stop()


@pytest.mark.asyncio
async def test_shutdown_waits_within_deadline_for_actual_integration_completion(
    app_rig,
):
    import threading

    app, _, _, _, _ = app_rig
    await app.start()
    app.shutdown_seconds = 0.3
    entered, finish = threading.Event(), threading.Event()

    def integration():
        entered.set()
        finish.wait(1)

    work = asyncio.create_task(app._work(integration))
    while not entered.is_set():
        await asyncio.sleep(0.001)
    asyncio.get_running_loop().call_later(0.03, finish.set)
    try:
        await app.stop()
        assert work.done()
        assert not app._faulted
    finally:
        finish.set()
        await work


@pytest.mark.asyncio
async def test_offline_boot_suppresses_all_starts_and_recovers_without_replay(app_rig):
    from tests.support.conversation import Live
    from tests.support.asyncio import wait_until

    app, _, audio, hardware, ready = app_rig
    app._connectivity_probe.return_value = False
    await app.start()
    ready.assert_called_once()
    app.session.live_factory = Live
    app.session.greeting = ""
    for _ in range(3):
        app._button()
        app._alert("timer")
        app.session.request(True)
    assert not app.session.active and app.session.live is None
    assert hardware.lighting.snapshot(100).mode == "unavailable"
    hardware.present.assert_not_called()
    hardware.chime.assert_not_awaited()
    app._speech.prepare.assert_not_awaited()
    audio.begin.assert_not_awaited()
    app._connectivity_probe.return_value = True
    await app.availability.check()
    assert not app.availability.ready
    await app.availability.check()
    assert app.availability.ready
    assert not app.session.active
    hardware.present.assert_not_called()
    app._button()
    await wait_until(lambda: app.session.live_connected)
    assert app.session.active
    await app.stop()


@pytest.mark.asyncio
async def test_active_network_failure_mutes_fences_and_recovers_only_to_idle(app_rig):
    from blooglyblob.ai.live import LiveSessionError
    from tests.support.conversation import Live
    from tests.support.asyncio import wait_until

    app, _, audio, hardware, _ = app_rig
    await app.start()
    app.session.live_factory = Live
    app.session.greeting = ""
    app._button()
    await wait_until(lambda: app.session.live_connected)
    old = app.session.live
    await old.callbacks["on_error"](
        LiveSessionError("connection lost", category="network")
    )
    await app.session._runner
    assert not app._faulted
    assert not app.availability.ready and not app.session.active
    assert hardware.lighting.snapshot(100).mode == "unavailable"
    audio.mute.assert_called()
    audio.audio.reset_mock()
    await old.callbacks["on_audio"](bytes(960))
    audio.audio.assert_not_awaited()
    app._alert("missed timer")
    hardware.chime.assert_not_awaited()
    await app.availability.check()
    await app.availability.check()
    assert app.availability.ready and not app.session.active
    assert hardware.lighting.snapshot(100).mode == "sleeping"
    app._button()
    await wait_until(lambda: app.session.live_connected)
    assert app.session.live is not old
    await app.stop()


@pytest.mark.asyncio
async def test_provider_error_during_startup_cleanup_does_not_cancel_its_own_close(
    app_rig,
):
    from blooglyblob.ai.live import OpenAILiveSession
    from tests.support.live import FakeConnection
    from tests.support.asyncio import wait_until

    app, _, _, _, _ = app_rig
    await app.start()
    connection = FakeConnection()
    manager = AsyncMock()
    manager.__aenter__.return_value = connection
    app.session.api = SimpleNamespace(
        live=SimpleNamespace(connect=Mock(return_value=manager))
    )
    app.session.live_factory = OpenAILiveSession
    app.session.greeting = ""
    app._button()
    await wait_until(lambda: connection.session.start.await_count == 1)
    await connection.events.put(
        SimpleNamespace(type="error", error=SimpleNamespace(code="invalid_api_key"))
    )
    await wait_until(lambda: not app.session.active)
    await app.session._runner
    try:
        assert app.availability.reason == "auth"
        assert not app._faulted and not app._stopping
        manager.__aexit__.assert_awaited_once()
    finally:
        await app.stop()


@pytest.mark.asyncio
async def test_prefetch_auth_failure_stays_inactive_despite_reachable_internet(app_rig):
    from blooglyblob.ai.speech import SpeechError
    from tests.support.asyncio import wait_until

    app, _, _, hardware, _ = app_rig
    app._speech.prepare.side_effect = SpeechError("denied", category="auth")
    await app.start()
    await wait_until(lambda: app.availability.reason == "auth")
    await app.availability.check()
    app._button()
    assert not app.session.active
    assert hardware.lighting.snapshot(100).mode == "unavailable"
    assert not app._faulted
    await app.stop()


@pytest.mark.asyncio
async def test_shutdown_reports_measurements_recorded_during_audio_close(caplog):
    import json
    import logging
    from blooglyblob.application import Application

    app = Application(config=AIConfig(openai_api_key="fake"))

    async def close_audio():
        app.diagnostics.count("capture_samples", 123)

    app.audio = SimpleNamespace(mute=Mock(), close=AsyncMock(side_effect=close_audio))
    with caplog.at_level(logging.INFO, logger="blooglyblob.audio.diagnostics"):
        await app.stop()
    summaries = [
        r.message for r in caplog.records if r.name == "blooglyblob.audio.diagnostics"
    ]
    assert len(summaries) == 1
    assert json.loads(summaries[0].removeprefix("Audio diagnostics: "))["counts"] == {
        "capture_samples": 123
    }


@pytest.mark.asyncio
async def test_cancelled_backend_parser_remains_owned_until_worker_finishes(app_rig):
    import threading
    from tests.support.asyncio import wait_until

    app, api, audio, _, _ = app_rig
    entered, release = threading.Event(), threading.Event()

    def parse():
        entered.set()
        assert release.wait(2), "test did not release parser"
        return SimpleNamespace(status="completed", output=[], usage=None)

    api.responses.with_raw_response = SimpleNamespace(
        create=AsyncMock(return_value=SimpleNamespace(parse=parse))
    )
    await app.start()
    engine = app.session.responses
    request = asyncio.create_task(engine.run([], lambda: True))
    stopping = None
    try:
        await wait_until(entered.is_set)
        request.cancel()
        with pytest.raises(asyncio.CancelledError):
            await request
        assert any(not worker.done() for worker in app._workers)
        stopping = asyncio.create_task(app.stop())
        await asyncio.sleep(0.01)
        assert not stopping.done()
        release.set()
        await stopping
        await wait_until(lambda: not engine._pending_tasks)
        assert not app._faulted
        audio.close.assert_awaited_once()
    finally:
        release.set()
        await asyncio.gather(request, *(engine._pending_tasks), return_exceptions=True)
        if stopping is not None:
            await stopping
        else:
            await app.stop()
