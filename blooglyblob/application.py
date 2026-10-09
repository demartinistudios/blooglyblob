"""The single application composition root and bounded lifecycle."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from typing import TYPE_CHECKING, TypeVar

from concurrent.futures import Future, ThreadPoolExecutor
import logging
import math
import os
import signal
import socket
import threading
import time

from blooglyblob.audio.diagnostics import AudioDiagnostics
from blooglyblob.config import validate_settings
from blooglyblob.connectivity import Availability, ReachabilityProbe, failure_category

if TYPE_CHECKING:
    from openai import AsyncOpenAI
    from blooglyblob.config import AIConfig
    from blooglyblob.audio.controller import AudioController
    from blooglyblob.hardware.controller import HardwareController
    from blooglyblob.conversation import ConversationSession
    from blooglyblob.ai.speech import OpenAISpeech
    from blooglyblob.tools.executor import ToolExecutor
    from blooglyblob.tools.timer_manager import TimerManager
    from blooglyblob.tools.ring_handler import RingHandler

T = TypeVar("T")

logger = logging.getLogger(__name__)
OWNERSHIP_UNCERTAIN_EXIT = 73
SHUTDOWN_SECONDS = 15.0
STARTUP_SECONDS = 25.0


class OwnershipUncertain(RuntimeError):
    """An owner did not confirm closure; require an inspected explicit restart."""


def notify_ready() -> None:
    """Notify from the owning process; no listener and no cloud request."""
    address = os.environ.get("NOTIFY_SOCKET")
    if address:
        if address.startswith("@"):
            address = "\0" + address[1:]
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as channel:
            channel.settimeout(1.0)
            channel.connect(address)
            channel.sendall(b"READY=1")


class Application:
    def __init__(
        self,
        *,
        config: AIConfig,
        audio_factory: Callable[..., AudioController] | None = None,
        hardware_factory: Callable[..., HardwareController] | None = None,
        ready: Callable[[], None] = notify_ready,
        connectivity_probe: Callable[[], Awaitable[bool]] | None = None,
        shutdown_seconds: float = SHUTDOWN_SECONDS,
        on_shutdown: Callable[[], None] = lambda: None,
    ) -> None:
        self.diagnostics = AudioDiagnostics()
        self.config = config
        self.audio: AudioController | None = None
        self.hardware: HardwareController | None = None
        self.session: ConversationSession | None = None
        self._api: AsyncOpenAI | None = None
        self._executor: ToolExecutor | None = None
        self._pool: ThreadPoolExecutor | None = None
        self._timer_manager: TimerManager | None = None
        self._ring_handler: RingHandler | None = None
        self._speech: OpenAISpeech | None = None
        self.availability: Availability | None = None
        self._connectivity_probe = connectivity_probe
        self._greeting_task: asyncio.Task[None] | None = None
        self._greeting_prepared = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopping = False
        self._ready = False
        self._faulted = False
        self._stop_task: asyncio.Task[None] | None = None
        self._shutdown_deadline: float | None = None
        self._done = asyncio.Event()
        self._tasks: set[asyncio.Task[None]] = set()
        self._workers: set[Future] = set()
        self._audio_factory, self._hardware_factory = audio_factory, hardware_factory
        self._notify_ready = ready
        if not math.isfinite(shutdown_seconds) or shutdown_seconds <= 0:
            raise ValueError("Shutdown deadline must be positive and finite")
        self.shutdown_seconds, self._on_shutdown = shutdown_seconds, on_shutdown

    def _fault(self) -> None:
        self._faulted = True
        if self.audio:
            self.audio.mute()
        if self.hardware:
            self.hardware.mute_media()
            self.hardware.light("fault")
        self._shutdown_requested()

    def _can_start(self) -> bool:
        return bool(
            self.availability and self.availability.ready and not self._stopping
        )

    def _availability_changed(self, available: bool) -> None:
        if self._stopping:
            return
        if self.hardware:
            self.hardware.set_unavailable(not available)
        if not available:
            if (
                self._greeting_task
                and self._greeting_task is not asyncio.current_task()
            ):
                self._greeting_task.cancel()
            if self.session:
                self.session.suspend()
        elif not self._greeting_prepared:
            self._greeting_task = self._own(self._prepare_greeting())

    def _unavailable(self, reason: str) -> None:
        if self.availability:
            self.availability.fail(reason)

    def _button(self) -> None:
        if self._ready and not self._stopping:
            assert self.session is not None  # Readiness requires a constructed session.
            self.session.button()

    def _media_failure(self, identity: str | None, reason: str) -> None:
        if self.session:
            self.session.media_failed(identity, reason)
        elif (self.audio and self.audio.ownership_uncertain) or (
            self.hardware and self.hardware.ownership_uncertain
        ):
            self._fault()
        logger.warning("Owned worker failed: %s", reason)

    def _dance_finished(self, identity: str) -> None:
        if self.session and not self._stopping:
            self.session.dance_finished(identity)

    async def _audio_input(self, pcm: bytes) -> None:
        if self._ready and not self._stopping:
            assert self.session is not None  # Readiness requires a constructed session.
            await self.session.input_audio(pcm)

    def _level(self, level: float) -> None:
        if self.hardware:
            self.hardware.set_level(level)

    def _alert_from_thread(self, message: str) -> None:
        if self._loop and not self._stopping:
            self._loop.call_soon_threadsafe(self._alert, message)

    def _alert(self, message: str) -> None:
        if self._ready and not self._stopping:
            assert self.session is not None  # Readiness requires a constructed session.
            self.session.alert(message)

    async def _work(self, operation: Callable[[], T]) -> T:
        assert self._pool is not None  # Work is submitted only after startup.
        future = self._pool.submit(operation)
        self._workers.add(future)

        def completed(future: Future[T]) -> None:
            self._workers.discard(future)
            if not future.cancelled():
                future.exception()

        future.add_done_callback(completed)
        return await asyncio.wrap_future(future)

    def _own(self, coroutine: Coroutine[object, object, None]) -> asyncio.Task[None]:
        task = asyncio.create_task(coroutine)
        self._tasks.add(task)

        def completed(task: asyncio.Task[None]) -> None:
            self._tasks.discard(task)
            if not task.cancelled() and task.exception():
                logger.warning(
                    "Application background task failed (%s)",
                    type(task.exception()).__name__,
                )

        task.add_done_callback(completed)
        return task

    async def _prepare_greeting(self) -> None:
        from blooglyblob.ai.voice_profile import default_greeting
        from blooglyblob.conversation import GREETING_SPEED

        try:
            assert self._speech is not None
            await self._speech.prepare(default_greeting(), speed=GREETING_SPEED)
            self._greeting_prepared = True
        except Exception as error:
            category = failure_category(error)
            if category:
                self._unavailable(category)
            logger.warning(
                "Greeting preparation failed (%s); speech will stream on demand",
                type(error).__name__,
            )

    async def start(self) -> None:
        # No API or hardware construction before all session limits validate.
        validate_settings(os.environ)
        limits = {
            "inactivity_seconds": float(os.getenv("OPENAI_INACTIVITY_SECONDS", "20")),
            "max_session_seconds": float(
                os.getenv("OPENAI_SESSION_MAX_SECONDS", "600")
            ),
        }
        if any(not math.isfinite(value) or value <= 0 for value in limits.values()):
            raise ValueError("Session limits must be positive and finite")
        if self._stopping or self._loop:
            raise RuntimeError("Application already started or stopping")
        from openai import AsyncOpenAI
        from blooglyblob.ai.alert_ack import OpenAIAlertAcknowledgement
        from blooglyblob.ai.live import OpenAILiveSession
        from blooglyblob.ai.responses import prepare_responses
        from blooglyblob.ai.speech import OpenAISpeech
        from blooglyblob.ai.voice_profile import (
            backend_instructions,
            default_greeting,
            default_speech_voice,
            default_voice,
            live_instructions,
            output_effect_factory,
        )
        from blooglyblob.audio.controller import AudioController
        from blooglyblob.conversation import ConversationSession
        from blooglyblob.hardware.controller import HardwareController
        from blooglyblob.tools.content_search import ContentSearch
        from blooglyblob.tools.executor import ToolExecutor
        from blooglyblob.tools.handlers import ToolHandlers
        from blooglyblob.tools.registry import ToolRegistry
        from blooglyblob.tools.ring_handler import RingHandler
        from blooglyblob.tools.roku_controller import RokuController
        from blooglyblob.tools.timer_manager import TimerManager

        self._loop = asyncio.get_running_loop()
        self._pool = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="application-work"
        )
        try:
            registry = ToolRegistry()
            registry.load_from_configs()
            # Read resources before activating hardware.
            instructions, backend, greeting = (
                live_instructions(),
                backend_instructions(),
                default_greeting(),
            )
            voice = os.getenv("OPENAI_VOICE", default_voice())
            effect = output_effect_factory()
            self._api = AsyncOpenAI(
                api_key=self.config.openai_api_key, max_retries=0, timeout=30.0
            )
            self._speech = self._speech or OpenAISpeech(
                client=self._api,
                voice=os.getenv(
                    "OPENAI_SPEECH_VOICE",
                    os.getenv("OPENAI_VOICE", default_speech_voice()),
                ),
                model=os.getenv("OPENAI_SPEECH_MODEL", "gpt-4o-mini-tts"),
            )
            await self._work(lambda: prepare_responses(self._api))
            self._check_starting()
            self.audio = (self._audio_factory or AudioController)(
                diagnostics=self.diagnostics,
                on_input=self._audio_input,
                on_failure=self._media_failure,
                on_level=self._level,
            )
            await self.audio.check_devices()
            self._check_starting()
            self.hardware = (self._hardware_factory or HardwareController)(
                self.audio,
                on_button=self._button,
                on_dance_finished=self._dance_finished,
                on_failure=self._media_failure,
            )
            self.hardware.set_unavailable(True)
            await self.hardware.prepare()
            self._check_starting()
            try:
                search_path = self.hardware.search_path
                assert (
                    search_path is not None
                )  # Hardware.prepare resolves bundled resources.
                await self.audio.prepare(search_path)
            except (OSError, ValueError):
                logger.warning("Optional scanner sound unavailable")
            self._check_starting()
            self._timer_manager = TimerManager(
                alert_callback=lambda timer: self._alert_from_thread(
                    "Hey! Your " + (timer.label[:120] or "timer") + " timer is done!"
                )
            )
            self._ring_handler = RingHandler(
                on_doorbell=lambda: self._alert_from_thread(
                    "Someone is at the front door!"
                )
            )
            tmdb, roku = os.getenv("TMDB_API_KEY"), os.getenv("ROKU_IP")
            roku_controller = (
                await self._work(lambda: RokuController(roku)) if roku else None
            )
            self._check_starting()
            handlers = ToolHandlers(
                content_search=ContentSearch(
                    tmdb_api_key=tmdb, watchmode_api_key=os.getenv("WATCHMODE_API_KEY")
                )
                if tmdb
                else None,
                roku_controller=roku_controller,
                timer_manager=self._timer_manager,
            )

            async def terminal(name: str, params: dict[str, object]) -> str:
                assert self.session is not None
                return self.session.terminal(name, params)

            self._executor = ToolExecutor(
                hardware=self.hardware,
                handlers=handlers,
                terminal=terminal,
                pool=self._pool,
            )
            model = os.getenv("OPENAI_RESPONSES_MODEL", "gpt-5.6-terra")
            self.availability = Availability(
                probe=self._connectivity_probe
                or ReachabilityProbe(str(self._api.base_url)),
                changed=self._availability_changed,
                live_connected=lambda: bool(
                    self.session and self.session.live_connected
                ),
            )
            self.session = ConversationSession(
                audio=self.audio,
                hardware=self.hardware,
                diagnostics=self.diagnostics,
                on_fault=self._fault,
                can_start=self._can_start,
                on_unavailable=self._unavailable,
                api=self._api,
                live_factory=OpenAILiveSession,
                instructions=instructions,
                voice_effect_factory=effect,
                voice=voice,
                greeting=greeting,
                model=os.getenv("OPENAI_LIVE_MODEL", "gpt-live-1"),
                registry=registry,
                executor=self._executor,
                backend_instructions=backend,
                backend_work=self._work,
                responses_model=model,
                speech=self._speech,
                acknowledge=OpenAIAlertAcknowledgement(self._api, model=model),
                inactivity_seconds=limits["inactivity_seconds"],
                max_session_seconds=limits["max_session_seconds"],
            )
            self._timer_manager.start()
            if self._ring_handler.is_available:
                self._ring_handler.start()
            if self._stopping or self._faulted:
                raise OwnershipUncertain("Startup ownership unconfirmed")
            self._ready = True
            self._notify_ready()
            self._own(self.availability.run())
            self._own(self.diagnostics.run())
            await asyncio.sleep(0)  # Start monitoring without waiting for the network.
            logger.info("Application ready: local controls initialized")
        except BaseException:
            await self.stop()
            raise

    def _begin_shutdown(self) -> None:
        if self._stopping:
            return
        self._stopping, self._ready = True, False
        self._shutdown_deadline = time.monotonic() + self.shutdown_seconds
        self._on_shutdown()
        if self.audio:
            self.audio.mute()
        if self.hardware:
            self.hardware.mute_media()
        if self._executor:
            self._executor.close()

    def _shutdown_requested(self) -> None:
        self._begin_shutdown()
        self._done.set()

    def _check_starting(self) -> None:
        if self._stopping:
            raise asyncio.CancelledError

    async def _stop_producer(self, component: TimerManager | RingHandler) -> None:
        # Two fixed lifecycle workers cannot queue behind four blocked tools.
        future: Future[None] = Future()
        self._workers.add(future)

        def stop() -> None:
            try:
                future.set_result(component.stop())
            except BaseException as error:
                future.set_exception(error)
            finally:
                self._workers.discard(future)

        threading.Thread(target=stop, daemon=True, name="integration-stop").start()
        wrapped = asyncio.wrap_future(future)
        wrapped.add_done_callback(
            lambda task: task.exception() if not task.cancelled() else None
        )
        await asyncio.shield(wrapped)

    async def _cleanup(self) -> None:
        errors = []

        async def bounded(operation: Coroutine[object, object, None]) -> None:
            task = asyncio.create_task(operation)
            task.add_done_callback(
                lambda done: done.exception() if not done.cancelled() else None
            )
            done, _ = await asyncio.wait(
                {task}, timeout=min(3.0, self.shutdown_seconds / 5)
            )
            if not done:
                errors.append("OwnerStillRunning")
            elif task.cancelled() or task.exception():
                errors.append("OwnerCloseFailed")

        operations = [
            self._stop_producer(component)
            for component in (self._timer_manager, self._ring_handler)
            if component
        ]
        if self.session:
            operations.append(self.session.close())
        await asyncio.gather(*(bounded(operation) for operation in operations))
        for task in tuple(self._tasks):
            task.cancel()
        # Independent closure is attempted even when another owner is stuck.
        for component in (self.hardware, self.audio, self._api):
            if component:
                await bounded(component.close())
        if self._tasks:
            done, pending = await asyncio.wait(
                tuple(self._tasks), timeout=min(1.0, self.shutdown_seconds / 5)
            )
            if pending:
                errors.append("TaskStillRunning")
        self.diagnostics.report()
        if self._pool:
            self._pool.shutdown(wait=False, cancel_futures=True)
        assert self._shutdown_deadline is not None  # Cleanup follows _begin_shutdown.
        remaining = max(0.0, self._shutdown_deadline - time.monotonic() - 0.02)
        futures = [asyncio.wrap_future(future) for future in tuple(self._workers)]
        for future in futures:
            future.add_done_callback(
                lambda done: done.exception() if not done.cancelled() else None
            )
        waiting = []
        if futures:
            waiting.append(asyncio.wait(futures, timeout=remaining))
        if self._executor:
            waiting.append(self._executor.wait_closed(remaining))
        await asyncio.gather(*waiting)
        # Completion can reach the loop before worker-side tracking is removed.
        unfinished_workers = any(not worker.done() for worker in tuple(self._workers))
        if unfinished_workers or (self._executor and self._executor.pending):
            errors.append("WorkerStillRunning")
        if (self.audio and getattr(self.audio, "ownership_uncertain", False)) or (
            self.hardware and getattr(self.hardware, "ownership_uncertain", False)
        ):
            errors.append("OwnershipUncertain")
        if errors:
            logger.error("Application cleanup unconfirmed: %s", ",".join(errors))
            self._faulted = True

    async def stop(self) -> None:
        if self._stop_task is None:
            self._begin_shutdown()
            self._stop_task = asyncio.create_task(self._cleanup())
            self._stop_task.add_done_callback(
                lambda task: task.exception() if not task.cancelled() else None
            )
        assert self._shutdown_deadline is not None
        done, _ = await asyncio.wait(
            {self._stop_task},
            timeout=max(0.0, self._shutdown_deadline - time.monotonic()),
        )
        if not done:
            self._faulted = True
            logger.error("Application shutdown deadline exceeded")
        elif self._stop_task.exception():
            self._faulted = True
        if self._faulted:
            raise OwnershipUncertain("Application ownership unconfirmed")

    async def run_forever(self) -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._shutdown_requested)
        startup = asyncio.create_task(self.start())
        stopping = asyncio.create_task(self._done.wait())
        try:
            done, _ = await asyncio.wait(
                {startup, stopping},
                return_when=asyncio.FIRST_COMPLETED,
                timeout=STARTUP_SECONDS,
            )
            if startup in done:
                await startup
                await stopping
            else:
                if not done:
                    logger.error("Application startup deadline exceeded")
                    self._faulted = True
                self._begin_shutdown()
                startup.cancel()
                startup.add_done_callback(
                    lambda task: task.exception() if not task.cancelled() else None
                )
                await asyncio.wait(
                    {startup}, timeout=min(1.0, self.shutdown_seconds / 5)
                )
        finally:
            stopping.cancel()
            await self.stop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)
