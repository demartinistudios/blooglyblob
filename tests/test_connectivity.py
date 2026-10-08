"""Admission and probe contracts without real network requests."""

import asyncio
from unittest.mock import AsyncMock, Mock

import aiohttp
import pytest

from blooglyblob.connectivity import Availability, ReachabilityProbe, failure_category


@pytest.mark.asyncio
async def test_boot_failure_and_recovery_require_fresh_admission():
    changed = Mock()
    monitor = Availability(probe=AsyncMock(return_value=False), changed=changed)
    assert not monitor.ready
    await monitor.check()
    assert monitor.reason == "network"
    monitor.probe.return_value = True
    await monitor.check()
    assert not monitor.ready
    await monitor.check()
    assert monitor.ready
    changed.assert_called_once_with(True)
    monitor.probe.return_value = False
    await monitor.check()
    assert monitor.ready
    await monitor.check()
    assert not monitor.ready
    assert changed.call_args.args == (False,)


@pytest.mark.asyncio
async def test_initial_success_is_enough_but_auth_failure_is_latched():
    monitor = Availability(probe=AsyncMock(return_value=True), changed=Mock())
    await monitor.check()
    assert monitor.ready
    monitor.fail("auth")
    for _ in range(3):
        await monitor.check()
    assert not monitor.ready and monitor.reason == "auth"
    assert monitor.probe.await_count == 1


@pytest.mark.asyncio
async def test_late_probe_cannot_clear_session_failure_or_override_healthy_live():
    entered, finish = asyncio.Event(), asyncio.Event()

    async def probe():
        entered.set()
        await finish.wait()
        return True

    busy = Mock(return_value=False)
    monitor = Availability(probe=probe, changed=Mock(), live_connected=busy)
    task = asyncio.create_task(monitor.check())
    await entered.wait()
    monitor.fail("network")
    finish.set()
    await task
    assert not monitor.ready and monitor._successes == 0
    busy.return_value = True
    await monitor.check()
    assert not monitor.ready


@pytest.mark.asyncio
async def test_service_cooldown_survives_failed_network_check():
    clock = Mock(return_value=0)
    monitor = Availability(
        probe=AsyncMock(return_value=True), changed=Mock(), clock=clock
    )
    await monitor.check()
    monitor.fail("service")
    monitor.probe.return_value = False
    await monitor.check()
    monitor.probe.return_value = True
    await monitor.check()
    await monitor.check()
    assert not monitor.ready
    clock.return_value = 31
    await monitor.check()
    assert monitor.ready


@pytest.mark.asyncio
async def test_monitor_cancellation_closes_inflight_probe():
    entered, closed = asyncio.Event(), asyncio.Event()

    async def probe():
        try:
            entered.set()
            await asyncio.Event().wait()
        finally:
            closed.set()

    monitor = Availability(probe=probe, changed=Mock())
    task = asyncio.create_task(monitor.run())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()


@pytest.mark.asyncio
async def test_probe_accepts_only_expected_json_status_without_credentials(monkeypatch):
    from types import SimpleNamespace
    from contextlib import asynccontextmanager

    calls = []
    response = SimpleNamespace(status=401, content_type="application/json")

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["timeout"].total == 3

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        @asynccontextmanager
        async def get(self, url, **kwargs):
            calls.append((url, kwargs))
            yield response

    monkeypatch.setattr(aiohttp, "ClientSession", Client)
    probe = ReachabilityProbe("https://api.openai.com/v1/?private=ignored")
    assert await probe()
    assert calls == [("https://api.openai.com/v1/models", {"allow_redirects": False})]
    for status, content_type in [
        (302, "application/json"),
        (503, "application/json"),
        (200, "text/html"),
    ]:
        response.status, response.content_type = status, content_type
        assert not await probe()


def test_error_categories_never_need_provider_message():
    import httpx2
    from openai import AuthenticationError, RateLimitError, APIConnectionError

    response = httpx2.Response(
        401, request=httpx2.Request("GET", "https://example.com")
    )
    assert (
        failure_category(AuthenticationError("private", response=response, body=None))
        == "auth"
    )
    response.status_code = 429
    assert (
        failure_category(RateLimitError("private", response=response, body=None))
        == "service"
    )
    assert failure_category(APIConnectionError(request=response.request)) == "network"
    assert failure_category(TimeoutError()) == "network"
    assert failure_category(ValueError()) is None


def test_dns_and_sdk_disconnect_are_recoverable_without_parsing_messages():
    import socket
    from openai import WebSocketConnectionClosedError

    assert failure_category(socket.gaierror("private hostname")) == "network"
    assert (
        failure_category(WebSocketConnectionClosedError("private", unsent_messages=[]))
        == "network"
    )
