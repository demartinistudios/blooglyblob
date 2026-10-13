"""Offline effect-boundary evidence through real executor/bridge owners."""

import asyncio
import threading
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from blooglyblob.ai.tool_bridge import OpenAIToolBridge, StaleResponse
from blooglyblob.hardware.controller import HardwareController
from blooglyblob.hardware.local_media import Worker
from blooglyblob.tools.content_search import ContentSearch, ContentResult
from blooglyblob.tools.execution_scope import ExecutionScope, execution_scope
from blooglyblob.tools.executor import ToolExecutor
from blooglyblob.tools.handlers import ToolHandlers, create_stream_content_handler
from blooglyblob.tools.outcomes import NotDispatched
from blooglyblob.tools.registry import ToolRegistry
from blooglyblob.tools.roku_controller import RokuController


async def wait_event(event):
    async with asyncio.timeout(2):
        while not event.is_set():
            await asyncio.sleep(0.001)


async def test_busy_motion_is_audible_refusal_and_new_call_can_succeed():
    hardware = HardwareController(MagicMock(), admission_timeout=0.02)
    hardware.servos = MagicMock()
    executor = ToolExecutor(hardware=hardware, handlers=None, terminal=AsyncMock())
    registry = ToolRegistry()
    registry.load_from_configs()
    bridge = OpenAIToolBridge(
        registry,
        lambda ident, name, params: executor.execute(ident, name, params, lambda: True),
    )
    hardware.animation_lock.acquire()
    try:
        began = time.monotonic()
        refused = await bridge.execute(
            "busy", "moveHead", '{"direction":"left"}', lambda: True
        )
        assert isinstance(refused, NotDispatched)
        assert str(refused).startswith("Error:")
        assert time.monotonic() - began < 0.5
        hardware.servos.head.look_left.assert_not_called()
    finally:
        hardware.animation_lock.release()
    assert (
        await bridge.execute("busy", "moveHead", '{"direction":"left"}', lambda: True)
        == refused
    )
    assert (
        await bridge.execute("next", "moveHead", '{"direction":"left"}', lambda: True)
        == "Moving head left"
    )
    await hardware.wait_gestures()
    hardware.servos.head.look_left.assert_called_once()
    executor.close()


async def test_motion_waits_briefly_for_admission_and_rechecks_freshness():
    hardware = HardwareController(MagicMock(), admission_timeout=0.2)
    hardware.servos = MagicMock()
    hardware.animation_lock.acquire()
    task = asyncio.create_task(hardware.execute("moveHead", {"direction": "left"}))
    await asyncio.sleep(0.02)
    hardware.servos.head.look_left.assert_not_called()
    hardware.animation_lock.release()
    assert await task == "Moving head left"
    await hardware.wait_gestures()
    hardware.servos.reset_mock()
    hardware.animation_lock.acquire()
    current = True
    task = asyncio.create_task(
        hardware.execute("moveHead", {"direction": "left"}, is_current=lambda: current)
    )
    await asyncio.sleep(0.02)
    current = False
    hardware.animation_lock.release()
    assert isinstance(await task, NotDispatched)
    hardware.servos.head.look_left.assert_not_called()


@pytest.mark.parametrize("cancel", [False, True])
async def test_motion_rechecks_at_delayed_actual_worker_start(monkeypatch, cancel):
    release, entered = threading.Event(), threading.Event()

    def delayed_worker(operation, name):
        def delayed():
            entered.set()
            assert release.wait(2)
            operation()

        return Worker(delayed, name)

    monkeypatch.setattr("blooglyblob.hardware.controller.Worker", delayed_worker)
    hardware = HardwareController(MagicMock())
    hardware.servos = MagicMock()
    current = True
    executor = ToolExecutor(hardware=hardware, handlers=None, terminal=AsyncMock())
    task = asyncio.create_task(
        executor.execute("1", "moveHead", {"direction": "left"}, lambda: current)
    )
    try:
        await wait_event(entered)
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            current = False
        release.set()
        if not cancel:
            assert isinstance(await task, NotDispatched)
        await hardware.wait_gestures()
        hardware.servos.head.look_left.assert_not_called()
        assert not hardware.animation_lock.locked()
    finally:
        release.set()
        executor.close()


