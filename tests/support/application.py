from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from blooglyblob.config import AIConfig


@pytest.fixture
def app_rig(monkeypatch, tmp_path):
    import openai
    import blooglyblob.ai.responses as responses
    from blooglyblob.application import Application
    from blooglyblob.tools.timer_manager import TimerManager
    from blooglyblob.tools.ring_handler import RingHandler
    from tests.support.conversation import Audio, Hardware

    monkeypatch.setenv("BLOOGLYBLOB_STATE_DIR", str(tmp_path))
    for key in (
        "TMDB_API_KEY",
        "ROKU_IP",
        "RING_TOKEN",
        "OPENAI_INACTIVITY_SECONDS",
        "OPENAI_SESSION_MAX_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)
    api = SimpleNamespace(close=AsyncMock(), responses=SimpleNamespace())
    monkeypatch.setattr(openai, "AsyncOpenAI", Mock(return_value=api))
    monkeypatch.setattr(responses, "prepare_responses", Mock())
    monkeypatch.setattr(TimerManager, "start", Mock())
    monkeypatch.setattr(RingHandler, "start", Mock())
    audio = Audio()
    audio.check_devices, audio.prepare, audio.close = (
        AsyncMock(),
        AsyncMock(),
        AsyncMock(),
    )
    hardware = Hardware(audio)
    hardware.prepare, hardware.close = AsyncMock(), AsyncMock()
    hardware.search_path = tmp_path / "scanner.wav"
    hardware.set_level = Mock()
    ready = Mock()
    app = Application(
        config=AIConfig(openai_api_key="offline"),
        audio_factory=lambda **kwargs: audio,
        hardware_factory=lambda *args, **kwargs: hardware,
        ready=ready,
        connectivity_probe=AsyncMock(return_value=True),
    )
    app._speech = SimpleNamespace(prepare=AsyncMock(), speak=AsyncMock())
    return app, api, audio, hardware, ready
