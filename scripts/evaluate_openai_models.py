"""Opt-in, small synthetic backend comparison; every integration effect is mocked.

Run from the repository root with ``python -m scripts.evaluate_openai_models``.
Bring your own OPENAI_API_KEY; running this helper incurs billable token usage.
See CONTRIBUTING.md for setup, a small example run, and result interpretation.
This measures neither spoken voice quality nor device latency or real-world use.
"""

import argparse
import asyncio
import copy
import json
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace


MODELS = ("gpt-5.6-luna", "gpt-5.6-terra")
ROOT = Path(__file__).resolve().parents[1]
LIMITATIONS = (
    "Small synthetic evaluation with mocked integrations and hosted search disabled. "
    "Clarification scoring is a text heuristic. No hardware, voice quality, real "
    "users, statistical significance, or general model superiority is measured. "
    "Usage covers Responses only, excluding Live and Speech."
)


@dataclass(frozen=True)
class Case:
    name: str
    messages: tuple[str, ...]
    expected_calls: tuple[dict, ...]
    clarification: bool = False


CASES = (
    Case(
        "labeled_timer",
        ("Set a timer for two minutes called rocket.",),
        ({"name": "setTimer", "params": {"duration_seconds": 120, "label": "rocket"}},),
    ),
    Case(
        "head_motion",
        ("Look left at normal speed.",),
        ({"name": "moveHead", "params": {"direction": "left", "speed": "normal"}},),
    ),
    Case(
        "goodbye",
        ("Goodnight Meep, I'm done chatting.",),
        ({"name": "goToSleep", "params": {}},),
    ),
    Case(
        "dance", ("Let's have a dance party!",), ({"name": "danceMode", "params": {}},)
    ),
    Case(
        "find_timers",
        ("Tell me all the timers that are running.",),
        ({"name": "findTimers", "params": {}},),
    ),
    Case(
        "cancel_timer",
        ("Cancel my rocket timer. Keep my snack timer.",),
        (
            {"name": "findTimers", "params": {"queries": ["rocket"]}},
            {"name": "cancelTimer", "params": {"timer_id": "mock-rocket"}},
        ),
    ),
    Case("ambiguous_timer", ("Set a timer for my game.",), (), clarification=True),
    Case(
        "corrected_duration",
        (
            "Set a timer for five minutes called rocket.",
            "Wait, make that two minutes instead. You haven't started it yet.",
        ),
        ({"name": "setTimer", "params": {"duration_seconds": 120, "label": "rocket"}},),
    ),
)


