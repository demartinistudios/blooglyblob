"""Offline validation and lifecycle contracts for the Responses/tool loop."""

import asyncio
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from blooglyblob.ai.responses import (
    OpenAIResponses,
    OpenAIResponsesError,
    ResponsesTimeout,
)
from blooglyblob.ai.tool_bridge import OpenAIToolBridge, StaleResponse
from blooglyblob.tools.registry import ToolRegistry


def registry():
    value = ToolRegistry()
    value.load_from_configs()
    return value


def response(*items, text="", status="completed"):
    output = list(items)
    if text:
        output.append(
            {
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        )
    return SimpleNamespace(
        status=status,
        output=output,
        output_text=text,
        usage=SimpleNamespace(input_tokens=11, output_tokens=3, total_tokens=14),
    )


def call(call_id="a", name="moveHead", arguments='{"direction":"left","speed":null}'):
    return {
        "type": "function_call",
        "call_id": call_id,
        "name": name,
        "arguments": arguments,
        "status": "completed",
    }


def runner(outputs, execute=None, **kwargs):
    execute = execute or AsyncMock(return_value='{"status":"started"}')
    bridge = OpenAIToolBridge(registry(), execute)
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=outputs))
    )
    engine = OpenAIResponses(
        client, instructions="Be concise.", bridge=bridge, **kwargs
    )
    return engine, client, execute


def test_schema_parity_optional_nullable_and_detached_copy():
    source = registry()
    before = copy.deepcopy(source.schemas())
    bridge = OpenAIToolBridge(source, AsyncMock())
    tools = {tool["name"]: tool for tool in bridge.tools()}
    assert set(tools) == set(source.tool_names) and len(tools) == 10
    for tool in tools.values():
        schema = tool["parameters"]
        assert tool["strict"] is True and schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
    assert tools["goToSleep"]["parameters"]["required"] == []
    speed = tools["moveHead"]["parameters"]["properties"]["speed"]
    assert "null" in speed["type"] and None in speed["enum"]
    tools["goToSleep"]["parameters"]["properties"]["oops"] = {}
    assert source.schemas() == before
    assert "oops" not in bridge.tools()[4]["parameters"]["properties"]


@pytest.mark.asyncio
async def test_optional_nulls_restore_handler_defaults_and_zero_args():
    execute = AsyncMock(return_value="ok")
    bridge = OpenAIToolBridge(registry(), execute)
    await bridge.execute(
        "one",
        "streamContent",
        json.dumps(
            {
                "title": "Bluey",
                "service": None,
                "random_episode": None,
                "episode_query": None,
            }
        ),
        lambda: True,
    )
    await bridge.execute("two", "danceMode", "{}", lambda: True)
    assert execute.await_args_list[0].args == (
        "one",
        "streamContent",
        {"title": "Bluey"},
    )
    assert execute.await_args_list[1].args == ("two", "danceMode", {})


@pytest.mark.parametrize(
    "name,args",
    [
        ("unknown", "{}"),
        ("moveHead", "{}"),
        ("moveHead", '{"direction":"up"}'),
        ("goToSleep", '{"extra":1}'),
        ("setTimer", '{"duration_seconds":true}'),
        ("setTimer", '{"duration_seconds":NaN}'),
        ("setTimer", '{"duration_seconds":0}'),
        ("streamContent", '{"title":"x","random_episode":1}'),
        ("findTimers", '{"queries":[1]}'),
        ("moveHead", '{"direction":null}'),
        ("findTimers", "[]"),
        ("findTimers", "{"),
        ("galacticScan", '{"query":""}'),
        ("moveHead", '{"direction":"left","direction":"right"}'),
        ("findTimers", '{"queries":["' + "x" * 17000 + '"]}'),
    ],
)
@pytest.mark.asyncio
async def test_invalid_arguments_never_dispatch(name, args):
    execute = AsyncMock()
    bridge = OpenAIToolBridge(registry(), execute)
    assert "error" in json.loads(await bridge.execute("a", name, args, lambda: True))
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_duplicate_ids_and_changed_arguments_do_not_repeat():
    execute = AsyncMock(return_value="started")
    bridge = OpenAIToolBridge(registry(), execute)
    first = await bridge.execute("a", "moveHead", '{"direction":"left"}', lambda: True)
    assert (
        await bridge.execute("a", "moveHead", '{"direction":"left"}', lambda: True)
        == first
    )
    assert "error" in await bridge.execute(
        "a", "moveHead", '{"direction":"right"}', lambda: True
    )
    execute.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [TimeoutError("secret"), ConnectionError("secret")])
