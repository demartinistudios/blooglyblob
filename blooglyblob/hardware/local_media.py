"""Local WAV activities using the audio owner's exclusive physical boundary."""
import asyncio
from concurrent.futures import Future
from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import random
import threading
import time
from typing import Any


class HardwareReleaseError(RuntimeError):
    """A native device could not confirm cleanup; optional startup must abort."""


class Worker:
    """A retained daemon thread; completion means the thread actually exited."""

    def __init__(self, operation, name):
        self.error: BaseException | None = None
        self.result: Any = None
        self.done: Future = Future()

        def run():
            try:
                self.result = operation()
            except BaseException as exc:
                self.error = exc
            finally:
                self.done.set_result(None)

        self.thread = threading.Thread(target=run, name=name, daemon=True)
        self.thread.start()

    async def wait(self, timeout=None):
        wrapped = asyncio.wrap_future(self.done)
        try:
            await asyncio.wait_for(asyncio.shield(wrapped), timeout)
        except TimeoutError:
            raise RuntimeError('worker_release_timeout') from None
        deadline = asyncio.get_running_loop().time() + (timeout or 1.)
        while self.thread.is_alive():
            if asyncio.get_running_loop().time() >= deadline:
                raise RuntimeError('worker_release_timeout')
            await asyncio.sleep(.005)
        self.thread.join(0)
        if self.error:
            raise RuntimeError('worker_failed') from None
        return self.result


@dataclass
class Activity:
    identity: Any
    kind: str
    stop: threading.Event = field(default_factory=threading.Event)
    workers: list[Worker] = field(default_factory=list)
    task: asyncio.Task | None = None
    stopping: asyncio.Event = field(default_factory=asyncio.Event)


def dance_move(servos, move_index: int, bpm: float):
    """Original sixteen-position choreography, including every-cycle accent."""
    if servos is None:
        return
    try:
        jitter = random.uniform(-0.05, 0.05)
        pattern_position = move_index % 16
        if pattern_position % 2 == 0:
            left_pos, right_pos = 65 + jitter * 100, 35 + jitter * 100
        else:
            left_pos, right_pos = 35 + jitter * 100, 65 + jitter * 100
        if pattern_position == 0:
            servos.head.look_left(speed=2.5)
        elif pattern_position == 4:
            servos.head.center(speed=2.5)
        elif pattern_position == 8:
            servos.head.look_right(speed=2.5)
        elif pattern_position == 12:
            servos.head.center(speed=2.5)
        if pattern_position == 0 and move_index > 0:
            servos.left_arm.set_percent(80, speed=3.0)
            servos.right_arm.set_percent(80, speed=3.0)
            time.sleep(0.15)
        servos.left_arm.set_percent(left_pos, speed=2.5)
        servos.right_arm.set_percent(right_pos, speed=2.5)
    except Exception:
        logging.getLogger(__name__).warning('dance_move_failed')



