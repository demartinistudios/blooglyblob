"""Direct audio operations with one physical owner and confirmed completions."""

import asyncio
from concurrent.futures import Future
from pathlib import Path
import threading
import wave

from .background import BackgroundSound
from .diagnostics import AudioDiagnostics
from .capture import CaptureHandoff
from .driver import AudioDriver, select_input_device, select_output_device
from .playback import Playback
from .presentation import OutputPresentation, OutputTimeline
from .resampler import PCMResampler


async def _ignore_input(pcm):
    pass


class AudioController:
    """Create on the application loop. No device opens until begin/play_file.

    Driver factories return an object exposing start(on_input, on_failure),
    out_stream, and stop(). Only the owned writer calls the output stream.
    on_failure runs on the loop; on_level runs on the writer thread.
    Cancellation stops waiting, never cancels ownership cleanup. on_input must
    cooperate with cancellation and must not call this controller's lifecycle
    methods: release cancels and joins its epoch consumer before reopening.
    Activity failures clear only after full release; ownership uncertainty never
    clears within this application instance.
    """

    def __init__(
        self,
        *,
        driver_factory=None,
        diagnostics=None,
        on_input=_ignore_input,
        on_failure=lambda *_: None,
        on_level=lambda _: None,
        operation_timeout=5.0,
    ):
        self.diagnostics = diagnostics or AudioDiagnostics()
        self.presentation = OutputPresentation()
        self._loop = asyncio.get_running_loop()
        self._factory = driver_factory or (
            lambda: AudioDriver(diagnostics=self.diagnostics)
        )
        self._failure, self._level = on_failure, on_level
        self._driver = self._writer = None
        self._generation = None
        self._epoch = 0
        self._retirement = 0
        self._mute_version = 0
        self._capture_generation = None
        self._capture = CaptureHandoff(
            on_input,
            self._capture_failed,
            diagnostics=self.diagnostics,
            retirement_timeout=min(1.0, operation_timeout),
        )
        self._physical = threading.Lock()
        self._serial = asyncio.Lock()
        self._operations = set()
        self._fault = None
        self._ownership_uncertain = False
        self._closed = False
        self._background = None
        self._file_stop = None
        self._timeout = operation_timeout

    @property
    def ownership_uncertain(self):
        return self._ownership_uncertain

    def _notify_failure(self, generation, reason):
        if reason in {
            "audio_ownership_timeout",
            "audio_release_failed",
            "file_release_failed",
            "capture_retirement_timeout",
        }:
            self._ownership_uncertain = True
        if self._fault is None:
            self._fault = reason
            self.mute()
            self._capture.stop()
            self._failure(generation, reason)

    def _capture_failed(self, epoch, reason):
        if epoch == self._epoch:
            self._notify_failure(self._capture_generation, reason)

    def _driver_failed(self, epoch, reason):
        self._loop.call_soon_threadsafe(self._capture_failed, epoch, reason)

    def _playback_failed(self, epoch, generation, reason):
        self._loop.call_soon_threadsafe(
            self._accept_playback_failure, epoch, generation, reason
        )

    def _accept_playback_failure(self, epoch, generation, reason):
        if epoch == self._epoch and generation == self._generation:
            self._notify_failure(generation, reason)

    async def _native(self, operation):
        # An owned daemon avoids an uninterruptible default-executor shutdown.
        done = Future()

        def run():
            try:
                done.set_result(operation())
            except BaseException as exc:
                done.set_exception(exc)

        threading.Thread(target=run, daemon=True, name="audio-lifecycle").start()
        return await asyncio.shield(asyncio.wrap_future(done))

    async def _owned(self, operation):
        async def serialized():
            async with self._serial:
                return await operation()

        task = self._loop.create_task(serialized(), name="audio-operation")
        self._operations.add(task)

        def finished(completed):
            self._operations.discard(completed)
            if not completed.cancelled():
                completed.exception()  # Retiring operations remain observed.

        task.add_done_callback(finished)
        try:
            return await asyncio.wait_for(asyncio.shield(task), self._timeout)
        except TimeoutError:
            self._notify_failure(self._generation, "audio_ownership_timeout")
            raise RuntimeError("Audio ownership completion not confirmed") from None

    async def check_devices(self):
        def check():
            import pyaudio

            pa = pyaudio.PyAudio()
            try:
                devices = [
                    pa.get_device_info_by_index(i) for i in range(pa.get_device_count())
                ]
                select_input_device(pa, devices=devices)
                select_output_device(pa, devices=devices)
            finally:
                try:
                    pa.terminate()
                except Exception:
                    self._loop.call_soon_threadsafe(
                        self._notify_failure, None, "audio_release_failed"
                    )
                    raise

        await self._owned(lambda: self._native(check))

    async def prepare(self, search_sound_path: str | Path):
        async def prepare():
            self._background = await self._native(
                lambda: BackgroundSound.from_wav(search_sound_path)
            )

        await self._owned(prepare)

    async def begin(self, generation):
        retirement = self._retirement
        mute_version = self._mute_version

        async def start():
            if self._closed or self._fault or retirement != self._retirement:
                raise RuntimeError(self._fault or "Audio closed or retiring")
            if self._driver is None:
                if not self._physical.acquire(blocking=False):
                    raise RuntimeError("Local media still owns audio")
                self._epoch += 1
                epoch = self._epoch
                try:
                    await self._capture.begin(epoch)
                except Exception:
                    self._notify_failure(generation, "capture_retirement_timeout")
                    raise
                self._capture_generation = generation
                try:
                    self._driver = self._factory()
                except Exception:
                    self._physical.release()
                    self._capture.stop()
                    raise
                try:
                    await self._native(
                        lambda: self._driver.start(
                            lambda pcm: self._capture.submit(epoch, pcm),
                            lambda reason: self._driver_failed(epoch, reason),
                        )
                    )
                    if self._fault:
                        raise RuntimeError(self._fault)
                except Exception:
                    self._notify_failure(generation, "audio_start_failed")
                    raise
                if self._closed or retirement != self._retirement:
                    raise RuntimeError("Audio startup superseded by release")
                self._writer = Playback(
                    self._driver.out_stream,
                    lambda gen, reason: self._playback_failed(epoch, gen, reason),
                    self._level,
                    presentation=self.presentation,
                    diagnostics=self.diagnostics,
                )
            if mute_version != self._mute_version:
                raise RuntimeError("Audio startup muted")
            self._generation = generation
            self._capture_generation = generation
            self._writer.begin(generation)

        await self._owned(start)

    async def audio(self, generation, pcm):
        if self._writer is not None:
            self._writer.submit("chunk", generation, pcm)

    async def _completion(self, kind, generation=None, data=None):
        if self._writer is None:
            if kind == "end" or (kind == "flush" and self._physical.locked()):
                raise RuntimeError("Audio playback ownership is not active")
            return
        future = self._writer.submit(kind, generation, data)
        wrapped = asyncio.wrap_future(future)
        # Observe exceptions even when the caller cancels its shielded wait.
        wrapped.add_done_callback(
            lambda done: done.exception() if not done.cancelled() else None
        )
        try:
            await asyncio.wait_for(asyncio.shield(wrapped), self._timeout)
        except TimeoutError:
            self._notify_failure(generation, "audio_ownership_timeout")
            raise RuntimeError("Audio ownership completion not confirmed") from None

    async def drain(self, generation):
        await self._completion("end", generation)

    async def flush(self, generation):
        await self._completion("flush", generation)

    async def start_background(self, activity_id, generation):
        if self._background is None or self._writer is None:
            raise RuntimeError("Background sound is not prepared or audio is inactive")
        await self._completion(
            "background_start", generation, (activity_id, self._background.fresh())
        )

    async def stop_background(self, activity_id):
        await self._completion("background_stop", self._generation, activity_id)

    def mute(self):
        """GPIO-safe: bounded local work, no loop, cloud or driver wait."""
        self.presentation.mute()
        self._mute_version += 1
        if self._file_stop is not None:
            self._file_stop.set()
        if self._writer is not None:
            self._writer.mute()

    async def release(self):
        self._retirement += 1
        self.mute()
        self._capture.stop()

        async def stop():
            self._capture.stop()  # Also invalidate a startup that completed late.
            try:
                await self._capture.retire()
            except Exception:
                self._notify_failure(self._generation, "capture_retirement_timeout")
                raise
            if self._driver is not None:
                try:
                    if self._writer:
                        await self._native(self._writer.stop)
                    await self._native(self._driver.stop)
                except Exception:
                    self._notify_failure(self._generation, "audio_release_failed")
                    raise
                self._writer = self._driver = None
                self._physical.release()
            elif self._physical.locked():
                self._notify_failure(self._generation, "audio_release_failed")
                raise RuntimeError("Local media release not confirmed")
            self._generation = None
            self._capture_generation = None
            self._epoch += 1  # Late failures cannot attach to a new physical owner.
            if not self._ownership_uncertain:
                self._fault = None

        await self._owned(stop)

    async def close(self):
        self._closed = True
        try:
            await self.release()
        finally:
            await self._capture.close()

    def play_file(self, path, stop_event, *, output_rate=None, music=False):
        """Blocking WAV playback for the hardware owner's joined media worker.

        output_rate preserves the alert's 48 kHz conversion; dance uses native WAV rate.
        Returns only after stream/PortAudio close. The hardware owner must join
        this worker before release; an occupied driver is never replaced.
        """
        if self._closed or self._fault or not self._physical.acquire(blocking=False):
            raise RuntimeError("Audio is unavailable or already owned")
        self._file_stop = stop_event
        pa = stream = None
        visual_owner = self.presentation.begin("music", stop_event) if music else None
        released = False
        try:
            import pyaudio

            pa = pyaudio.PyAudio()
            with wave.open(str(path), "rb") as source:
                converter = None
                if output_rate is not None:
                    if source.getnchannels() != 1 or source.getsampwidth() != 2:
                        raise ValueError("Rate conversion requires mono PCM16")
                    converter = PCMResampler(source.getframerate(), output_rate)
                stream = pa.open(
                    format=pa.get_format_from_width(source.getsampwidth()),
                    channels=source.getnchannels(),
                    rate=output_rate or source.getframerate(),
                    output=True,
                    output_device_index=select_output_device(pa),
                )
                timeline = (
                    OutputTimeline(
                        stream, source.getframerate(), self.presentation, visual_owner
                    )
                    if music
                    else None
                )
                while not stop_event.is_set():
                    pcm = source.readframes(1024)
                    if not pcm:
                        break
                    if converter is not None:
                        pcm = converter.process(pcm)
                    if pcm and not stop_event.is_set():
                        if timeline:
                            timeline.before_write()
                        stream.write(pcm)
                        if timeline and not stop_event.is_set():
                            timeline.written(
                                len(pcm)
                                // (source.getnchannels() * source.getsampwidth())
                            )
                if converter is not None and not stop_event.is_set():
                    tail = converter.process(b"", last=True)
                    if tail and not stop_event.is_set():
                        stream.write(tail)
        except BaseException:
            self.presentation.retire(visual_owner)
            raise
        finally:
            try:
                if stream:
                    stream.stop_stream()
                    stream.close()
                if pa:
                    pa.terminate()
                released = True
            finally:
                self.presentation.retire(visual_owner)
                if released:
                    self._file_stop = None
                    self._physical.release()
                else:
                    self._loop.call_soon_threadsafe(
                        self._notify_failure, self._generation, "file_release_failed"
                    )