async def test_uncertain_delivery_guards_new_call_ids(failure):
    execute = AsyncMock(side_effect=failure)
    bridge = OpenAIToolBridge(registry(), execute)
    result = await bridge.execute("a", "moveHead", '{"direction":"left"}', lambda: True)
    assert "unknown" in result and "secret" not in result
    assert "unknown" in await bridge.execute(
        "b", "moveHead", '{"direction":"left"}', lambda: True
    )
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancellation_and_late_completion_guard_effects():
    started = asyncio.Event()
    released = asyncio.Event()
    current = True

    async def execute(*args):
        started.set()
        await released.wait()
        return "started"

    bridge = OpenAIToolBridge(registry(), execute)
    pending = asyncio.create_task(
        bridge.execute("a", "moveHead", '{"direction":"left"}', lambda: current)
    )
    await started.wait()
    current = False
    released.set()
    with pytest.raises(StaleResponse):
        await pending
    current = True
    assert "unknown" in await bridge.execute(
        "b", "moveHead", '{"direction":"left"}', lambda: current
    )


@pytest.mark.asyncio
async def test_parallel_items_reasoning_round_trip_and_usage():
    reasoning = {
        "type": "reasoning",
        "id": "reason",
        "summary": [],
        "encrypted_content": "opaque",
    }
    engine, client, execute = runner(
        [
            response(reasoning, call(), call("b", "danceMode", "{}")),
            response(text="The movement started."),
        ]
    )
    assert (
        await engine.run([{"role": "user", "content": "Move and dance"}], lambda: True)
        == "The movement started."
    )
    assert execute.await_count == 2
    inputs = client.responses.create.await_args_list[1].kwargs["input"]
    assert reasoning in inputs
    assert [
        item["call_id"] for item in inputs if item.get("type") == "function_call_output"
    ] == ["a", "b"]
    for request in client.responses.create.await_args_list:
        assert request.kwargs["store"] is False
        assert request.kwargs["max_output_tokens"] <= 2000
        assert request.kwargs["reasoning"] == {"effort": "low"}
        assert request.kwargs["include"] == ["reasoning.encrypted_content"]
    assert engine.usage == {"input_tokens": 22, "output_tokens": 6, "total_tokens": 28}


@pytest.mark.asyncio
async def test_web_search_uses_only_openai_never_legacy_dispatch():
    engine, client, execute = runner(
        [
            response(call("a", "galacticScan", '{"query":"weather"}')),
            response(text="It is raining, according to the forecast."),
            response(text="Rain is forecast."),
        ]
    )
    assert await engine.run([], lambda: True) == "Rain is forecast."
    execute.assert_not_awaited()
    search_request = client.responses.create.await_args_list[1].kwargs
    assert search_request["tools"] == [{"type": "web_search"}]
    assert search_request["tool_choice"] == "required"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "output",
    [
        response(call(), status="incomplete"),
        response({**call(), "status": "in_progress"}),
        response(text="x" * 401),
    ],
)
async def test_incomplete_and_overlong_results_fail_closed(output):
    engine, _client, execute = runner([output])
    with pytest.raises(OpenAIResponsesError):
        await engine.run([], lambda: True)
    execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_correction_between_parallel_calls_stops_next_effect():
    current = True

    async def execute(*args):
        nonlocal current
        current = False
        return "started"

    action = AsyncMock(side_effect=execute)
    engine, _client, _ = runner([response(call(), call("b"))], execute=action)
    with pytest.raises(StaleResponse):
        await engine.run([], lambda: current)
    action.assert_awaited_once()