def _normalized(value):
    if isinstance(value, str):
        return value.strip().casefold()
    if isinstance(value, dict):
        return {key: _normalized(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalized(item) for item in value]
    return value


def score_case(case, observed, result):
    """Exact ordered effects, plus an explicitly limited clarification heuristic."""
    calls_match = _normalized(observed) == _normalized(list(case.expected_calls))
    clarification_match = not case.clarification or (
        "?" in result
        and any(
            word in result.casefold()
            for word in (
                "how long",
                "duration",
                "minutes",
                "seconds",
                "length of time",
            )
        )
    )
    return {
        "success": calls_match and clarification_match,
        "calls_match": calls_match,
        "clarification_match": clarification_match,
    }


class MockEffects:
    """No real registry dispatch, timer manager, device, or network integration."""

    def __init__(self):
        self.calls = []

    async def execute(self, _call_id, name, params):
        self.calls.append({"name": name, "params": copy.deepcopy(params)})
        if name == "findTimers":
            timers = [
                {"id": "mock-rocket", "label": "rocket", "remaining_seconds": 120},
                {"id": "mock-snack", "label": "snack", "remaining_seconds": 300},
            ]
            queries = params.get("queries", [])
            return json.dumps(
                {
                    "timers": [
                        timer
                        for timer in timers
                        if not queries
                        or any(query.casefold() in timer["label"] for query in queries)
                    ]
                }
            )
        return json.dumps({"status": "confirmed", "mock": True})

    async def search(self, query):
        self.calls.append({"name": "galacticScan", "params": {"query": query}})
        return json.dumps({"mock": True, "results": []})


class FunctionsOnlyClient:
    """Keep real Responses inference, but prevent hosted search from executing."""

    def __init__(self, client):
        self._client = client
        self.responses = SimpleNamespace(create=self.create)

    async def create(self, **kwargs):
        kwargs["tools"] = [
            tool for tool in kwargs["tools"] if tool["type"] == "function"
        ]
        return await self._client.responses.create(**kwargs)


async def evaluate_case(client, model, case):
    from blooglyblob.ai.responses import OpenAIResponses
    from blooglyblob.ai.tool_bridge import OpenAIToolBridge
    from blooglyblob.tools.registry import ToolRegistry
    from blooglyblob.ai.voice_profile import backend_instructions

    if model not in MODELS or case not in CASES:
        raise ValueError("Only the bounded built-in evaluation is supported")
    registry = ToolRegistry()
    registry.load_from_configs()
    effects = MockEffects()
    bridge = OpenAIToolBridge(registry, effects.execute, search=effects.search)
    runner = OpenAIResponses(
        FunctionsOnlyClient(client),
        model=model,
        instructions=backend_instructions(),
        bridge=bridge,
        timeout_seconds=30,
        max_rounds=6,
        terminal_pending=lambda: (
            bool(effects.calls)
            and effects.calls[-1]["name"] in {"goToSleep", "danceMode"}
        ),
    )
    started = time.monotonic()
    error_class = None
    result = ""
    try:
        result = await runner.run(
            [{"role": "user", "content": message} for message in case.messages],
            lambda: True,
        )
    except Exception as exc:  # noqa: BLE001 - never record provider bodies or secrets
        error_class = type(exc).__name__
    score = score_case(case, effects.calls, result)
    score["success"] = score["success"] and error_class is None
    return {
        "case": case.name,
        "model": model,
        "expected_calls": list(case.expected_calls),
        "observed_calls": effects.calls,
        **score,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "usage": dict(runner.usage),
        "error_class": error_class,
    }


def _case_count(value):
    count = int(value)
    if not 1 <= count <= len(CASES):
        raise argparse.ArgumentTypeError("Cases must be between 1 and 8")
    return count


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", required=True, type=Path, help="JSON artifact destination"
    )
    parser.add_argument(
        "--cases",
        default=8,
        type=_case_count,
        help="First 1–8 built-in cases per model",
    )
    parser.add_argument("--models", nargs="+", choices=MODELS, default=list(MODELS))
    args = parser.parse_args(argv)
    if len(args.models) != len(set(args.models)):
        parser.error("Each model may appear only once")
    return args


async def run_evaluation(client, models, count):
    if (
        type(count) is not int
        or not 1 <= count <= 8
        or not models
        or len(models) != len(set(models))
        or any(model not in MODELS for model in models)
    ):
        raise ValueError("Invalid evaluation bounds")
    results = []
    for case in CASES[:count]:
        # Alternate order so neither model always receives the earlier request.
        order = (
            models if len(results) // len(models) % 2 == 0 else list(reversed(models))
        )
        for model in order:
            results.append(await evaluate_case(client, model, case))
    return {
        "evaluation": "synthetic_backend_comparison",
        "limitations": LIMITATIONS,
        "results": results,
    }


async def _paid_run(args):
    from blooglyblob.config import load_ai_config, load_runtime_environment

    load_runtime_environment()
    from openai import AsyncOpenAI

    key = load_ai_config().openai_api_key
    async with AsyncOpenAI(api_key=key, max_retries=0, timeout=30) as client:
        artifact = await run_evaluation(client, args.models, args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n")


def main(argv=None):
    args = parse_args(argv)  # Validate arguments before loading credentials.
    try:
        asyncio.run(_paid_run(args))
    except Exception as exc:  # noqa: BLE001 - never print provider exception text
        print("Evaluation failed:", type(exc).__name__)
        return 1
    print("Synthetic evaluation artifact written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
