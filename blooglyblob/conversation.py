"""One conversation owner with direct media and hardware collaborators."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypedDict

from contextvars import ContextVar

from blooglyblob.media import MediaCoordinator, MediaError
from blooglyblob.ai.tool_bridge import OpenAIToolBridge, StaleResponse
from blooglyblob.audio.voice_effects import RingModulator

if TYPE_CHECKING:
    from openai import AsyncOpenAI
    from blooglyblob.ai.alert_ack import OpenAIAlertAcknowledgement
    from blooglyblob.ai.live import OpenAILiveSession
    from blooglyblob.ai.responses import OpenAIResponses
    from blooglyblob.ai.speech import OpenAISpeech
    from blooglyblob.audio.controller import AudioController
    from blooglyblob.hardware.controller import HardwareController
    from blooglyblob.tools.executor import ToolExecutor
    from blooglyblob.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)
_tool_owner: ContextVar[tuple[ConversationSession, str, str] | None] = ContextVar(
    "conversation_tool_owner", default=None
)
GREETING_SPEED = 1.25
DANCE_RETURN_GREETING = "That was fun! What's next?"


def _terminal_speech_candidate(context: list[dict[str, str]]) -> bool:
    """A conservative playback hint, never authorization to execute an action."""
    text = next(
        (item["content"] for item in reversed(context) if item["role"] == "user"), ""
    )
    text = " ".join(text.lower().replace("’", "'").split()).strip(" .!?")
    return (
        re.fullmatch(
            r"(?:please )?(?:(?:can|could|would|will) you (?:please )?)?"
            r"(?:go(?: back)? to sleep|go to bed|sleep|start dancing|dance|"
            r"let(?:'s| us) (?:have a )?dance(?: party)?)"
            r"(?: now| please| for me| blooglyblob)*",
            text,
        )
        is not None
    )


class TranscriptFragment(TypedDict):
    role: str
    text: str
    start_ms: int
    end_ms: int


class ActionRecord(TypedDict):
    name: str
    params: dict[str, object]
    outcome: str


class ConversationSession:
    """Serialize media ownership while fencing concurrent backend work."""

    SPEECH_GATE_SECONDS = 6.0

    def __init__(
        self,
        *,
        audio: AudioController,
        hardware: HardwareController,
        on_fault: Callable[[], None] = lambda: None,
        api: AsyncOpenAI,
        live_factory: Callable[..., OpenAILiveSession],
        instructions: str,
        voice: str = "marin",
        model: str = "gpt-live-1",
        greeting: str = "",
        inactivity_seconds: float = 20.0,
        max_session_seconds: float = 600.0,
        on_delegation: Callable[[ConversationSession, str, str, int], Awaitable[None]]
        | None = None,
        speech: OpenAISpeech | None = None,
        responses: OpenAIResponses | None = None,
        registry: ToolRegistry | None = None,
        executor: ToolExecutor | None = None,
        backend_instructions: str = "",
        responses_model: str = "gpt-5.6-terra",
        acknowledge: OpenAIAlertAcknowledgement | None = None,
        media_timeout: float = 3.0,
        alert_voice_seconds: float = 120.0,
        alert_total_seconds: float = 300.0,
        dance_timeout: float = 300.0,
        cloud_close_timeout: float = 3.0,
        voice_effect_factory: Callable[[], RingModulator] = RingModulator,
    ) -> None:
        if any(
            not math.isfinite(value) or value <= 0
            for value in (
                inactivity_seconds,
                max_session_seconds,
                alert_voice_seconds,
                alert_total_seconds,
                dance_timeout,
                cloud_close_timeout,
            )
        ):
            raise ValueError("Session time limits must be positive and finite")
        self.audio, self.hardware, self.api = audio, hardware, api
        self._on_fault = on_fault
        self._closing = False
        self.live_factory, self.instructions = live_factory, instructions
        self.voice, self.model, self.greeting = voice, model, greeting
        self.inactivity_seconds, self.max_session_seconds = (
            inactivity_seconds,
            max_session_seconds,
        )
        self.alert_voice_seconds, self.alert_total_seconds = (
            alert_voice_seconds,
            alert_total_seconds,
        )
        self.dance_timeout = dance_timeout
        self.cloud_close_timeout = cloud_close_timeout
        self.on_delegation, self.speech, self.acknowledge = (
            on_delegation,
            speech,
            acknowledge,
        )
        self.executor, self.responses = executor, responses
        self.voice_effect_factory = voice_effect_factory
        self.active, self.activity = False, "idle"
        self.generation: str | None = None
        self.live: OpenAILiveSession | None = None
        self._live_generation: str | None = None
        self._runner: asyncio.Task[None] | None = None
        self._accept_live_input = False
        self._retiring: set[asyncio.Task[None]] = set()
        self._jobs: set[asyncio.Task[None]] = set()
        self._job: asyncio.Task[None] | None = None
        self._job_id: str | None = None
        self._speech_gate: float | None = None
        self._terminal_job_id: str | None = None
        self._terminal_input_cutoff = 0
        self._pending_terminal: (
            tuple[str, str, str] | tuple[str, str, str, ActionRecord] | None
        ) = None
        self._uncertain_terminals: set[str] = set()
        self._cloud_closers: set[asyncio.Task[None]] = set()
        self._faulted = False
        self._last_activity = time.monotonic()
        self.backend_busy = False
        self.transcripts: deque[TranscriptFragment] = deque(maxlen=200)
        self.actions: deque[ActionRecord] = deque(maxlen=30)
        self.last_usage: dict[str, object] | None = None
        self._dance_id: str | None = None
        self._dance_done: asyncio.Event | None = None
        self._alert_message = ""
        self.media = MediaCoordinator(audio, hardware, timeout=media_timeout)
        if registry is not None and responses is None:
            from blooglyblob.ai.responses import OpenAIResponses

            bridge = OpenAIToolBridge(registry, self._execute_tool, search=self._search)
            self.responses = OpenAIResponses(
                api,
                model=responses_model,
                instructions=backend_instructions,
                bridge=bridge,
                terminal_pending=lambda: self._pending_terminal is not None,
            )

    def _current(self, generation: str | None) -> bool:
        return (
            self.active
            and self.generation == generation
            and not self._closing
            and not self._faulted
        )

    def _ownership_failed(self) -> None:
        self._faulted = True
        self.active = False
        self.audio.mute()
        self.hardware.mute_media()
        self._on_fault()

    def _clear_speech_gate(self) -> None:
        if self._speech_gate is not None:
            self._speech_gate = None
            if self.live:
                self.live.discard_output()

    def _cancel_job(self) -> None:
        self.hardware.pending_light(self._job_id, False)
        self._clear_speech_gate()
        self._terminal_job_id = None
        self._pending_terminal = None
        self._job_id = None
        self.backend_busy = False
        if self._job and not self._job.done():
            self._job.cancel()
        self._job = None

    def request(self, active: bool, greeting: str = "") -> None:
        self._request_activity("conversation" if active else "idle", greeting=greeting)

    def _request_activity(
        self,
        activity: str,
        *,
        greeting: str = "",
        message: str = "",
        terminal_record: ActionRecord | None = None,
    ) -> None:
        if self._closing and activity != "idle":
            return
        self._cancel_job()
        self.hardware.pending_light(self.generation, False)
        self.hardware.light(
            {
                "conversation": "waking",
                "idle": "sleeping",
                "sleep": "goodbye",
                "dance": "waiting",
                "alert": "alert",
            }[activity]
        )
        self.active, self.activity = activity != "idle", activity
        self.generation = uuid.uuid4().hex
        generation = self.generation
        if activity == "conversation":
            self.hardware.pending_light(generation, True)
        logger.info("Activity requested: %s generation=%s", activity, generation)
        if self._runner and not self._runner.done():
            if self._runner is not asyncio.current_task():
                self._runner.cancel()
            self._retiring.add(self._runner)
            self._runner.add_done_callback(self._retiring.discard)
        retiring = tuple(self._retiring)
        self._runner = asyncio.create_task(
            self._transition(
                generation, activity, greeting, message, retiring, terminal_record
            )
        )

    def alert(self, message: str) -> bool:
        if self.activity == "alert" or self._closing or self._faulted:
            return False
        self._alert_message = message
        self._request_activity("alert", message=message)
        return True

    def terminal(self, name: str, params: dict[str, object]) -> str:
        owner = _tool_owner.get()
        if (
            owner is None
            or owner[0] is not self
            or not self._owns_job(owner[1], owner[2])
        ):
            raise StaleResponse("Terminal action no longer owns the conversation")
        self._pending_terminal = (owner[1], owner[2], name)
        logger.info("Terminal selected: tool=%s generation=%s", name, owner[1])
        return "Terminal request accepted; speech and action are not yet complete."

    async def _transition(
        self,
        generation: str,
        activity: str,
        greeting: str,
        message: str,
        retiring: tuple[asyncio.Task[None], ...],
        terminal_record: ActionRecord | None = None,
    ) -> None:
        owns_media = False
        try:
            # A rapid toggle must never cancel cleanup of the previous owner.
            await asyncio.gather(
                *(asyncio.shield(task) for task in retiring), return_exceptions=True
            )
            if self.generation != generation:
                return
            owns_media = True
            if activity == "idle" or self._faulted:
                return
            await self.media.release()
            self.transcripts.clear()
            if activity == "conversation":
                opening = greeting or self.greeting
                greeted = bool(opening and self.speech)
                if self._current(generation):
                    await self._run_live(generation, opening, greeted=greeted)
            elif activity in {"sleep", "dance"}:
                await self._run_terminal(generation, activity, terminal_record)
            elif activity == "alert":
                await asyncio.wait_for(
                    self._run_alert(generation, message), self.alert_total_seconds
                )
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - fail closed at lifecycle boundaries
            logger.warning("Activity ended (%s)", type(error).__name__)
        finally:
            if terminal_record and terminal_record["outcome"].startswith(
                "pending speech"
            ):
                terminal_record["outcome"] = (
                    "not dispatched; activity ended before physical delivery"
                )
            if self.generation == generation:
                self._cancel_job()
                self.active = False
                self.activity = "idle"
            if owns_media:
                try:
                    await self.media.release()
                except Exception:  # noqa: BLE001 - never open another writer after unconfirmed release
                    self._ownership_failed()
                    logger.error("Media release unconfirmed; application stopping")
                try:
                    # Retiring owners still release their audio, but only the
                    # current activity may put the robot to sleep. A handoff to
                    # farewell/dance speech must keep its eyes and posture awake.
                    if self.generation == generation:
                        self.hardware.present("idle")
                        self.hardware.light("sleeping")
                except Exception:  # noqa: BLE001 - disconnect cleanup is best effort
                    logger.warning("Idle state could not be delivered")

    async def _run_live(
        self,
        generation: str,
        greeting: str = "",
        *,
        alert: bool = False,
        duration: float | None = None,
        greeted: bool = False,
    ) -> None:
        self._last_activity = time.monotonic()
        audio_generation = uuid.uuid4().hex
        effect = self.voice_effect_factory()
        live: OpenAILiveSession | None = None
        opening_done = not greeted
        self._accept_live_input = not greeted

        async def output(pcm: bytes) -> None:
            if self._current(generation) and opening_done and self._speech_gate is None:
                processed = effect.process(pcm)
                if processed:
                    await self.media.audio(audio_generation, processed)

        async def opening() -> None:
            nonlocal opening_done
            # The cloud connection opens concurrently, but cached Speech has no
            # acoustic echo reference in Live. Keep its microphone input isolated.
            await asyncio.sleep(0.15)
            await self._finite(generation, greeting, speed=GREETING_SPEED)
            if self._current(generation):
                await self.media.begin(audio_generation)
                assert live is not None
                live.discard_output()
                opening_done = True
                self._accept_live_input = True
                self.hardware.present("listening")
                self.hardware.light("listening")

        async def transcript(role: str, delta: str, start_ms: int, end_ms: int) -> None:
            if self._current(generation) and delta.strip():
                self._last_activity = time.monotonic()
                if (
                    role == "user"
                    and self._terminal_job_id == self._job_id
                    and self._terminal_job_id is not None
                    and start_ms >= self._terminal_input_cutoff
                    and any(char.isalnum() for char in delta)
                ):
                    # New speech may correct the action. Never deliver its old result.
                    self._cancel_job()
                self.transcripts.append(
                    {
                        "role": role,
                        "text": delta,
                        "start_ms": start_ms,
                        "end_ms": end_ms,
                    }
                )

        async def delegation(delegation_id: str, offset_ms: int) -> None:
            nonlocal audio_generation
            if self._current(generation):
                if self.on_delegation:
                    await self.on_delegation(self, generation, delegation_id, offset_ms)
                else:
                    self._delegate(
                        generation, delegation_id, alert=alert, offset_ms=offset_ms
                    )
                    if self._speech_gate is not None:
                        assert live is not None
                        live.discard_output()
                        if opening_done:
                            # Fence the old speaker queue before a pending preamble arrives.
                            await self.media.release()
                            if self._current(generation):
                                audio_generation = uuid.uuid4().hex
                                await self.media.begin(audio_generation)

        failed = asyncio.Event()

        async def failure(error: Exception) -> None:
            if self._current(generation):
                logger.warning("Live connection failed (%s)", type(error).__name__)
                failed.set()

        instructions = self.instructions
        if greeted:
            instructions += (
                "\nYour greeting has already played through the speaker. "
                "Do not repeat it or introduce yourself again. Listen and respond to the user."
            )
        if alert:
            instructions += (
                "\nYou are waiting for acknowledgement of an alert. The announcement has "
                "already played. Do not repeat it. Delegate acknowledgement or dismissal "
                "to the backend. Do not perform other tasks, search, or offer actions."
            )
        try:
            live = self.live_factory(
                client=self.api,
                instructions=instructions,
                voice=self.voice,
                model=self.model,
                on_audio=output,
                on_transcript=transcript,
                on_delegation=delegation,
                on_error=failure,
                max_session_seconds=duration or self.max_session_seconds,
            )
            self.live, self._live_generation = live, generation
            self.hardware.present("alert" if alert else "listening")
            if alert:
                self.hardware.light("listening")
            if greeted:
                startup = asyncio.create_task(live.start())
                cached_greeting = asyncio.create_task(opening())
                try:
                    await asyncio.gather(startup, cached_greeting)
                finally:
                    startup.cancel()
                    cached_greeting.cancel()
                    await asyncio.gather(
                        startup, cached_greeting, return_exceptions=True
                    )
            else:
                await self.media.begin(audio_generation)
                await live.start(greeting=greeting)
            self.hardware.pending_light(generation, False)
            if self._current(generation):
                self.hardware.light("listening")
            logger.info("Live ready for conversation: generation=%s", generation)
            started = time.monotonic()
            while self._current(generation) and not failed.is_set():
                await asyncio.sleep(min(0.25, self.inactivity_seconds / 2))
                now = time.monotonic()
                if self._speech_gate is not None and now >= self._speech_gate:
                    self._clear_speech_gate()
                    logger.info(
                        "Pending terminal speech gate expired; conversation audio resumed"
                    )
                if now - started >= (duration or self.max_session_seconds):
                    break
                if (
                    not alert
                    and not self.backend_busy
                    and now - self._last_activity >= self.inactivity_seconds
                ):
                    break
        finally:
            self.hardware.pending_light(generation, False)
            self._accept_live_input = False
            if self.generation == generation:
                # Cancel the background search before releasing all media.
                self._cancel_job()
            try:
                if live:
                    try:
                        await self._close_live(live)
                        if getattr(live, "session_started", False) and not getattr(
                            live, "finalization_confirmed", False
                        ):
                            logger.warning(
                                "Live final usage unavailable after transport closure"
                            )
                        if getattr(live, "close_confirmed", True) is False:
                            raise RuntimeError("Live transport close unconfirmed")
                    except Exception:  # noqa: BLE001 - prohibit replacement when close is unconfirmed
                        self._ownership_failed()
                        logger.error("Cloud cleanup unconfirmed; application stopping")
                    finally:
                        self.last_usage = {
                            "connected_seconds": getattr(
                                live, "connected_seconds", None
                            ),
                            "reported_seconds": getattr(live, "usage_seconds", None),
                            "close_confirmed": getattr(live, "close_confirmed", None),
                            "finalization_confirmed": getattr(
                                live, "finalization_confirmed", None
                            ),
                            "close_reason": getattr(live, "close_reason", None),
                        }
                        logger.info("Live usage: %s", self.last_usage)
                        if self.live is live:
                            self.live, self._live_generation = None, None
                            self._accept_live_input = False
            finally:
                # Flush even when cloud cleanup failed or was cancelled.
                try:
                    await self.media.release()
                except Exception:
                    self._ownership_failed()
                    raise

    async def _close_live(self, live: OpenAILiveSession) -> None:
        # Keep one observed close attempt alive without letting a stalled provider
        # prevent the device flush. A timeout permanently blocks new owners.
        task = asyncio.create_task(live.close())
        self._cloud_closers.add(task)

        def finished(done: asyncio.Task[None]) -> None:
            self._cloud_closers.discard(done)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(finished)
        try:
            done, _ = await asyncio.wait({task}, timeout=self.cloud_close_timeout)
            if not done:
                raise TimeoutError("Cloud cleanup did not finish")
            task.result()
        except asyncio.CancelledError:
            self._ownership_failed()
            raise

    def _context(self) -> list[dict[str, str]]:
        context = []
        size = 0
        # Bound payload independently of the number of transcript fragments.
        for fragment in reversed(self.transcripts):
            text = fragment["text"]
            if fragment["role"] not in {"user", "assistant"}:
                continue
            size += len(text.encode("utf-8"))
            if size > 16000:
                break
            context.append({"role": fragment["role"], "content": text})
        context.reverse()
        merged: list[dict[str, str]] = []
        for item in context:
            if merged and merged[-1]["role"] == item["role"]:
                merged[-1]["content"] += item["content"]
            else:
                merged.append(item.copy())
        if self.actions:
            merged.insert(
                0,
                {
                    "role": "developer",
                    "content": "Recorded action outcomes; do not repeat completed or uncertain actions: "
                    + json.dumps(list(self.actions)),
                },
            )
        return merged

    def _owns_job(self, generation: str, job_id: str) -> bool:
        return self._current(generation) and self._job_id == job_id

    def _delegate(
        self,
        generation: str,
        delegation_id: str,
        *,
        alert: bool = False,
        offset_ms: int = 0,
    ) -> None:
        self._cancel_job()
        if len(self._jobs) >= 4:
            logger.warning("Unfinished device work limit reached; ending activity")
            self.request(False)
            return
        job_id = uuid.uuid4().hex
        self._job_id = job_id
        self.backend_busy = True
        self.hardware.pending_light(job_id, True)
        context = self._context()
        if not alert and _terminal_speech_candidate(context):
            self._speech_gate = time.monotonic() + self.SPEECH_GATE_SECONDS
            self._terminal_job_id = job_id
            self._terminal_input_cutoff = offset_ms
        self._job = asyncio.create_task(
            self._work(generation, job_id, delegation_id, context, alert)
        )
        self._jobs.add(self._job)
        self._job.add_done_callback(self._jobs.discard)

    async def _work(
        self,
        generation: str,
        job_id: str,
        delegation_id: str,
        context: list[dict[str, str]],
        alert: bool,
    ) -> None:
        token = _tool_owner.set((self, generation, job_id))

        def owns() -> bool:
            return self._owns_job(generation, job_id)

        try:
            if alert:
                if (
                    self.acknowledge
                    and await self.acknowledge.acknowledge(context, self._alert_message)
                    and owns()
                ):
                    self.request(False)
                return
            if not self.responses:
                raise RuntimeError("Task backend is unavailable")
            await self.media.wait_for_local_sound()
            if not owns():
                raise StaleResponse("Backend job was replaced during audio handoff")
            result = await self.responses.run(context, owns)
            if owns() and self._pending_terminal:
                name = self._pending_terminal[2]
                assert (
                    len(self._pending_terminal) == 4
                )  # Tool completion attaches its action record.
                record = self._pending_terminal[3]
                self._request_activity(
                    "sleep" if name == "goToSleep" else "dance", terminal_record=record
                )
            elif owns() and self.live:
                self._clear_speech_gate()
                await self.live.append_result(delegation_id, result)
        except asyncio.CancelledError:
            raise
        except StaleResponse:
            pass
        except Exception as error:  # noqa: BLE001 - report uncertainty without exposing credentials
            logger.warning("Delegated work ended (%s)", type(error).__name__)
            if owns() and self.live and not alert:
                self._clear_speech_gate()
                try:
                    await self.live.append_result(
                        delegation_id,
                        "I couldn't verify that request. An action may have started; don't retry automatically.",
                    )
                except Exception:  # noqa: BLE001 - a failed handoff ends the session
                    self.request(False)
        finally:
            _tool_owner.reset(token)
            if not alert and self.responses and hasattr(self.responses, "usage"):
                logger.info("Cumulative Responses usage: %s", self.responses.usage)
            self.hardware.pending_light(job_id, False)
            if self._job_id == job_id:
                self._clear_speech_gate()
                self._terminal_job_id = None
                self.backend_busy = False
                self._last_activity = time.monotonic()
                self._job_id = None

    async def _search(self, query: str) -> str:
        owner = _tool_owner.get()
        if owner is None or owner[0] is not self:
            raise StaleResponse("No owned search job")

        def owns() -> bool:
            return self._owns_job(owner[1], owner[2])

        try:
            async with self.media.search_sound(owns):
                assert self.responses is not None
                return await self.responses.search(query)
        except MediaError:
            if self.media.ownership_uncertain:
                self._ownership_failed()
            self.request(False)
            raise

    async def _execute_tool(
        self, call_id: str, name: str, params: dict[str, object]
    ) -> str:
        owner = _tool_owner.get()
        if owner is None or owner[0] is not self:
            raise StaleResponse("No owned backend job")

        def owns() -> bool:
            return self._owns_job(owner[1], owner[2])

        if name in self._uncertain_terminals:
            return json.dumps(
                {
                    "error": "execution_unknown",
                    "message": "The previous terminal action was not confirmed; do not retry.",
                }
            )
        record: ActionRecord = {
            "name": name,
            "params": params,
            "outcome": "unknown; may have started, never retry automatically",
        }
        self.actions.append(record)
        assert self.executor is not None
        result = await self.executor.execute(call_id, name, params, owns)
        if owns():
            if name in {"goToSleep", "danceMode"} and self._pending_terminal:
                record["outcome"] = "pending speech; physical action not dispatched"
                assert len(self._pending_terminal) == 3
                self._pending_terminal = (*self._pending_terminal, record)
            else:
                record["outcome"] = (
                    result[:2000] if isinstance(result, str) else "unknown result"
                )
        return result

    async def _finite(self, generation: str, text: str, *, speed: float = 1.0) -> None:
        if not self.speech or not self._current(generation):
            raise RuntimeError("Finite speech is unavailable")
        effect = self.voice_effect_factory()
        audio_generation = uuid.uuid4().hex
        self.hardware.pending_light(audio_generation, True)
        try:
            self.hardware.present("speaking")
            await self.media.begin(audio_generation)

            async def output(pcm: bytes) -> None:
                if not self._current(generation):
                    raise StaleResponse("Speech no longer owns playback")
                processed = effect.process(pcm)
                if processed:
                    await self.media.audio(audio_generation, processed)

            options = {"speed": speed} if speed != 1.0 else {}
            logger.info(
                "Finite speech started: activity=%s generation=%s audio_generation=%s",
                self.activity,
                generation,
                audio_generation,
            )
            seconds = await self.speech.speak(text, output, **options)
            if not self._current(generation):
                raise StaleResponse("Speech no longer owns playback")
            effect.finish()
            await self.media.drain(audio_generation)
            logger.info(
                "Finite speech drained: audio_seconds=%s activity=%s generation=%s",
                seconds,
                self.activity,
                generation,
            )
            if not self._current(generation):
                raise StaleResponse("Playback was superseded")
        finally:
            self.hardware.pending_light(audio_generation, False)

    async def _run_terminal(
        self, generation: str, activity: str, record: ActionRecord | None = None
    ) -> None:
        await self._finite(
            generation,
            "Goodnight! Catch you on the next orbit."
            if activity == "sleep"
            else "Let's dance! Time to party!",
        )
        # Speaker drain and local-media ownership are separate ownership barriers.
        await self.media.release()
        if not self._current(generation):
            raise StaleResponse("Terminal activity no longer owns presentation")
        name = "goToSleep" if activity == "sleep" else "danceMode"
        if record is None:
            record = {"name": name, "params": {}, "outcome": "not dispatched"}
            self.actions.append(record)
        if activity == "sleep":
            await self._dispatch_terminal(generation, name, {}, record)
            return
        activity_id = uuid.uuid4().hex
        self._dance_id, self._dance_done = activity_id, asyncio.Event()
        try:
            self.hardware.present("dancing")
            self.hardware.light("dancing")
            await self._dispatch_terminal(
                generation, name, {"activity_id": activity_id}, record
            )
            await asyncio.wait_for(self._dance_done.wait(), self.dance_timeout)
            if self._current(generation):
                self.request(True, greeting=DANCE_RETURN_GREETING)
        finally:
            self._dance_id, self._dance_done = None, None

    async def _dispatch_terminal(
        self,
        generation: str,
        name: str,
        params: dict[str, object],
        record: ActionRecord,
    ) -> None:
        if not self._current(generation) or name in self._uncertain_terminals:
            raise StaleResponse("Terminal dispatch no longer owns this activity")
        # Reserve before the local action starts, including cancellation after
        # it may have acted but before the awaited completion is observed.
        self._uncertain_terminals.add(name)
        record["outcome"] = "unknown; may have started, never retry automatically"
        logger.info("Terminal dispatch: tool=%s generation=%s", name, generation)
        result = await self.hardware.execute(name, params)
        if not self._current(generation):
            raise StaleResponse("Terminal acknowledgement no longer owns this activity")
        confirmations = {
            "goToSleep": {"Going to sleep"},
            "danceMode": {"Dance mode starting"},
        }
        if not isinstance(result, str) or result.strip() not in confirmations[name]:
            raise RuntimeError("Terminal action was not confirmed")
        self._uncertain_terminals.remove(name)
        record["outcome"] = result[:2000]
        logger.info("Terminal acknowledged: tool=%s generation=%s", name, generation)

    async def _run_alert(self, generation: str, message: str) -> None:
        deadline = time.monotonic() + self.alert_total_seconds
        self.hardware.present("alert")
        self.hardware.light("alert")
        try:
            await self.media.chime(uuid.uuid4().hex)
            await self._finite(generation, message)
            self.transcripts.clear()
            remaining = deadline - time.monotonic()
            if remaining > 0:
                await self._run_live(
                    generation,
                    alert=True,
                    duration=min(self.alert_voice_seconds, remaining),
                )
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - keep button dismissal available during provider outages
            logger.warning(
                "Alert voice unavailable (%s); button dismissal remains available",
                type(error).__name__,
            )
            try:
                await self.media.release()
            except Exception:  # noqa: BLE001 - never reopen a failed media owner
                self._ownership_failed()
        if self._current(generation):
            self.hardware.present("alert")
            self.hardware.light("alert")
            await asyncio.sleep(max(0, deadline - time.monotonic()))

    async def input_audio(self, pcm: bytes) -> None:
        if (
            self.live
            and self._accept_live_input
            and self._current(self._live_generation)
        ):
            live, generation = self.live, self._live_generation
            try:
                await live.input_audio(pcm)
            except Exception:  # noqa: BLE001 - invalid input or transport failure ends the activity
                # Startup failure may already be closing this session. Do not
                # cancel that cleanup, or stop a replacement for a stale send.
                if (
                    self.live is live
                    and self._accept_live_input
                    and self._current(generation)
                ):
                    self.request(False)

    def button(self) -> None:
        if self._closing or self._faulted:
            return
        if self.activity == "dance" and self._dance_id is not None:
            self.request(True, greeting=DANCE_RETURN_GREETING)
        else:
            self.request(not self.active)

    def dance_finished(self, activity_id: str) -> None:
        if self._dance_done and activity_id == self._dance_id:
            self._dance_done.set()

    def media_failed(self, identity: str | None, reason: str) -> None:
        if self.audio.ownership_uncertain or self.hardware.ownership_uncertain:
            self._ownership_failed()
            self.request(False)
        elif identity is not None and identity in {
            self.media.generation,
            self._dance_id,
        }:
            self.request(False)
        logger.warning("Owned media failure: %s", reason)

    async def start(self, greeting: str = "") -> None:
        self.request(True, greeting)

    async def stop(self) -> None:
        self.audio.mute()
        self.hardware.mute_media()
        self.request(False)
        assert self._runner is not None  # request() always creates the transition task.
        await asyncio.shield(self._runner)

    async def close(self) -> None:
        self._closing = True
        await self.stop()
