"""Bounded tool-stage logs: local job identity and monotonic time, never inputs."""

import logging
import time
from contextvars import ContextVar

logger = logging.getLogger(__name__)
_trace: ContextVar[tuple[str, float] | None] = ContextVar("tool_trace", default=None)
_STAGES = frozenset(
    {
        "delegation",
        "audio_ready",
        "backend_request",
        "backend_received",
        "backend_parsed",
        "tool_selected",
        "tool_admitted",
        "effect_dispatch",
        "tool_result",
        "search_started",
        "search_finished",
        "result_supplied",
        "job_finished",
    }
)
_TOOLS = frozenset(
    {
        "moveHead",
        "playAnimation",
        "goToSleep",
        "danceMode",
        "galacticScan",
        "setTimer",
        "findTimers",
        "cancelTimer",
        "rokuControl",
        "streamContent",
    }
)


def begin_trace(job_id: str):
    return _trace.set((job_id, time.monotonic()))


def end_trace(token):
    _trace.reset(token)


def stage(name: str, *, tool: str = "none") -> None:
    trace = _trace.get()
    if trace is None or name not in _STAGES or (tool != "none" and tool not in _TOOLS):
        return
    logger.info(
        "Tool stage: job=%s stage=%s tool=%s elapsed_ms=%.1f",
        trace[0],
        name,
        tool,
        (time.monotonic() - trace[1]) * 1000,
    )
