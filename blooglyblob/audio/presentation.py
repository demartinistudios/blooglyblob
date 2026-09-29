"""Bounded, best-effort output timing for lights; never an audio completion signal.

Only successful writes publish intervals. Retiring an opaque owner rejects both
late writes and late clears, without waiting for the native speaker worker.
"""

from collections import deque
from dataclasses import dataclass
import logging
import math
import threading
import time

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutputSample:
    kind: str | None = None
    level: float = 0.0
    position: float = 0.0


@dataclass(frozen=True)
class Interval:
    start: float
    end: float
    position: float
    level: float


class OutputPresentation:
    def __init__(self):
        self._lock = threading.Lock()
        self._owner = None
        self._kind = None
        self._intervals: deque[Interval] = deque()
        self._disabled = False

    def begin(self, kind, owner=None):
        with self._lock:
            self._owner = object() if owner is None else owner
            self._kind = kind
            self._intervals.clear()
            self._disabled = False
            return self._owner

    def retire(self, owner):
        with self._lock:
            if self._owner is owner:
                self._owner = self._kind = None
                self._intervals.clear()

    def mute(self):
        with self._lock:
            self._owner = self._kind = None
            self._intervals.clear()

    def commit(self, owner, *, start, end, position, level, now=None):
        now = start if now is None else now
        with self._lock:
            if self._owner is not owner or self._disabled:
                return
            while self._intervals and self._intervals[0].end <= now:
                self._intervals.popleft()
            if (
                not all(math.isfinite(v) for v in (start, end, position, level, now))
                or end <= start
                or end - now > 2
                or len(self._intervals) >= 128
            ):
                self._disabled = True
                self._intervals.clear()
                log.warning("Lighting output timing unavailable for this playback")
                return
            self._intervals.append(
                Interval(start, end, position, max(0.0, min(1.0, level)))
            )

    def sample(self, now):
        with self._lock:
            while self._intervals and self._intervals[0].end <= now:
                self._intervals.popleft()
            if self._intervals:
                current = self._intervals[0]
                if current.start <= now < current.end:
                    return OutputSample(
                        self._kind,
                        current.level,
                        current.position + now - current.start,
                    )
            return OutputSample()


class OutputTimeline:
    """Writer-local estimate using blocking-write bounds and reported latency.

    PortAudio's latency is an estimate, not a DAC timestamp. Gaps reanchor the
    timeline; it never runs past committed samples. No new stream or callback.
    """

    def __init__(self, stream, rate, output, owner, *, clock=time.monotonic):
        self.output, self.owner, self.rate = output, owner, rate
        self.clock = clock
        self._frames = 0
        self._end = 0.0
        self._before = 0.0
        try:
            latency = float(stream.get_output_latency())
            self.latency = (
                latency if math.isfinite(latency) and 0 <= latency < 2 else None
            )
        except Exception:
            self.latency = None
        if self.latency is None:
            log.warning("Lighting disabled: speaker output latency unavailable")

    def before_write(self):
        self._before = self.clock()

    def written(self, frames, level=0.0):
        after = self.clock()
        duration = frames / self.rate
        if self.latency is not None and frames:
            # A blocked write may have consumed most of the interval already.
            # Keep sample continuity, but never advance across a supply gap.
            start = max(
                self._end, self._before + self.latency, after + self.latency - duration
            )
            self._end = start + duration
            try:
                self.output.commit(
                    self.owner,
                    start=start,
                    end=self._end,
                    position=self._frames / self.rate,
                    level=level,
                    now=after,
                )
            except Exception:
                self.latency = None
                self.output.retire(self.owner)
                log.warning("Lighting observation failed; audio continues")
        self._frames += frames