@pytest.mark.asyncio
async def test_total_deadline_includes_tool_and_uncertain_guard():
    async def slow(*args):
        await asyncio.sleep(10)

    action = AsyncMock(side_effect=slow)
    engine, _client, _ = runner(
        [response(call())], execute=action, timeout_seconds=0.02
    )
    with pytest.raises(ResponsesTimeout):
        await engine.run([], lambda: True)
    assert "unknown" in await engine.bridge.execute(
        "new", "moveHead", '{"direction":"left"}', lambda: True
    )
    action.assert_awaited_once()


@pytest.mark.asyncio
async def test_round_limit_and_provider_failure_are_sanitized():
    engine, _client, _execute = runner([response(call())], max_rounds=1)
    with pytest.raises(OpenAIResponsesError, match="round"):
        await engine.run([], lambda: True)
    engine, _client, _execute = runner([RuntimeError("api-key secret rawbody")])
    with pytest.raises(OpenAIResponsesError) as error:
        await engine.run([], lambda: True)
    assert "secret" not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.asyncio
@pytest.mark.parametrize("abort", ["timeout", "cancel"])
async def test_integration_suppressing_cancel_cannot_clear_uncertainty(abort):
    started = asyncio.Event()
    release = asyncio.Event()
    completed = asyncio.Event()

    async def stubborn(*args):
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()
        completed.set()
        return "started"

    action = AsyncMock(side_effect=stubborn)
    engine, _, _ = runner(
        [response(call()), response(text="Started.")],
        execute=action,
        timeout_seconds=0.02 if abort == "timeout" else 5,
    )
    task = asyncio.create_task(engine.run([], lambda: True))
    await started.wait()
    if abort == "cancel":
        task.cancel()
    with pytest.raises(
        ResponsesTimeout if abort == "timeout" else asyncio.CancelledError
    ):
        await task
    release.set()
    await completed.wait()
    await asyncio.sleep(0)
    outcome = await engine.bridge.execute(
        "new", "moveHead", '{"direction":"left"}', lambda: True
    )
    assert "unknown" in outcome
    action.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,params",
    [
        ("playAnimation", {"animation": "celebrate"}),
        ("moveHead", {"direction": "center"}),
        ("goToSleep", {}),
        ("danceMode", {}),
        ("galacticScan", {"query": "current weather"}),
        ("streamContent", {"title": "Bluey"}),
        ("rokuControl", {"action": "volume_up"}),
        ("setTimer", {"duration_seconds": 60}),
        ("cancelTimer", {"timer_id": "one"}),
        ("findTimers", {}),
    ],
)
async def test_all_ten_tools_reach_exactly_the_intended_callback(name, params):
    action = AsyncMock(return_value="confirmed")
    search = AsyncMock(return_value="Forecast verified")
    bridge = OpenAIToolBridge(registry(), action, search=search)
    result = await bridge.execute("one", name, json.dumps(params), lambda: True)
    if name == "galacticScan":
        search.assert_awaited_once_with(params["query"])
        action.assert_not_awaited()
    else:
        action.assert_awaited_once_with("one", name, params)
        search.assert_not_awaited()
    assert result in ("confirmed", "Forecast verified")


@pytest.mark.asyncio
async def test_search_incomplete_output_is_rejected():
    engine, _, _ = runner(
        [response({"type": "web_search_call", "status": "in_progress"}, text="Sunny")]
    )
    with pytest.raises(OpenAIResponsesError):
        await engine.search("weather")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": True},
        {"max_rounds": True},
        {"max_rounds": 1.5},
    ],
)
def test_constructor_rejects_invalid_numeric_bounds(kwargs):
    with pytest.raises(ValueError):
        runner([], **kwargs)


