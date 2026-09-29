"""Provider-independent validation and session-scoped action deduplication.

Only the injected validated callback can reach integrations or hardware. The registry's
canonical input schemas remain unchanged; no legacy provider SDK is imported.
"""

import asyncio
import copy
import json
import math
from typing import Callable

from blooglyblob.tools.registry import ToolRegistry


class ToolBridgeError(RuntimeError):
    """A bounded, safe-to-log tool bridge failure."""


class StaleResponse(ToolBridgeError):
    """The request no longer owns this session; dispatched effects may remain."""


def _error(code: str, message: str) -> str:
    return json.dumps({"error": code, "message": message})


_UNKNOWN = _error(
    "execution_unknown", "Execution status is unknown; do not retry this action."
)


def _strict(schema: dict) -> dict:
    result = copy.deepcopy(schema)
    if result.get("type") == "object":
        required = set(result.get("required", []))
        properties = result.setdefault("properties", {})
        for name, child in properties.items():
            child = _strict(child)
            if name not in required:
                kind = child["type"]
                child["type"] = (
                    [kind, "null"] if isinstance(kind, str) else [*kind, "null"]
                )
                if "enum" in child:
                    child["enum"].append(None)
            properties[name] = child
        result["required"] = list(properties)
        result["additionalProperties"] = False
    elif result.get("type") == "array":
        result["items"] = _strict(result["items"])
    return result


def _validate(value, schema: dict):
    """Validate the primitive/object/array subset used by the canonical configs."""
    kind = schema.get("type")
    if kind == "object":
        if type(value) is not dict:
            raise ValueError
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        if set(value) - properties.keys() or required - value.keys():
            raise ValueError
        normalized = {}
        for name, item in value.items():
            if item is None and name not in required:
                continue  # Original handler defaults apply, including False and "any".
            normalized[name] = _validate(item, properties[name])
        return normalized
    if kind == "array":
        if type(value) is not list or len(value) > 128:
            raise ValueError
        return [_validate(item, schema["items"]) for item in value]
    valid = {
        "string": type(value) is str,
        "boolean": type(value) is bool,
        "integer": type(value) is int,
        "number": type(value) in (int, float) and math.isfinite(value),
    }
    if not isinstance(kind, str) or not valid.get(kind, False):
        raise ValueError
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError
    return value


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError


def _unconfirmed(result: str) -> bool:
    try:
        payload = json.loads(result)
    except (ValueError, RecursionError):
        payload = None
    if isinstance(payload, dict):
        return "error" in payload or payload.get("status") in (
            "unknown",
            "execution_unknown",
            "error",
            "failed",
            "timeout",
        )
    return (
        result.strip()
        .lower()
        .startswith(
            (
                "error:",
                "timeout",
                "timed out",
                "unknown execution",
                "execution status is unknown",
                "uncertain delivery",
                "failed:",
            )
        )
    )


class OpenAIToolBridge:
    """Keep one instance per session, shared by its successive delegations.

    ``execute`` must be async and check connection ownership at the actual effect
    boundary. It must raise or return an error when delivery is unconfirmed.
    Search is deliberately separate: missing search never invokes a legacy handler.
    """

    def __init__(self, registry: ToolRegistry, execute, search=None):
        self._schemas = {
            tool["name"]: copy.deepcopy(tool) for tool in registry.schemas()
        }
        self._execute = execute
        self.search = search
        self._calls: dict[str, tuple[str, str]] = {}
        self._uncertain: set[str] = set()

    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "name": tool["name"],
                "description": tool["description"],
                "strict": True,
                "parameters": _strict(tool["input_schema"]),
            }
            for tool in self._schemas.values()
        ]

    async def execute(
        self,
        call_id: str,
        name: str,
        arguments_json: str,
        is_current: Callable[[], bool],
    ) -> str:
        if not is_current():
            raise StaleResponse("Request superseded; no further actions permitted.")
        try:
            if (
                type(call_id) is not str
                or not call_id
                or len(call_id) > 256
                or type(name) is not str
                or name not in self._schemas
                or type(arguments_json) is not str
                or len(arguments_json.encode("utf-8")) > 16384
            ):
                raise ValueError
            params = _validate(
                json.loads(
                    arguments_json,
                    parse_constant=_reject_constant,
                    object_pairs_hook=_unique_object,
                ),
                self._schemas[name]["input_schema"],
            )
            if name == "setTimer" and params["duration_seconds"] <= 0:
                raise ValueError
            for key in ("query", "title", "timer_id"):
                if key in params and not params[key].strip():
                    raise ValueError
            if (
                name == "rokuControl"
                and params["action"] == "launch_app"
                and not params.get("app", "").strip()
            ):
                raise ValueError
        except (ValueError, TypeError, RecursionError, UnicodeError, OverflowError):
            return _error(
                "invalid_tool_arguments",
                "Unknown tool or invalid arguments; no action dispatched.",
            )
        signature = (
            name + ":" + json.dumps(params, sort_keys=True, separators=(",", ":"))
        )
        previous = self._calls.get(call_id)
        if previous:
            if previous[0] != signature:
                return _error(
                    "call_id_conflict",
                    "Call ID was already used with different arguments; no action dispatched.",
                )
            return previous[1]
        if signature in self._uncertain:
            return _UNKNOWN
        if len(self._calls) >= 512:
            return _error(
                "tool_limit", "Session action limit reached; no action dispatched."
            )
        if not is_current():
            raise StaleResponse("Request superseded; no further actions permitted.")
        # Reserve before yielding. Concurrent duplicate IDs/signatures cannot replay.
        self._calls[call_id] = (signature, _UNKNOWN)
        self._uncertain.add(signature)
        try:
            if name == "galacticScan":
                if self.search is None:
                    result = _error(
                        "search_unavailable", "OpenAI search is unavailable."
                    )
                else:
                    result = await self.search(params["query"])
            else:
                result = await self._execute(call_id, name, params)
            if not is_current():
                raise StaleResponse(
                    "Request superseded; already dispatched execution status is unknown."
                )
            if not isinstance(result, str) or len(result.encode("utf-8")) > 32768:
                return _UNKNOWN
            # Error strings can represent a lost acknowledgment. Fail closed even
            # when retained handlers return an error instead of raising it.
            if _unconfirmed(result):
                self._calls[call_id] = (signature, _UNKNOWN)
                return _UNKNOWN
            self._uncertain.discard(signature)
            self._calls[call_id] = (signature, result)
            return result
        except (asyncio.CancelledError, StaleResponse):
            raise
        except Exception:  # noqa: BLE001 - sanitize provider/integration boundary failures
            # Do not surface exception strings, which may contain URLs or keys.
            return _UNKNOWN
