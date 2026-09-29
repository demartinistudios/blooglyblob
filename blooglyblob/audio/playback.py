"""Single speaker worker with typed completion futures, bounded PCM and barriers."""

from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
import threading

import numpy as np

from .presentation import OutputPresentation, OutputTimeline
from .resampler import DEVICE_SAMPLE_RATE, SPEECH_SAMPLE_RATE, PCMResampler


@dataclass
class Command:
    kind: str
    generation: str | int | None
    data: object = None
    done: Future | None = None


class Playback:
    def __init__(self, stream, on_failure, on_level, *, capacity=20, presentation=None):
        self.presentation = (
            presentation if presentation is not None else OutputPresentation()
        )
        self._visual_owner = None
        self.stream = stream
        self._failure, self._level = on_failure, on_level
        self._capacity = capacity
        self._condition = threading.Condition(threading.RLock())
        self._commands = deque()
        self._generation = None
        self._muted = False
        self._accept = False
        self._stopping = False
        self._fault = None
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="audio-playback"
        )
        self._thread.start()

    @staticmethod
    def _finish(future, error=None):
        if future is not None and not future.done():
            if error:
                future.set_exception(RuntimeError(error))
            else:
                future.set_result(None)

    def begin(self, generation):
        with self._condition:
            if self._fault or self._stopping:
                raise RuntimeError(self._fault or "Playback closed")
            if self._generation is not None:
                raise RuntimeError("Previous playback has not drained or flushed")
            self._generation, self._muted, self._accept = generation, False, True
            self._visual_owner = self.presentation.begin("speech")

    def submit(self, kind, generation=None, data=None):
        # Completion is registered before work can reach the worker.
        future = Future() if kind != "chunk" else None
        with self._condition:
            if self._fault or self._stopping:
                if future is None:
                    raise RuntimeError(self._fault or "Playback closed")
                self._finish(future, self._fault or "Playback closed")
                return future
            if kind in {"chunk", "end", "background_start"} and (
                generation != self._generation or not self._accept or self._muted
            ):
                if kind != "chunk":
                    self._finish(future, "Stale playback generation")
                return future
            if kind == "chunk" and len(data) % 2:
                self._fail(generation, "invalid_pcm")
                return future
            if kind == "flush":
                if generation != self._generation:
                    self._finish(future)
                    return future
                self.presentation.retire(self._visual_owner)
                self._muted, self._accept = True, False
                self._discard_chunks()
            if kind == "end":
                self._accept = False
            pieces = (
                (data[offset : offset + 960] for offset in range(0, len(data), 960))
                if kind == "chunk"
                else [data]
            )
            for piece in pieces:
                if len(self._commands) >= self._capacity:
                    self._fail(generation, "output_overflow")
                    self._finish(future, "output_overflow")
                    break
                self._commands.append(Command(kind, generation, piece, future))
            self._condition.notify()
        return future

    def _discard_chunks(self):
        kept = deque()
        for command in self._commands:
            if command.kind in {"chunk", "background_start"}:
                self._finish(command.done, "Playback muted")
            else:
                kept.append(command)
        self._commands = kept

    def mute(self):
        with self._condition:
            self.presentation.retire(self._visual_owner)
            self._muted, self._accept = True, False
            self._discard_chunks()
            self._condition.notify()

    def _fail(self, generation, reason):
        with self._condition:
            if self._fault is not None:
                return
            self.presentation.retire(self._visual_owner)
            self._fault = reason
            self._muted, self._accept = True, False
            for command in self._commands:
                self._finish(command.done, reason)
            self._commands.clear()
        self._failure(generation, reason)

    def stop(self):
        with self._condition:
            self.presentation.retire(self._visual_owner)
            self._stopping = True
            self._muted = True
            for command in self._commands:
                self._finish(command.done, "Playback stopped")
            self._commands.clear()
            self._condition.notify()
        self._thread.join(timeout=2)
        if self._thread.is_alive():
            raise RuntimeError("Audio writer still owns driver; release not confirmed")

    def _run(self):
        converter = None
        converter_generation = None
        background = None
        background_id = None
        background_generation = None
        background_stops = []
        driver_stopped = False
        timeline = None

        def clear_background(error=None):
            nonlocal background, background_id, background_generation
            background = background_id = background_generation = None
            for future in background_stops:
                self._finish(future, error)
            background_stops.clear()

        def write(pcm, generation, *, voice=True):
            nonlocal driver_stopped, timeline
            for offset in range(0, len(pcm), 1920):
                with self._condition:
                    if self._stopping or self._muted or generation != self._generation:
                        break
                    visual_owner = self._visual_owner
                frame = pcm[offset : offset + 1920]
                samples = np.frombuffer(frame, dtype=np.int16)
                level = (
                    min(
                        1.0,
                        float(np.sqrt(np.mean(np.square(samples, dtype=np.float32))))
                        / 4000,
                    )
                    if voice and len(samples)
                    else 0.0
                )
                self._level(level)
                if background is not None:
                    frame = background.mix(frame)
                if driver_stopped:
                    self.stream.start_stream()
                    driver_stopped = False
                if timeline is None or timeline.owner is not visual_owner:
                    timeline = OutputTimeline(
                        self.stream, DEVICE_SAMPLE_RATE, self.presentation, visual_owner
                    )
                timeline.before_write()
                self.stream.write(frame)
                # retire() fences observations even when mute raced this write.
                timeline.written(len(frame) // 2, level)
                if background is not None and background.finished:
                    clear_background()

        while True:
            with self._condition:
                if self._stopping:
                    break
                if background is not None and (
                    self._muted or background_generation != self._generation
                ):
                    clear_background()
                if not self._commands and background is None:
                    self._level(0.0)
                    self._condition.wait(0.05)
                    continue
                command = (
                    self._commands.popleft()
                    if self._commands
                    else Command("background", background_generation)
                )
            generation = command.generation
            try:
                if command.kind == "background_start":
                    with self._condition:
                        if self._muted or generation != self._generation:
                            self._finish(command.done, "Stale playback generation")
                            continue
                    if background is not None:
                        self._finish(command.done, "Background sound already active")
                        continue
                    background_id, background = command.data
                    background_generation = generation
                    self._finish(command.done)
                elif command.kind == "background_stop":
                    if command.data == background_id and background is not None:
                        background.stop()
                        background_stops.append(command.done)
                    else:
                        self._finish(command.done)
                elif command.kind == "background":
                    write(bytes(1920), generation, voice=False)
                elif command.kind in {"end", "flush"}:
                    clear_background()
                    if converter is not None and converter_generation == generation:
                        if command.kind == "end":
                            write(converter.process(b"", last=True), generation)
                        converter = converter_generation = None
                    self.stream.stop_stream()
                    driver_stopped = True
                    self._level(0.0)
                    self.presentation.retire(self._visual_owner)
                    timeline = None
                    with self._condition:
                        if generation == self._generation:
                            self._generation = None
                    self._finish(command.done)
                elif command.kind == "chunk":
                    with self._condition:
                        if self._muted or generation != self._generation:
                            continue
                    if converter_generation != generation:
                        converter = PCMResampler(SPEECH_SAMPLE_RATE, DEVICE_SAMPLE_RATE)
                        converter_generation = generation
                    write(converter.process(command.data), generation)
            except Exception:
                clear_background("playback_failed")
                self._level(0.0)
                self._finish(command.done, "playback_failed")
                self._fail(generation, "playback_failed")
        self._level(0.0)
        clear_background("Playback stopped")