async def test_cancelled_lookup_cannot_dispatch_even_when_outer_owner_stays_current():
    entered, release = threading.Event(), threading.Event()
    content, roku = MagicMock(), MagicMock()

    def lookup(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return ContentResult(1, "Title", "movie", 2000)

    content.search.side_effect = lookup
    content.get_streaming_links.return_value = {"netflix": {"content_id": "1"}}
    executor = ToolExecutor(
        hardware=None,
        handlers=ToolHandlers(content, roku),
        terminal=AsyncMock(),
        concurrency=1,
    )
    task = asyncio.create_task(
        executor.execute("1", "streamContent", {"title": "Title"}, lambda: True)
    )
    try:
        await wait_event(entered)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert executor.pending
        release.set()
        await executor.wait_closed(2)
        roku.launch_with_content.assert_not_called()
        roku.launch_app.assert_not_called()
    finally:
        release.set()
        executor.close()


@pytest.mark.parametrize("select_success", [False, True])
def test_netflix_checks_after_delay_and_reports_select_failure(
    monkeypatch, select_success
):
    controller = RokuController.__new__(RokuController)
    controller.roku_ip, controller.roku = "192.0.2.1", MagicMock()
    controller.channel_ids = {"netflix": SimpleNamespace(id=12)}
    post = MagicMock(return_value=SimpleNamespace(status_code=200))
    monkeypatch.setattr("blooglyblob.tools.roku_controller.requests.post", post)
    scope = ExecutionScope(lambda: True, time.monotonic() + 30)
    monkeypatch.setattr(
        "blooglyblob.tools.roku_controller.time.sleep", lambda _: scope.cancelled.set()
    )
    with execution_scope(scope), pytest.raises(StaleResponse):
        controller.launch_with_content("netflix", "123", "movie")
    assert post.call_count == 1  # Launch already happened; it cannot be undone.
    controller.roku.select.assert_not_called()
    monkeypatch.setattr("blooglyblob.tools.roku_controller.time.sleep", lambda _: None)
    controller.select = MagicMock(return_value=select_success)
    assert controller.launch_with_content("netflix", "123", "movie") is select_success


def test_uncertain_deep_link_never_falls_back_to_another_command():
    content, roku = MagicMock(), MagicMock()
    content.search.return_value = ContentResult(1, "Title", "movie", 2000)
    content.get_streaming_links.return_value = {"netflix": {"content_id": "1"}}
    roku.launch_with_content.return_value = False
    result = create_stream_content_handler(content, roku)({"title": "Title"})
    assert result.startswith("Uncertain delivery:")
    roku.launch_app.assert_not_called()


def test_provider_resolution_reuses_links_and_watchmode_payload(monkeypatch):
    content = ContentSearch("placeholder", "placeholder")
    content.search_client = SimpleNamespace(
        multi=lambda _: [
            SimpleNamespace(
                id=1, title="Title", media_type="movie", release_date="2000-01-01"
            )
        ]
    )
    urls = []

    def get(url, **kwargs):
        urls.append(url)
        if "watchmode" in url:
            payload = {
                "sources": [
                    {"source_id": 203, "web_url": "https://www.netflix.com/title/123"},
                    {"source_id": 157, "web_url": "https://www.hulu.com/movie/456"},
                ]
            }
        else:
            payload = {
                "results": {
                    "US": {"flatrate": [{"provider_id": 8}, {"provider_id": 15}]}
                }
            }
        return SimpleNamespace(status_code=200, json=lambda: payload)

    monkeypatch.setattr("blooglyblob.tools.content_search.requests.get", get)
    with execution_scope(ExecutionScope(lambda: True, time.monotonic() + 30)):
        assert content.search("Title").tmdb_id == 1
        links = content.get_streaming_links(1, "movie")
        assert links["netflix"]["content_id"] == "123"
        assert links["hulu"]["content_id"] == "456"
    assert len(urls) == 2


def test_episode_aggregate_deadline_stops_further_requests(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(
        "blooglyblob.tools.execution_scope.time.monotonic", lambda: now[0]
    )
    content = ContentSearch("placeholder")
    requests = []

    def request(method, url, **kwargs):
        requests.append(kwargs["timeout"])
        now[0] += 0.6
        payload = {"episodes": []} if "/season/" in url else {"number_of_seasons": 100}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)

    monkeypatch.setattr("blooglyblob.tools.content_search.requests.request", request)
    with (
        execution_scope(ExecutionScope(lambda: True, 1.0)),
        pytest.raises(StaleResponse),
    ):
        content.get_all_episodes(1)
    assert requests == [1.0, 0.4]


async def test_cancel_during_motion_admission_keeps_existing_owner():
    hardware = HardwareController(MagicMock(), admission_timeout=0.2)
    hardware.servos = MagicMock()
    hardware.animation_lock.acquire()
    task = asyncio.create_task(hardware.execute("moveHead", {"direction": "left"}))
    try:
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert hardware.animation_lock.locked()
        hardware.servos.head.look_left.assert_not_called()
    finally:
        hardware.animation_lock.release()


async def test_executor_cancel_during_netflix_delay_prevents_select(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    controller = RokuController.__new__(RokuController)
    controller.roku_ip, controller.roku = "192.0.2.1", MagicMock()
    controller.channel_ids = {"netflix": SimpleNamespace(id=12)}
    post = MagicMock(return_value=SimpleNamespace(status_code=200))
    monkeypatch.setattr("blooglyblob.tools.roku_controller.requests.post", post)

    def delay(_):
        entered.set()
        assert release.wait(2)

    monkeypatch.setattr("blooglyblob.tools.roku_controller.time.sleep", delay)
    content = MagicMock()
    content.search.return_value = ContentResult(1, "Title", "movie", 2000)
    content.get_streaming_links.return_value = {"netflix": {"content_id": "1"}}
    executor = ToolExecutor(
        hardware=None, handlers=ToolHandlers(content, controller), terminal=AsyncMock()
    )
    task = asyncio.create_task(
        executor.execute("1", "streamContent", {"title": "Title"}, lambda: True)
    )
    try:
        await wait_event(entered)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert executor.pending
        release.set()
        await executor.wait_closed(2)
        assert post.call_count == 1
        controller.roku.select.assert_not_called()
    finally:
        release.set()
        executor.close()


def test_real_roku_timeout_is_not_replayed_as_app_launch(monkeypatch):
    import requests

    controller = RokuController.__new__(RokuController)
    controller.roku_ip, controller.roku = "192.0.2.1", MagicMock()
    app = MagicMock()
    app.id = 12
    controller.channel_ids = {"netflix": app}
    post = MagicMock(side_effect=requests.Timeout("private-url"))
    monkeypatch.setattr("blooglyblob.tools.roku_controller.requests.post", post)
    content = MagicMock()
    content.search.return_value = ContentResult(1, "Title", "movie", 2000)
    content.get_streaming_links.return_value = {"netflix": {"content_id": "1"}}
    result = create_stream_content_handler(content, controller)({"title": "Title"})
    assert result.startswith("Uncertain delivery:")
    app.launch.assert_not_called()
    controller.roku.select.assert_not_called()
    post.assert_called_once()


async def test_motion_stage_trace_reaches_native_worker_without_arguments(caplog):
    from blooglyblob.tools.timing import begin_trace, end_trace

    hardware = HardwareController(MagicMock())
    hardware.servos = MagicMock()
    executor = ToolExecutor(hardware=hardware, handlers=None, terminal=AsyncMock())
    token = begin_trace("local-42")
    try:
        with caplog.at_level("INFO"):
            await executor.execute(
                "private-call",
                "moveHead",
                {"direction": "left", "extra": "private-payload"},
                lambda: True,
            )
            await hardware.wait_gestures()
        stages = [
            record.message
            for record in caplog.records
            if "Tool stage:" in record.message
        ]
        assert len(stages) == 2
        assert "stage=tool_admitted" in stages[0]
        assert "stage=effect_dispatch" in stages[1]
        assert all(
            "job=local-42" in message and "elapsed_ms=" in message for message in stages
        )
        assert "private-call" not in caplog.text
        assert "private-payload" not in caplog.text
    finally:
        end_trace(token)
        executor.close()


async def test_admission_deadline_also_bounds_worker_start(monkeypatch):
    release, entered = threading.Event(), threading.Event()

    def delayed_worker(operation, name):
        def delayed():
            entered.set()
            assert release.wait(2)
            operation()

        return Worker(delayed, name)

    monkeypatch.setattr("blooglyblob.hardware.controller.Worker", delayed_worker)
    hardware = HardwareController(MagicMock(), admission_timeout=0.02)
    hardware.servos = MagicMock()
    task = asyncio.create_task(hardware.execute("moveHead", {"direction": "left"}))
    try:
        await wait_event(entered)
        await asyncio.sleep(0.06)
        assert task.done(), "Admission deadline must cover worker start"
        assert isinstance(task.result(), NotDispatched)
        release.set()
        await hardware.wait_gestures()
        hardware.servos.head.look_left.assert_not_called()
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        await hardware.wait_gestures()
