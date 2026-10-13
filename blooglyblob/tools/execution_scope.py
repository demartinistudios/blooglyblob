"""Per-execution ownership carried into synchronous integration workers."""

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import threading
import time
from typing import Callable

from blooglyblob.ai.tool_bridge import StaleResponse
from .timing import stage


@dataclass
class ExecutionScope:
    is_current: Callable[[], bool]
    deadline: float
    tool: str = "none"
    cancelled: threading.Event = field(default_factory=threading.Event)
    cache: dict = field(default_factory=dict)

    def current(self):
        return (
            not self.cancelled.is_set()
            and time.monotonic() < self.deadline
            and self.is_current()
        )

    def check(self):
        if not self.current():
            raise StaleResponse("Execution no longer owns further effects")


_scope: ContextVar[ExecutionScope | None] = ContextVar("tool_execution", default=None)


@contextmanager
def execution_scope(scope):
    token = _scope.set(scope)
    try:
        yield scope
    finally:
        _scope.reset(token)


def check_current():
    scope = _scope.get()
    if scope is not None:
        scope.check()


def request_timeout(maximum=10.0):
    scope = _scope.get()
    if scope is None:
        return maximum
    scope.check()
    return min(maximum, max(0.001, scope.deadline - time.monotonic()))


def cached_lookup(key, lookup):
    """Reuse provider results only within this bounded tool execution."""
    scope = _scope.get()
    if scope is None:
        return lookup()
    scope.check()
    if key not in scope.cache:
        scope.cache[key] = lookup()
    scope.check()
    return scope.cache[key]


def effect_boundary():
    check_current()
    scope = _scope.get()
    stage("effect_dispatch", tool=scope.tool if scope else "none")
