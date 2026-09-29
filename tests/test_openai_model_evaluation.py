"""Offline evaluation guards and scoring; no key, HTTP, or device required."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from scripts import evaluate_openai_models as evaluation


def response(*calls, text="Timer confirmed."):
    return {
        "status": "completed",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        "output": list(calls)
        or [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }


def call(name, params, call_id="call1"):
    return {
        "type": "function_call",
        "name": name,
        "call_id": call_id,
        "arguments": json.dumps(params),
    }


def fake_client(*responses):
    return SimpleNamespace(
        responses=SimpleNamespace(create=AsyncMock(side_effect=responses))
    )


@pytest.mark.parametrize(
    "extra",
    [
        ["--cases", "9"],
        ["--cases", "0"],
        ["--models", "gpt-5.6-luna", "gpt-5.6-luna"],
    ],
)
def test_cli_rejects_before_any_paid_run(monkeypatch, tmp_path, extra):
    paid = AsyncMock()
    monkeypatch.setattr(evaluation, "_paid_run", paid)
    with pytest.raises(SystemExit):
        evaluation.main(["--output", str(tmp_path / "result.json"), *extra])
    paid.assert_not_called()


def test_cli_runs_with_valid_arguments(monkeypatch, tmp_path):
    paid = AsyncMock()
    monkeypatch.setattr(evaluation, "_paid_run", paid)
    output = tmp_path / "result.json"

    assert evaluation.main(["--cases", "1", "--output", str(output)]) == 0

    paid.assert_awaited_once()
    args = paid.await_args.args[0]
    assert args.cases == 1
    assert args.output == output
    assert args.models == list(evaluation.MODELS)


def test_effect_scoring_rejects_wrong_duration_extra_action_and_reversed_order():
    case = evaluation.CASES[0]
    expected = list(case.expected_calls)
    assert evaluation.score_case(case, expected, "Done.")["success"]
    wrong = [
        {"name": "setTimer", "params": {"duration_seconds": 300, "label": "rocket"}}
    ]
    assert not evaluation.score_case(case, wrong, "Done.")["success"]
    assert not evaluation.score_case(case, expected * 2, "Done.")["success"]
    cancel = evaluation.CASES[5]
    assert not evaluation.score_case(
        cancel, list(reversed(cancel.expected_calls)), "Done."
    )["success"]


def test_clarification_requires_duration_question_and_no_action():
    case = evaluation.CASES[6]
    assert evaluation.score_case(case, [], "How long should the timer run?")["success"]
    assert not evaluation.score_case(case, [], "Sure, okay!")["success"]
    assert not evaluation.score_case(case, [], "What's your favorite color?")["success"]
    assert not evaluation.score_case(
        case, list(evaluation.CASES[0].expected_calls), "How many minutes?"
    )["success"]


@pytest.mark.asyncio
async def test_actual_responses_loop_only_mocks_effects_and_records_usage(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Real integration execution is forbidden")

    from blooglyblob.tools.executor import ToolExecutor

    monkeypatch.setattr(ToolExecutor, "execute", forbidden)
    client = fake_client(
        response(call("setTimer", {"duration_seconds": 120, "label": "rocket"})),
        response(),
    )
    result = await evaluation.evaluate_case(
        client, evaluation.MODELS[0], evaluation.CASES[0]
    )
    assert result["success"]
    assert result["usage"] == {
        "input_tokens": 20,
        "output_tokens": 10,
        "total_tokens": 30,
    }
    assert result["elapsed_seconds"] >= 0
    assert result["error_class"] is None
    assert "Timer confirmed" not in json.dumps(result)
    for request in client.responses.create.call_args_list:
        assert len(request.kwargs["tools"]) == 10
        assert all(
            tool["type"] == "function" and tool["strict"]
            for tool in request.kwargs["tools"]
        )
        assert request.kwargs["store"] is False
        assert request.kwargs["timeout"] <= 30


@pytest.mark.asyncio
async def test_invalid_provider_arguments_never_count_as_effect():
    client = fake_client(
        response(call("setTimer", {"duration_seconds": -1})), response()
    )
    result = await evaluation.evaluate_case(
        client, evaluation.MODELS[0], evaluation.CASES[0]
    )
    assert not result["success"]
    assert result["observed_calls"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("case_index", [2, 3])
async def test_terminal_request_stops_without_extra_reasoning_round(case_index):
    case = evaluation.CASES[case_index]
    client = fake_client(response(call(case.expected_calls[0]["name"], {})))
    result = await evaluation.evaluate_case(client, evaluation.MODELS[0], case)
    assert result["success"]
    assert client.responses.create.await_count == 1


@pytest.mark.asyncio
async def test_find_then_cancel_uses_mock_id_only():
    client = fake_client(
        response(call("findTimers", {"queries": ["rocket"]})),
        response(call("cancelTimer", {"timer_id": "mock-rocket"}, "call2")),
        response(text="Rocket timer canceled."),
    )
    result = await evaluation.evaluate_case(
        client, evaluation.MODELS[1], evaluation.CASES[5]
    )
    assert result["success"]
    history = client.responses.create.call_args_list[1].kwargs["input"]
    tool_result = next(
        item["output"] for item in history if item.get("type") == "function_call_output"
    )
    assert "mock-rocket" in tool_result
    assert "mock-snack" not in tool_result


@pytest.mark.asyncio
async def test_failure_artifact_has_class_not_exception_body():
    client = fake_client(RuntimeError("secret-api-key and private transcript"))
    result = await evaluation.evaluate_case(
        client, evaluation.MODELS[0], evaluation.CASES[0]
    )
    assert result["error_class"] == "OpenAIResponsesError"
    assert not result["success"]
    assert "secret-api-key" not in json.dumps(result)
    assert "private transcript" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "models,count",
    [
        (evaluation.MODELS, 9),
        (evaluation.MODELS, True),
        ([evaluation.MODELS[0]] * 2, 1),
        (["other"], 1),
    ],
)
async def test_programmatic_bounds_reject_before_network(models, count):
    client = fake_client()
    with pytest.raises(ValueError):
        await evaluation.run_evaluation(client, models, count)
    client.responses.create.assert_not_called()


@pytest.mark.asyncio
async def test_comparison_cases_are_bounded_and_order_alternates(monkeypatch):
    execute = AsyncMock(
        side_effect=lambda _client, model, case: {"model": model, "case": case.name}
    )
    monkeypatch.setattr(evaluation, "evaluate_case", execute)
    artifact = await evaluation.run_evaluation(None, evaluation.MODELS, 2)
    assert [item["model"] for item in artifact["results"]] == [
        evaluation.MODELS[0],
        evaluation.MODELS[1],
        evaluation.MODELS[1],
        evaluation.MODELS[0],
    ]
    assert "synthetic" in artifact["limitations"]
    assert len(artifact["results"]) == 4