class LocalMedia:
    """Reserve on the loop before dispatch, and retain failures for shutdown.

    The caller supplies paths whose resource contexts outlive close(). Completion
    callbacks run on the owning loop after all writers and audio.release finish.
    """

    def __init__(self, audio, hardware, *, timeout=3.):
        self.audio, self.hardware = audio, hardware
        self.timeout = timeout
        self.active: Activity | None = None
        self.fault: str | None = None
        self.ownership_uncertain = False
        self.closed = False
        self._loop = asyncio.get_running_loop()

    @property
    def dancing(self):
        return self.active is not None and self.active.kind == 'dance'

    def mute(self):
        # A GPIO callback only sets events, never waits for native work.
        active = self.active
        if active:
            active.stop.set()
            self.audio.presentation.retire(active.stop)
            self._loop.call_soon_threadsafe(active.stopping.set)

    def _reserve(self, kind, identity):
        if self.closed or self.fault:
            raise RuntimeError(self.fault or 'Media closed')
        if self.active:
            raise RuntimeError('Local media already active')
        activity = Activity(identity, kind)
        self.active = activity
        activity.task = asyncio.create_task(self._run(activity), name='local-media')
        activity.task.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
        return activity

    def start_dance(self, identity):
        if self.fault or self.closed:
            raise RuntimeError(self.fault or 'Media closed')
        if self.dancing:
            return 'Already dancing!'
        self._reserve('dance', identity)
        return 'Dance mode starting'

    async def chime(self, identity):
        activity = self._reserve('chime', identity)
        await asyncio.shield(activity.task)

    async def stop(self):
        self.mute()
        activity = self.active
        if activity and activity.task:
            # _run bounds each native completion itself. Do not cancel cleanup.
            await asyncio.shield(activity.task)
        if self.fault:
            raise RuntimeError(self.fault)

    async def close(self):
        self.closed = True
        await self.stop()

    async def _run(self, activity):
        reason = 'media_release_failed'
        try:
            # The previous conversation's native writer must close first.
            await self.audio.release()
            reason = 'media_worker_failed'
            if not activity.stop.is_set():
                operation = (lambda: self._dance(activity)) if activity.kind == 'dance' else (
                    lambda: self.audio.play_file(self.hardware.alert_path, activity.stop, output_rate=48000))
                worker = Worker(operation, 'local-' + activity.kind)
                activity.workers.append(worker)
                # Sleep until either physical completion or a control notification.
                # Cancellation of these waits never cancels the native worker.
                finished = asyncio.create_task(worker.wait())
                stopped = asyncio.create_task(activity.stopping.wait())
                try:
                    await asyncio.wait((finished, stopped), return_when=asyncio.FIRST_COMPLETED)
                    await worker.wait(self.timeout)
                finally:
                    for waiter in (finished, stopped):
                        waiter.cancel()
                    await asyncio.gather(finished, stopped, return_exceptions=True)
            reason = 'media_release_failed'
            await self.audio.release()
        except Exception:
            activity.stop.set()
            live = any(worker.thread.is_alive() for worker in activity.workers)
            if reason == 'media_release_failed' or live:
                self.ownership_uncertain = True
                reason = 'media_release_failed' if reason == 'media_release_failed' else 'media_release_timeout'
                self.fault = reason
            else:
                # An exited worker may fail without retaining physical ownership.
                # Observe the audio owner's release before allowing another activity.
                try:
                    await self.audio.release()
                except Exception:
                    self.ownership_uncertain = True
                    reason = self.fault = 'media_release_failed'
                else:
                    if self.active is activity:
                        self.active = None
            self.hardware.report_failure(activity.identity, reason)
            raise RuntimeError(reason) from None
        else:
            if self.active is activity:
                self.active = None
            if activity.kind == 'dance' and not self.closed:
                self.hardware.dance_finished(activity.identity)

    def _dance(self, activity):
        hw = self.hardware
        if not hw.animation_lock.acquire(timeout=5.):
            raise RuntimeError('dance_animation_busy')
        audio_worker = None
        try:
            if activity.stop.is_set():
                return
            if hw.ambient:
                hw.ambient.hold_all(300.)
            with Path(hw.beats_path).open() as source:
                beat_data = json.load(source)
            analysis = hw.music_lights
            if analysis is not None and not analysis.matches(hw.dance_path):
                logging.getLogger(__name__).warning('Dance mouth disabled: selected WAV changed since preparation')
                hw.music_lights = analysis = None
            hw.lighting.music(analysis)
            audio_worker = Worker(lambda: self.audio.play_file(hw.dance_path, activity.stop, music=True), 'dance-audio')
            activity.workers.append(audio_worker)
            start = time.time()
            for move_index, beat_index in enumerate(range(0, len(beat_data['beats']), 2)):
                beat_time = beat_data['beats'][beat_index]
                while not activity.stop.is_set():
                    remaining = beat_time - (time.time() - start)
                    if remaining <= 0:
                        break
                    activity.stop.wait(min(remaining, .05))
                if activity.stop.is_set():
                    break
                if audio_worker.error:
                    raise RuntimeError('dance_audio_failed')
                dance_move(hw.servos, move_index, beat_data['bpm'])
            if not activity.stop.is_set():
                audio_worker.thread.join(timeout=10.)
        finally:
            activity.stop.set()
            if audio_worker:
                audio_worker.thread.join(timeout=self.timeout)
                if audio_worker.thread.is_alive():
                    # Preserve the lock and all ownership records on uncertainty.
                    raise RuntimeError('dance_audio_release_timeout')
            try:
                if hw.servos:
                    hw.servos.head.center(speed=1.)
                    hw.servos.left_arm.down(speed=1.)
                    hw.servos.right_arm.down(speed=1.)
                if hw.ambient:
                    hw.ambient.hold_all(0)
            finally:
                hw.animation_lock.release()
        if audio_worker and audio_worker.error:
            raise RuntimeError('dance_audio_failed')
