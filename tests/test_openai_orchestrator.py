"""Startup, readiness and import-isolation coverage for the single application."""

import asyncio
import os
from pathlib import Path
import subprocess
import sys
import threading
from unittest.mock import Mock

import pytest
from tests.support.application import app_rig as app_rig
from blooglyblob.ai.responses import prepare_responses as real_prepare_responses


@pytest.mark.asyncio
async def test_response_sdk_is_prepared_before_accepting_audio(monkeypatch, app_rig):
    import openai
    from openai.types.responses import Response
    import blooglyblob.ai.responses as responses

    app, _, audio, _, ready = app_rig
    from openai import AsyncClient

    actual = AsyncClient(api_key="offline")
    monkeypatch.setattr(openai, "AsyncOpenAI", Mock(return_value=actual))
    monkeypatch.setattr(responses, "prepare_responses", real_prepare_responses)

    async def check_devices():
        assert "responses" in actual.__dict__
        assert Response.__pydantic_complete__
        ready.assert_not_called()

    audio.check_devices.side_effect = check_devices
    try:
        await app.start()
        ready.assert_called_once()
    finally:
        await app.stop()
    assert actual.is_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["ready", "failure", "cancel"])
async def test_sdk_preparation_keeps_startup_responsive_and_never_opens_early(
    monkeypatch, app_rig, outcome
):
    import blooglyblob.ai.responses as responses
    from blooglyblob.application import OwnershipUncertain

    app, api, audio, _, ready = app_rig
    entered, finished = asyncio.Event(), asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()

    def prepare(client):
        assert client is api
        loop.call_soon_threadsafe(entered.set)
        try:
            assert release.wait(2)
            if outcome == "failure":
                raise RuntimeError("SDK preparation failed")
        finally:
            loop.call_soon_threadsafe(finished.set)

    monkeypatch.setattr(responses, "prepare_responses", prepare)
    starting = asyncio.create_task(app.start())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert not starting.done()
        audio.check_devices.assert_not_awaited()
        ready.assert_not_called()
        if outcome == "cancel":
            app.shutdown_seconds = 0.1
            starting.cancel()
            with pytest.raises((asyncio.CancelledError, OwnershipUncertain)):
                await starting
            release.set()
            await finished.wait()
            audio.check_devices.assert_not_awaited()
            ready.assert_not_called()
        else:
            release.set()
            if outcome == "failure":
                with pytest.raises(RuntimeError, match="SDK preparation failed"):
                    await starting
                ready.assert_not_called()
            else:
                await starting
                ready.assert_called_once()
                await app.stop()
        api.close.assert_awaited_once()
    finally:
        release.set()
        await asyncio.wait_for(finished.wait(), 1)


def test_application_imports_and_direct_start_do_not_load_old_packages_or_native_drivers(
    tmp_path,
):
    root = Path(__file__).resolve().parents[1]
    program = r"""
import asyncio, importlib.abc, sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
class DenyOld(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'server','client','pi','pyaudio','gpiozero','pigpio','anthropic','torch','voicebox','pvporcupine'}:
            raise AssertionError('Unexpected import: '+fullname)
sys.meta_path.insert(0, DenyOld())
from blooglyblob.application import Application
from blooglyblob.config import AIConfig
from blooglyblob.audio.controller import AudioController
from blooglyblob.hardware.controller import HardwareController
from tests.support.conversation import Audio, Hardware, Live
async def main():
    audio=Audio()
    audio.check_devices=AsyncMock(); audio.prepare=AsyncMock(); audio.close=AsyncMock()
    hardware=Hardware(audio)
    hardware.prepare=AsyncMock(); hardware.close=AsyncMock(); hardware.search_path='unused'
    api=SimpleNamespace(close=AsyncMock(), responses=SimpleNamespace())
    with patch('openai.AsyncOpenAI', return_value=api), patch('blooglyblob.ai.responses.prepare_responses'), patch('blooglyblob.tools.timer_manager.TimerManager.start'):
        app=Application(config=AIConfig(openai_api_key='offline'), audio_factory=lambda **kw: audio,
            hardware_factory=lambda *args,**kw: hardware, ready=lambda: None,
            connectivity_probe=AsyncMock(return_value=True))
        app._speech=SimpleNamespace(prepare=AsyncMock(), speak=AsyncMock())
        await app.start()
        app.session.live_factory=Live; app.session.greeting=''
        app._button()
        await asyncio.sleep(.01)
        await app._audio_input(bytes(640))
        app._alert('Timer done!')
        await asyncio.sleep(.01)
        assert app.session.activity=='alert'
        app._button()
        await app.session._runner
        await app.stop()
        api.close.assert_awaited_once()
asyncio.run(main())
"""
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "OPENAI_API_KEY",
            "TMDB_API_KEY",
            "WATCHMODE_API_KEY",
            "ROKU_IP",
            "RING_TOKEN",
            "NOTIFY_SOCKET",
            "OPENAI_INACTIVITY_SECONDS",
            "OPENAI_SESSION_MAX_SECONDS",
        }
    }
    env["PYTHONPATH"] = str(root) + os.pathsep + str(root / "tests")
    env["BLOOGLYBLOB_STATE_DIR"] = str(tmp_path / "state")
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
