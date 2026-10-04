"""Logs retain operational signals without copying tool content or secrets."""

import json
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from blooglyblob.hardware.controller import HardwareController
from blooglyblob.audio.presentation import OutputPresentation
from blooglyblob.tools import ring_handler, roku_controller
from blooglyblob.tools.timer_manager import TimerManager
from blooglyblob.tools.handlers import ToolHandlers


PRIVATE = "private-content-example-731"


def test_timer_content_survives_results_storage_and_callback_but_not_logs(
    tmp_path, capsys
):
    callback = Mock(side_effect=RuntimeError(PRIVATE))
    manager = TimerManager(callback, str(tmp_path))
    tools = ToolHandlers(timer_manager=manager)
    assert PRIVATE in tools.set_timer({"duration_seconds": 60, "label": PRIVATE})
    assert PRIVATE in tools.find_timers({"queries": [PRIVATE]})
    assert PRIVATE in manager._timers_file.read_text()
    entry = manager.get_active_timers()[0]
    manager._fire_timer(entry)
    callback.assert_called_once_with(entry)
    assert entry.label == PRIVATE
    assert tools.cancel_timer({"timer_id": PRIVATE}) == "Timer not found"
    assert manager.cancel_timer(entry.id)
    output = capsys.readouterr().out
    assert PRIVATE not in output
    assert "setTimer" in output and "findTimers" in output
    assert "RuntimeError" in output and "Firing" in output


@pytest.mark.asyncio
async def test_tool_arguments_are_not_printed_even_on_invalid_calls(capsys):
    tools = ToolHandlers()
    assert "Error" in tools.stream_content({"title": PRIVATE})
    assert "Error" in tools.roku_control({"action": PRIVATE})
    device = HardwareController(SimpleNamespace(presentation=OutputPresentation()))
    assert await device.execute("goToSleep", {"label": PRIVATE}) == "Going to sleep"
    assert "Unknown tool" in await device.execute(PRIVATE, {})
    output = capsys.readouterr().out
    assert PRIVATE not in output
    assert "streamContent" in output and "rokuControl" in output


@pytest.mark.parametrize("failure", [False, True])
def test_roku_logs_hide_content_and_exception_text(monkeypatch, caplog, failure):
    controller = roku_controller.RokuController.__new__(roku_controller.RokuController)
    controller.roku_ip = "192.0.2.20"
    controller.roku = Mock()
    controller.channel_ids = {PRIVATE: SimpleNamespace(id=PRIVATE, launch=Mock())}
    post = Mock(return_value=SimpleNamespace(status_code=200))
    if failure:
        post.side_effect = RuntimeError(f"{PRIVATE}?api_key={PRIVATE}")
        controller.channel_ids[PRIVATE].launch.side_effect = RuntimeError(PRIVATE)
    monkeypatch.setattr(roku_controller.requests, "post", post)
    with caplog.at_level(logging.DEBUG, logger=roku_controller.__name__):
        assert controller.launch_with_content(PRIVATE, PRIVATE, "movie") is not failure
        assert post.call_args.kwargs["params"]["contentId"] == PRIVATE
        assert controller.launch_app(PRIVATE) is not failure
        assert controller._get_app(PRIVATE + "-missing") is None
    assert PRIVATE not in caplog.text
    assert "launch" in caplog.text.lower()
    if failure:
        assert "RuntimeError" in caplog.text


class Response:
    def __init__(self, payload=None, error=None, status=200):
        self.payload, self.error, self.status = payload, error, status

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *args):
        return False

    async def json(self):
        return self.payload


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["none", "connection", "poll", "http"])
async def test_ring_logs_hide_device_identity_and_exception_text(
    monkeypatch, capsys, failure
):
    callback = Mock()
    handler = ring_handler.RingHandler(callback, debounce_seconds=0)
    handler._running.set()
    monkeypatch.setenv("RING_TOKEN", json.dumps({"access_token": PRIVATE}))
    # Invoke the callback synchronously; no background worker or device needed.
    monkeypatch.setattr(
        ring_handler.threading,
        "Thread",
        lambda target, **kw: SimpleNamespace(start=target),
    )
    monkeypatch.setattr(ring_handler, "MAX_RETRY_ATTEMPTS", 1)

    async def stop_after_poll(_):
        handler._running.clear()

    monkeypatch.setattr(ring_handler.asyncio, "sleep", stop_after_poll)
    devices = Response(
        {"doorbots": [{"description": PRIVATE, "id": PRIVATE}]},
        error=RuntimeError(PRIVATE) if failure == "connection" else None,
    )
    dings = Response(
        [{"kind": "ding", "id": 1, "doorbot_description": PRIVATE}],
        error=RuntimeError(PRIVATE) if failure == "poll" else None,
        status=401 if failure == "http" else 200,
    )
    session = Response()
    session.get = Mock(side_effect=[devices, dings])
    monkeypatch.setattr(ring_handler.aiohttp, "ClientSession", lambda: session)
    await handler._poll_loop()
    assert (
        session.get.call_args_list[0].kwargs["headers"]["Authorization"]
        == f"Bearer {PRIVATE}"
    )
    assert callback.call_count == (1 if failure == "none" else 0)
    output = capsys.readouterr().out
    assert PRIVATE not in output
    if failure in {"connection", "poll"}:
        assert "RuntimeError" in output
    elif failure == "http":
        assert "401" in output
    else:
        assert "1 doorbell" in output and "Ding detected" in output
