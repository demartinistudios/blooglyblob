"""Ring doorbell event handler using direct API polling.

Polls Ring API directly for active dings, bypassing the library's
session endpoint which returns 406 errors.
"""

import asyncio
import json
import os
import threading
import time
from typing import Any, Callable

import aiohttp

# Ring is available if aiohttp is installed (always true since it's a dependency)
RING_AVAILABLE = True

# Polling configuration
POLL_INTERVAL = 3.0  # seconds between polls
MAX_RETRY_ATTEMPTS = 5
RETRY_DELAY = 30  # seconds between retries on error
STABLE_OPERATION_TIME = 300  # 5 minutes - reset retry count after this

# Ring API
RING_API_BASE = "https://api.ring.com/clients_api"
USER_AGENT = "android:com.ringapp"


class RingHandler:
    """Handles Ring doorbell ding events via direct API polling."""

    def __init__(
        self,
        on_doorbell: Callable[[], None] | None = None,
        debounce_seconds: float = 10.0,
    ):
        """Initialize the Ring handler.

        Args:
            on_doorbell: Callback when doorbell ding is detected.
            debounce_seconds: Minimum seconds between ding notifications.
        """
        self._on_doorbell = on_doorbell
        self._debounce_seconds = debounce_seconds

        # State
        self._access_token: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._running = threading.Event()
        self._last_ding_time: float = 0.0
        self._seen_ding_ids: set[int] = set()
        self._lock = threading.Lock()

    @property
    def is_available(self) -> bool:
        """Check if Ring integration is available."""
        return bool(os.environ.get("RING_TOKEN"))

    def _load_token(self) -> dict[str, Any] | None:
        """Load the token from the explicitly configured application environment."""
        # Try environment first
        token_json = os.environ.get("RING_TOKEN")
        if token_json:
            try:
                return json.loads(token_json)
            except json.JSONDecodeError:
                pass

        return None

    def _get_headers(self) -> dict[str, str]:
        """Get headers for Ring API requests."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

    def _handle_ding(self) -> None:
        """Handle a detected ding event with debouncing."""
        print("[RING] Ding detected")

        with self._lock:
            now = time.time()
            if now - self._last_ding_time < self._debounce_seconds:
                print(
                    f"[RING] Debounced (last ding {now - self._last_ding_time:.1f}s ago)"
                )
                return
            self._last_ding_time = now

        if self._on_doorbell:
            self._on_doorbell()

    async def _poll_loop(self) -> None:
        """Main polling loop for doorbell events."""
        token = self._load_token()
        if not token:
            print("[RING] Cannot start - no valid Ring token")
            return

        self._access_token = token.get("access_token")
        if not self._access_token:
            print("[RING] Cannot start - token missing access_token")
            return

        retry_count = 0

        async with aiohttp.ClientSession() as session:
            # Verify connection by fetching devices
            try:
                async with session.get(
                    f"{RING_API_BASE}/ring_devices",
                    headers=self._get_headers(),
                ) as resp:
                    if resp.status != 200:
                        print(f"[RING] Failed to connect: HTTP {resp.status}")
                        return

                    data = await resp.json()
                    doorbells = data.get("doorbots", [])
                    print(f"[RING] Connected - found {len(doorbells)} doorbell(s)")

                    if not doorbells:
                        print("[RING] No doorbells found - stopping")
                        return

            except Exception as e:
                print(f"[RING] Connection error: {type(e).__name__}")
                return

            print(f"[RING] Polling for events (interval: {POLL_INTERVAL}s)")
            started_at = time.time()

            # Polling loop
            while self._running.is_set() and retry_count < MAX_RETRY_ATTEMPTS:
                try:
                    await self._poll_once(session)

                    # Reset retry count after stable operation
                    if (
                        retry_count > 0
                        and time.time() - started_at > STABLE_OPERATION_TIME
                    ):
                        retry_count = 0

                    await asyncio.sleep(POLL_INTERVAL)

                except asyncio.CancelledError:
                    break

                except Exception as e:
                    if not self._running.is_set():
                        break

                    retry_count += 1
                    print(
                        f"[RING] Poll error: {type(e).__name__}, retrying ({retry_count}/{MAX_RETRY_ATTEMPTS})..."
                    )

                    if retry_count < MAX_RETRY_ATTEMPTS:
                        await asyncio.sleep(RETRY_DELAY)

        if retry_count >= MAX_RETRY_ATTEMPTS:
            print("[RING] Max retry attempts reached, giving up")

        print("[RING] Handler stopped")

    async def _poll_once(self, session: aiohttp.ClientSession) -> None:
        """Poll Ring API once for active dings."""
        async with session.get(
            f"{RING_API_BASE}/dings/active",
            headers=self._get_headers(),
        ) as resp:
            if resp.status != 200:
                print(f"[RING] Poll request failed: HTTP {resp.status}")
                raise Exception(f"HTTP {resp.status}")

            dings = await resp.json()

            for ding in dings:
                ding_id = ding.get("id")
                ding_kind = ding.get("kind")

                # Skip if already seen
                if ding_id in self._seen_ding_ids:
                    continue

                self._seen_ding_ids.add(ding_id)

                # Only handle ding events (not motion)
                if ding_kind == "ding":
                    self._handle_ding()

        # Prune old ding IDs to prevent memory growth
        if len(self._seen_ding_ids) > 100:
            sorted_ids = sorted(self._seen_ding_ids)
            self._seen_ding_ids = set(sorted_ids[-50:])

    def _thread_main(self) -> None:
        """Main function for the asyncio thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._poll_loop())
        except Exception as e:
            print(f"[RING] Thread error: {type(e).__name__}")
        finally:
            try:
                pending = asyncio.all_tasks(self._loop)
                for task in pending:
                    task.cancel()
                if pending:
                    self._loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
                self._loop.close()
            except Exception:
                pass
            self._loop = None

    def start(self) -> None:
        """Start listening for Ring doorbell events."""
        if not self._load_token():
            print("[RING] RING_TOKEN not set")
            print("[RING] Run 'make dev-setup-ring' to authenticate")
            return

        with self._lock:
            if self._thread and self._thread.is_alive():
                return

            self._running.set()
            self._thread = threading.Thread(
                target=self._thread_main,
                daemon=True,
                name="RingPoller",
            )
            self._thread.start()
            print("[RING] Handler started (polling mode)")

    def stop(self) -> None:
        """Stop listening for Ring doorbell events."""
        print("[RING] Stopping...")
        self._running.clear()

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread:
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                raise RuntimeError("Ring producer release unconfirmed")
            self._thread = None

        print("[RING] Stopped")
