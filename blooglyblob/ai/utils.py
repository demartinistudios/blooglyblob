"""Shared SDK response access and detached-task cleanup for OpenAI adapters."""

from asyncio import Task
from typing import Any


def field(value: Any, name: str, default=None):
    """Read a field from a decoded event or an SDK response object."""
    return (
        value.get(name, default)
        if isinstance(value, dict)
        else getattr(value, name, default)
    )


def consume_task_exception(task: Task) -> None:
    """Retrieve a detached task's failure without accepting its late result."""
    if not task.cancelled():
        task.exception()
