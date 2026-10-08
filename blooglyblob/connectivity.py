"""Bounded cloud reachability and admission; never repairs OS networking."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
import socket
import time
from urllib.parse import urlsplit

import aiohttp

logger = logging.getLogger(__name__)


def failure_category(error: Exception) -> str | None:
    """Use exception types/status only; never retain provider text or credentials."""
    from openai import (
        APIConnectionError,
        APIStatusError,
        WebSocketConnectionClosedError,
    )
    from websockets.exceptions import ConnectionClosed, InvalidStatus

    category = getattr(error, "category", None)
    if category in {"network", "auth", "service", "protocol"}:
        return category
    status = None
    if isinstance(error, APIStatusError):
        status = error.status_code
    elif isinstance(error, InvalidStatus):
        status = error.response.status_code
    if status in {401, 403}:
        return "auth"
    if status == 429 or (isinstance(status, int) and status >= 500):
        return "service"
    if status is not None:
        return "protocol"
    if isinstance(
        error,
        (
            APIConnectionError,
            aiohttp.ClientError,
            ConnectionClosed,
            WebSocketConnectionClosedError,
            socket.gaierror,
            ConnectionError,
            TimeoutError,
        ),
    ):
        return "network"
    return None


class ReachabilityProbe:
    """A credential-free request, separate from the authenticated API client."""

    def __init__(self, base_url: str):
        url = urlsplit(base_url)
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("Cloud reachability requires an HTTPS API origin")
        self.url = f"{url.scheme}://{url.netloc}/v1/models"

    async def __call__(self) -> bool:
        # A 401 is the expected response without a key. A 200 also demonstrates
        # reachability; redirects, captive portals and 5xx must not admit starts.
        async with asyncio.timeout(3):
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=3)
            ) as client:
                async with client.get(self.url, allow_redirects=False) as response:
                    return (
                        response.status in {200, 401}
                        and response.content_type == "application/json"
                    )


class Availability:
    """One loop-owned admission decision with hysteresis and stale-probe fencing."""

    def __init__(
        self,
        *,
        probe: Callable[[], Awaitable[bool]],
        changed: Callable[[bool], None],
        live_connected: Callable[[], bool] = lambda: False,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.probe, self.changed = probe, changed
        self.live_connected, self.clock = live_connected, clock
        self.ready = False
        self.reason = "checking"
        self._revision = 0
        self._successes = self._failures = 0
        self._retry_after = 0.0

    def fail(self, reason: str) -> None:
        if reason not in {"network", "auth", "service", "protocol"}:
            raise ValueError("Unknown availability failure")
        self._revision += 1
        self._successes = self._failures = 0
        self._retry_after = self.clock() + (30 if reason == "service" else 0)
        self._set(False, reason)

    def _set(self, ready: bool, reason: str) -> None:
        previous = self.ready
        if self.reason != reason:
            logger.info("Cloud availability: %s", reason)
        self.ready, self.reason = ready, reason
        if previous != ready:
            self.changed(ready)

    async def check(self) -> None:
        if self.live_connected() or self.reason in {"auth", "protocol"}:
            return
        revision = self._revision
        try:
            async with asyncio.timeout(3):
                success = await self.probe()
        except (TimeoutError, aiohttp.ClientError, OSError):
            success = False
        if revision != self._revision or self.live_connected():
            return
        if success:
            self._failures = 0
            self._successes += 1
            needed = 1 if self.reason == "checking" else 2
            if self._successes >= needed and self.clock() >= self._retry_after:
                self._set(True, "ready")
        else:
            self._successes = 0
            self._failures += 1
            if not self.ready or self._failures >= 2:
                self._set(False, "network")

    async def run(self) -> None:
        while True:
            await self.check()
            await asyncio.sleep(15)
