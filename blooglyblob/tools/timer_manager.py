"""Timer manager with persistent storage.

Manages countdown timers that persist across reboots.
Fires callbacks when timers are due, filtering out expired entries on load.
"""

import json
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Callable, Literal


@dataclass
class TimerEntry:
    """A single timer entry."""

    id: str
    timer_type: Literal["timer"]
    label: str
    fire_at: float  # Unix timestamp when timer should fire
    created_at: float  # Unix timestamp when timer was created
    duration_seconds: int | None = None  # Original duration for timers


class TimerManager:
    """Manages timers with persistent storage.

    Timers are stored in data/timers.json and persist across restarts.
    Expired entries are automatically cleaned up on load.
    """

    def __init__(
        self,
        alert_callback: Callable[[TimerEntry], None] | None = None,
        data_dir: str | None = None,
    ):
        """Initialize the timer manager.

        Args:
            alert_callback: Function to call when a timer fires.
            data_dir: Directory for storing timer data (relative to cwd or absolute).
        """
        self._alert_callback = alert_callback
        self._data_dir = Path(
            data_dir
            or os.environ.get(
                "BLOOGLYBLOB_STATE_DIR",
                str(Path.home() / ".local" / "state" / "blooglyblob" / "brain"),
            )
        )
        self._timers_file = self._data_dir / "timers.json"
        self._timers: list[TimerEntry] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Ensure data directory exists
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Load existing timers
        self._load()

    def _load(self) -> None:
        """Load timers from disk, filtering out expired ones."""
        if not self._timers_file.exists():
            self._timers = []
            return

        try:
            with open(self._timers_file, "r") as f:
                data = json.load(f)

            now = time.time()
            loaded_timers = []
            expired_count = 0

            for entry_dict in data.get("timers", []):
                # Skip expired timers (don't fire stale alerts)
                if entry_dict.get("fire_at", 0) < now:
                    expired_count += 1
                    continue

                entry = TimerEntry(
                    id=entry_dict["id"],
                    timer_type=entry_dict["timer_type"],
                    label=entry_dict["label"],
                    fire_at=entry_dict["fire_at"],
                    created_at=entry_dict["created_at"],
                    duration_seconds=entry_dict.get("duration_seconds"),
                )
                loaded_timers.append(entry)

            self._timers = loaded_timers

            if expired_count > 0:
                print(f"[TIMER] Cleaned up {expired_count} expired timer(s)")
                self._save()

            if self._timers:
                print(f"[TIMER] Loaded {len(self._timers)} active timer(s)")

        except (json.JSONDecodeError, KeyError) as e:
            print(f"[TIMER] Error loading timers: {type(e).__name__}")
            self._timers = []

    def _save(self) -> None:
        """Save timers to disk."""
        data = {
            "timers": [asdict(t) for t in self._timers],
            "saved_at": time.time(),
        }

        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self._data_dir, delete=False
            ) as f:
                temporary = Path(f.name)
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self._timers_file)
        except OSError as e:
            print(f"[TIMER] Error saving timers: {type(e).__name__}")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def add_timer(self, duration_seconds: int, label: str = "") -> str:
        """Add a countdown timer.

        Args:
            duration_seconds: How long until the timer fires.
            label: Optional label for the timer (e.g., "pizza").

        Returns:
            The timer ID.
        """
        timer_id = str(uuid.uuid4())[:8]
        now = time.time()

        entry = TimerEntry(
            id=timer_id,
            timer_type="timer",
            label=label or "Timer",
            fire_at=now + duration_seconds,
            created_at=now,
            duration_seconds=duration_seconds,
        )

        with self._lock:
            self._timers.append(entry)
            self._save()

        print(f"[TIMER] Added timer for {duration_seconds}s")
        return timer_id

    def cancel_timer(self, timer_id: str) -> bool:
        """Cancel a specific timer by ID.

        Args:
            timer_id: The timer ID to cancel.

        Returns:
            True if timer was found and cancelled.
        """
        with self._lock:
            original_count = len(self._timers)
            self._timers = [t for t in self._timers if t.id != timer_id]
            cancelled = len(self._timers) < original_count

            if cancelled:
                self._save()
                print("[TIMER] Cancelled timer")
            else:
                print("[TIMER] Timer not found")

            return cancelled

    def cancel_all(self) -> int:
        """Cancel all timers.

        Returns:
            Number of timers cancelled.
        """
        with self._lock:
            count = len(self._timers)
            self._timers = []
            self._save()
            print(f"[TIMER] Cancelled all {count} timer(s)")
            return count

    def get_active_timers(self) -> list[TimerEntry]:
        """Get list of all active timers."""
        with self._lock:
            return list(self._timers)

    def start(self) -> None:
        """Start the background monitoring thread."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        print("[TIMER] Timer manager started")

    def stop(self) -> None:
        """Stop the background monitoring thread."""
        self._running = False
        self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                raise RuntimeError("Timer producer release unconfirmed")

        print("[TIMER] Timer manager stopped")

    def _monitor_loop(self) -> None:
        """Background loop that checks for due timers every second."""
        while self._running and not self._stop_event.is_set():
            self._check_timers()
            self._stop_event.wait(timeout=1.0)

    def _check_timers(self) -> None:
        """Check for any timers that are due and fire them."""
        now = time.time()
        fired_ids: list[str] = []

        with self._lock:
            for candidate in self._timers:
                if candidate.fire_at <= now:
                    fired_ids.append(candidate.id)

        # Fire callbacks outside the lock to avoid blocking
        for timer_id in fired_ids:
            timer = None
            with self._lock:
                for t in self._timers:
                    if t.id == timer_id:
                        timer = t
                        break

            if timer:
                self._fire_timer(timer)

                # Remove from list after firing
                with self._lock:
                    self._timers = [t for t in self._timers if t.id != timer_id]
                    self._save()

    def _fire_timer(self, timer: TimerEntry) -> None:
        """Fire a single timer's callback."""
        print("[TIMER] Firing timer")

        if self._alert_callback:
            try:
                self._alert_callback(timer)
            except Exception as e:
                print(f"[TIMER] Error in alert callback: {type(e).__name__}")
