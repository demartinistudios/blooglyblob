"""Bounded numeric observations; never retain audio, text, or provider payloads."""

import asyncio
import json
import logging
import math
import threading
import time

import numpy as np

_LOG = logging.getLogger(__name__)
_COUNTS = frozenset(
    """
capture_callbacks capture_samples capture_status capture_overflows capture_queue_full
capture_processed_samples handoff_received_samples handoff_delivered_samples
handoff_discarded_samples input_received_samples input_accepted_samples
input_not_listening_samples input_enqueued_samples input_sent_samples
input_discarded_samples output_received_samples output_delivered_samples
output_discarded_samples output_gated_samples output_stale_samples
playback_submitted_samples playback_written_samples playback_discarded_samples
background_written_samples user_transcript_events assistant_transcript_events
delegations tool_results gate_starts gate_corrections
scanner_starts scanner_stops session_starts session_ends
exit_idle exit_ceiling exit_failed exit_cancelled
""".split()
)
_MAXIMA = frozenset(
    """
capture_queue_packets capture_age_ms handoff_queue_packets handoff_age_ms
input_queue_frames input_age_ms input_send_ms output_queue_frames output_queue_events
output_age_ms playback_queue_frames playback_write_ms loop_lag_ms
""".split()
)
_LEVELS = frozenset({"mic_raw", "mic_processed"})


class AudioDiagnostics:
    """One fixed-size accumulator shared by the loop and audio workers.

    Recording does no I/O. PCM reduction happens on the capture worker, never
    the PortAudio callback. Each snapshot consumes one reporting window; empty
    windows produce no log. Names are allowlisted to prevent accidental content
    logging or unbounded metric cardinality.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._counts = {}
        self._maxima = {}
        self._levels = {}

    def count(self, name, value=1):
        if name in _COUNTS and value:
            with self._lock:
                self._counts[name] = self._counts.get(name, 0) + value

    def maximum(self, name, value):
        if name in _MAXIMA and math.isfinite(value):
            with self._lock:
                self._maxima[name] = max(self._maxima.get(name, 0), value)

    def pcm(self, name, pcm):
        if name not in _LEVELS or not pcm:
            return
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float64)
        total, square = len(samples), float(np.dot(samples, samples))
        magnitude = np.abs(samples)
        peak = int(np.max(magnitude))
        clipped = int(np.count_nonzero(magnitude >= 32767))
        with self._lock:
            old = self._levels.get(name, (0, 0.0, 0, 0))
            self._levels[name] = (
                old[0] + total,
                old[1] + square,
                max(old[2], peak),
                old[3] + clipped,
            )

    def snapshot(self):
        with self._lock:
            counts, maxima, levels = self._counts, self._maxima, self._levels
            self._counts, self._maxima, self._levels = {}, {}, {}
        return {
            "counts": counts,
            "max": {key: round(value, 2) for key, value in maxima.items()},
            "levels": {
                key: {
                    "samples": n,
                    "rms": round(math.sqrt(square / n), 2),
                    "peak": peak,
                    "clipped": clipped,
                }
                for key, (n, square, peak, clipped) in levels.items()
            },
        }

    def report(self):
        summary = self.snapshot()
        if any(summary.values()):
            _LOG.info(
                "Audio diagnostics: %s", json.dumps(summary, separators=(",", ":"))
            )

    async def run(self):
        while True:
            started = time.monotonic()
            await asyncio.sleep(10)
            # Do not create idle logs just to record the reporter's own timer.
            with self._lock:
                active = bool(self._counts)
            if active:
                self.maximum(
                    "loop_lag_ms", max(0, time.monotonic() - started - 10) * 1000
                )
            self.report()
