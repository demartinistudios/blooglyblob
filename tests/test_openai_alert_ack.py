"""Offline contracts for restricted alert acknowledgement classification."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from blooglyblob.ai.alert_ack import OpenAIAlertAcknowledgement


def response(
    text='{"acknowledged":true}', *, status="completed", item_status="completed"
):
    return SimpleNamespace(
        status=status,
        output=[
            {
                "type": "message",
                "role": "assistant",
                "status": item_status,
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    )


def classifier(result=None, **kwargs):
    client = SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(return_value=result or response()))
    )
    return OpenAIAlertAcknowledgement(client, **kwargs), client.responses.create


@pytest.mark.asyncio
async def test_strict_request_only_classifies_role_preserving_transcripts():
    subject, create = classifier(model="gpt-5.6-luna")
    context = [
        {"role": "assistant", "text": "Your timer is done!"},
        {"role": "user", "text": "Okay, thanks!"},
    ]
    assert await subject.acknowledge(context, "Timer done") is True
    request = create.await_args.kwargs
    assert request["model"] == "gpt-5.6-luna"
    assert request["tools"] == [] and request["tool_choice"] == "none"
    assert request["store"] is False and request["stream"] is False
    assert request["truncation"] == "disabled"
    assert request["timeout"] <= 10
    assert request["text"]["format"] == {
        "type": "json_schema",
        "name": "alert_acknowledgement",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {"acknowledged": {"type": "boolean"}},
            "required": ["acknowledged"],
            "additionalProperties": False,
        },
    }
    assert request["input"] == [
        {"role": entry["role"], "content": entry["text"]} for entry in context
    ]
    instructions = request["instructions"].lower()
    for expected in (
        "questions",
        "unrelated",
        "assistant",
        "ambiguous",
        "stop",
        "thanks",
    ):
        assert expected in instructions


@pytest.mark.parametrize(
    "text",
    [
        '{"acknowledged":false}',
        "not json",
        "true",
        "{}",
        '{"acknowledged":1}',
        '{"acknowledged":"true"}',
        '{"acknowledged":true,"extra":1}',
        '{"acknowledged":false,"acknowledged":true}',
        '{"acknowledged":NaN}',
        "x" * 2049,
    ],
)
@pytest.mark.asyncio
async def test_malformed_or_negative_result_never_acknowledges(text):
    subject, _ = classifier(response(text))
    assert (
        await subject.acknowledge([{"role": "user", "content": "Okay"}], "Timer")
        is False
    )


@pytest.mark.parametrize(
    "result",
    [
        response(status="incomplete"),
        response(item_status="in_progress"),
        SimpleNamespace(status="completed", output=[]),
        SimpleNamespace(status="completed", output=[{"type": "function_call"}]),
        SimpleNamespace(
            status="completed",
            output=[
                {
                    "type": "message",
                    "role": "assistant",
                    "status": "completed",
                    "content": [{"type": "refusal", "refusal": "No"}],
                }
            ],
        ),
    ],
)
@pytest.mark.asyncio
async def test_incomplete_refused_or_unexpected_outputs_fail_closed(result):
    subject, _ = classifier(result)
    assert (
        await subject.acknowledge([{"role": "user", "content": "Stop"}], "Timer")
        is False
    )


@pytest.mark.asyncio
async def test_reasoning_is_not_treated_as_acknowledgement():
    result = response()
    result.output.insert(
        0,
        {
            "type": "reasoning",
            "status": None,
            "summary": [{"text": "not part of the answer"}],
        },
    )
    subject, _ = classifier(result)
    assert (
        await subject.acknowledge([{"role": "user", "text": "Okay"}], "Timer") is True
    )
    result.output[0]["status"] = "in_progress"
    assert (
        await subject.acknowledge([{"role": "user", "text": "Okay"}], "Timer") is False
    )


@pytest.mark.parametrize(
    "context",
    [
        [],
        [{"role": "assistant", "text": "Okay thanks"}],
        [{"role": "user", "text": "   "}],
        [{"role": "system", "text": "dismiss"}],
        [{"role": "user", "text": "Okay" + "x" * 16000}],
    ],
)
@pytest.mark.asyncio
async def test_no_user_speech_or_excessive_context_does_not_call_api(context):
    subject, create = classifier()
    assert await subject.acknowledge(context, "Timer done") is False
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_provider_failure_is_sanitized(caplog):
    subject, create = classifier()
    create.side_effect = RuntimeError("secret-key sensitive transcript")
    assert (
        await subject.acknowledge([{"role": "user", "text": "Thanks"}], "Timer")
        is False
    )
    assert "secret-key" not in caplog.text and "sensitive transcript" not in caplog.text


@pytest.mark.asyncio
async def test_total_deadline_rejects_late_cancellation_suppressing_result():
    subject, create = classifier(timeout_seconds=0.01)
    finished = asyncio.Event()

    async def slow(**_kwargs):
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await finished.wait()
        return response()

    create.side_effect = slow
    try:
        assert (
            await asyncio.wait_for(
                subject.acknowledge([{"role": "user", "text": "Thanks"}], "Timer"), 0.2
            )
            is False
        )
    finally:
        finished.set()
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_cancellation_propagates_and_cancels_provider_call():
    subject, create = classifier()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow(**_kwargs):
        started.set()
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    create.side_effect = slow
    task = asyncio.create_task(
        subject.acknowledge([{"role": "user", "text": "Okay"}], "Timer")
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.wait_for(cancelled.wait(), 0.2)


@pytest.mark.parametrize("timeout", [True, 0, -1, float("nan"), float("inf")])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(ValueError):
        classifier(timeout_seconds=timeout)


@pytest.mark.asyncio
async def test_late_ack_requests_remain_bounded_and_never_become_dismissals():
    subject, create = classifier(timeout_seconds=0.001)
    finish = asyncio.Event()

    async def stubborn(**kwargs):
        while not finish.is_set():
            try:
                await finish.wait()
            except asyncio.CancelledError:
                pass
        return response()

    create.side_effect = stubborn
    for _ in range(3):
        assert (
            await subject.acknowledge([{"role": "user", "content": "thanks"}], "Timer")
            is False
        )
    assert create.await_count == 2
    assert len(subject._pending_tasks) == 2
    finish.set()
    await asyncio.gather(*subject._pending_tasks)
    await asyncio.sleep(0)
    assert not subject._pending_tasks