@pytest.mark.asyncio
async def test_benign_unknown_label_does_not_lock_read_or_action():
    action = AsyncMock(return_value='Timer "unknown error" set for one minute.')
    bridge = OpenAIToolBridge(registry(), action)
    params = '{"duration_seconds":60,"label":"unknown error"}'
    first = await bridge.execute("a", "setTimer", params, lambda: True)
    assert first == 'Timer "unknown error" set for one minute.'
    await bridge.execute("b", "setTimer", params, lambda: True)
    assert action.await_count == 2


@pytest.mark.asyncio
async def test_session_ledger_limit_fails_closed():
    action = AsyncMock(return_value="ok")
    bridge = OpenAIToolBridge(registry(), action)
    for i in range(512):
        await bridge.execute(str(i), "moveHead", '{"direction":"left"}', lambda: True)
    assert "tool_limit" in await bridge.execute(
        "overflow", "danceMode", "{}", lambda: True
    )
    assert action.await_count == 512


@pytest.mark.asyncio
async def test_confirmed_terminal_handoff_stops_remaining_tools_and_model_calls():
    engine, client, execute = runner(
        [
            response(
                call("sleep", "goToSleep", "{}"),
                call("later", "moveHead", '{"direction":"left"}'),
            )
        ]
    )
    engine.terminal_pending = lambda: True
    result = await engine.run([{"role": "user", "content": "Goodbye"}], lambda: True)
    assert "host" in result
    execute.assert_awaited_once_with("sleep", "goToSleep", {})
    client.responses.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_silent_completed_reply_preserves_short_tool_outcome_without_replay():
    engine, client, execute = runner([response(call()), response(text="")])
    execute.return_value = "Head movement started; completion is unverified."
    result = await engine.run([], lambda: True)
    assert result == "Backend results: Head movement started; completion is unverified."
    execute.assert_awaited_once()
    assert client.responses.create.await_count == 2


@pytest.mark.asyncio
async def test_empty_reply_does_not_hide_refusal_or_truncate_tool_qualifications():
    refusal = {
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "refusal", "refusal": "Cannot help."}],
    }
    engine, _, _ = runner([response(call()), response(refusal)])
    with pytest.raises(OpenAIResponsesError, match="declined"):
        await engine.run([], lambda: True)
    engine, _, execute = runner([response(call()), response(text="")])
    execute.return_value = "x" * 500 + " status is unknown"
    with pytest.raises(OpenAIResponsesError, match="short factual"):
        await engine.run([], lambda: True)


@pytest.mark.asyncio
async def test_late_provider_tasks_cannot_exceed_response_capacity():
    engine, _, _ = runner([])
    finish = asyncio.Event()
    starts = []

    async def stubborn():
        starts.append(True)
        while not finish.is_set():
            try:
                await finish.wait()
            except asyncio.CancelledError:
                pass

    for _ in range(8):
        with pytest.raises(ResponsesTimeout):
            await engine._bounded(stubborn(), 0.001)
    with pytest.raises(OpenAIResponsesError, match="unfinished"):
        await engine._bounded(stubborn(), 0.001)
    assert len(starts) == len(engine._pending_tasks) == 8
    finish.set()
    await asyncio.gather(*engine._pending_tasks)
    await asyncio.sleep(0)
    assert not engine._pending_tasks


@pytest.mark.asyncio
async def test_preparing_real_sdk_resources_is_idempotent_and_makes_no_requests():
    import httpx2
    from openai import AsyncOpenAI
    from openai.types.responses import Response
    from blooglyblob.ai.responses import prepare_responses

    requests = []

    async def handler(request):
        requests.append(request)
        return httpx2.Response(
            200,
            json={
                "id": "resp_test",
                "object": "response",
                "created_at": 0,
                "status": "completed",
                "model": "test",
                "output": [],
            },
        )

    async with AsyncOpenAI(
        api_key="offline-test",
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    ) as api:
        await asyncio.to_thread(prepare_responses, api)
        resource = api.responses
        await asyncio.to_thread(prepare_responses, api)
        assert api.responses is resource
        assert Response.__pydantic_complete__
        assert requests == []
        result = await api.responses.create(model="test", input="test", store=False)
        assert result.status == "completed"
        assert len(requests) == 1
