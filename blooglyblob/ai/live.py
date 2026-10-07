"""OpenAI Live transport with bounded PCM and event handoff."""

import asyncio
import base64
import logging
import math
import time

from blooglyblob.audio.stream import PCMPacer
from blooglyblob.audio.resampler import SPEECH_SAMPLE_RATE
from blooglyblob.ai.utils import field

_LOG = logging.getLogger(__name__)


class LiveSessionError(RuntimeError):
    """A deliberately sanitized transport/protocol failure."""


def _timestamp(value):
    if type(value) is not int or value < 0:
        raise LiveSessionError("Malformed Live timeline")
    return value


class OpenAILiveSession:
    INPUT_QUEUE_FRAMES = 100  # Minimum capacity: two seconds of PCM.
    OUTPUT_QUEUE_EVENTS = 50
    OUTPUT_QUEUE_FRAMES = 50  # At most one second, regardless of provider chunk size.
    FRAME_BYTES = 960  # 24 kHz, mono PCM16LE, 20 ms.
    MAX_INPUT_BYTES = SPEECH_SAMPLE_RATE * 2  # At most one second of PCM16.
    MAX_OUTPUT_BYTES = 48000
    APPEND_CHAR_LIMIT = (
        500  # UTF-8 bytes are also capped below the 500-token API limit.
    )

    def __init__(
        self,
        *,
        client,
        instructions,
        on_audio,
        on_transcript,
        on_delegation,
        readiness_timeout=10,
        voice="marin",
        model="gpt-live-1",
        on_error=None,
        max_session_seconds=600,
    ):
        if not math.isfinite(readiness_timeout) or readiness_timeout <= 0:
            raise ValueError("Readiness timeout must be finite and positive")
        if not math.isfinite(max_session_seconds) or max_session_seconds <= 0:
            raise ValueError("Session ceiling must be finite and positive")
        self.client = client
        self.instructions = instructions
        self.voice = voice
        self.model = model
        self.readiness_timeout = readiness_timeout
        self.max_session_seconds = max_session_seconds
        self.on_audio = on_audio
        self.on_transcript = on_transcript
        self.on_delegation = on_delegation
        self.on_error = on_error
        self.usage_seconds = None
        self._manager = None
        self._connection = None
        self._started = False
        self._closed = False
        self._ready = asyncio.Event()
        self._failure = None
        self._close_failure = None
        self.close_confirmed = False
        self.session_started = False
        self.finalization_confirmed = False
        self.close_reason = None
        self._finalized = asyncio.Event()
        self._reader = None
        self._close_task = None
        self._setup_task = None
        self._workers = []
        # Capture can resume after the greeting while Live is still starting.
        # Preserve that speech for the full permitted readiness window, rather
        # than overflowing before the startup deadline. The same finite queue
        # remains bounded during conversation (ten seconds with defaults).
        input_frames = math.ceil(
            readiness_timeout * SPEECH_SAMPLE_RATE * 2 / self.FRAME_BYTES
        )
        self._input = asyncio.Queue(maxsize=max(self.INPUT_QUEUE_FRAMES, input_frames))
        self._output = asyncio.Queue(maxsize=self.OUTPUT_QUEUE_EVENTS)
        self._audio = asyncio.Queue(maxsize=self.OUTPUT_QUEUE_FRAMES)
        self._pending_pcm = b""
        self._output_epoch = 0
        self._connected_at = None
        self._disconnected_at = None
        self._send_lock = asyncio.Lock()

    @property
    def connected_seconds(self):
        if self._connected_at is None:
            return 0.0
        return (self._disconnected_at or time.monotonic()) - self._connected_at

    async def start(self, greeting=""):
        if self._started or self._closed:
            raise LiveSessionError("Live session cannot be started again")
        self._started = True
        self._setup_task = asyncio.create_task(self._start(greeting))
        try:
            done, _ = await asyncio.wait(
                {self._setup_task}, timeout=self.readiness_timeout
            )
            if not done:
                raise TimeoutError
            self._setup_task.result()
        except asyncio.CancelledError:
            self._begin_close()
            raise
        except asyncio.TimeoutError:
            self._begin_close()
            raise TimeoutError("Live session readiness timed out") from None
        except Exception:  # noqa: BLE001 - sanitize SDK/device boundary failures.
            self._begin_close()
            raise self._failure or LiveSessionError(
                "Live session startup failed"
            ) from None

    async def _start(self, greeting):
        # This manager is the sole owner of transport closure. SDK reconnect and
        # queued audio replay are explicitly disabled for conversation ownership.
        self._manager = self.client.live.connect(
            max_retries=0, websocket_connection_options={"close_timeout": 0.5}
        )
        self._connection = await self._manager.__aenter__()
        self._connected_at = time.monotonic()
        if self._closed:
            raise LiveSessionError("Live startup was canceled")
        self._reader = asyncio.create_task(self._read())
        self._workers = [
            self._reader,
            asyncio.create_task(self._deliver()),
            asyncio.create_task(self._deliver_audio()),
            asyncio.create_task(self._ceiling()),
        ]
        instructions = self.instructions
        if greeting:
            instructions += "\nBegin with this brief greeting: " + greeting
        await self._connection.session.start(
            session={
                "model": self.model,
                "instructions": instructions,
                "delegation": {"type": "client"},
                "audio": {
                    "format": {"type": "audio/pcm", "rate": SPEECH_SAMPLE_RATE},
                    "output": {"voice": self.voice},
                },
                "store": False,
            }
        )
        await self._ready.wait()
        if self._failure or self._closed:
            raise self._failure or LiveSessionError(
                "Live session closed before readiness"
            )
        self._workers.append(asyncio.create_task(self._send_audio()))

    def _require_ready(self):
        if self._closed or not self._ready.is_set() or self._connection is None:
            raise LiveSessionError("Live session is not ready")

    async def input_audio(self, pcm):
        # Capture opening speech before readiness in this session's bounded queue.
        # Startup and normal input share sample-rate pacing; stop purges the queue.
        if self._closed or not self._started:
            return
        try:
            if (
                not isinstance(pcm, bytes)
                or len(pcm) % 2
                or len(pcm) > self.MAX_INPUT_BYTES
            ):
                raise ValueError("Invalid PCM input packet")
            self._pending_pcm += pcm
            while len(self._pending_pcm) >= self.FRAME_BYTES:
                frame, self._pending_pcm = (
                    self._pending_pcm[: self.FRAME_BYTES],
                    self._pending_pcm[self.FRAME_BYTES :],
                )
                self._input.put_nowait(frame)
        except asyncio.QueueFull:
            error = LiveSessionError("Live input queue overflow")
            self._fail(error)
            await self.close()
            raise error from None
        except ValueError:
            self._fail(LiveSessionError("Invalid PCM input packet"))
            await self.close()
            raise ValueError("Invalid PCM input packet") from None

    async def _send_audio(self):
        pacer = PCMPacer()
        try:
            while not self._closed:
                frame = await self._input.get()
                await pacer.wait(0.02)
                if self._closed:
                    return
                async with self._send_lock:
                    if self._closed:
                        return
                    await self._connection.session.input_audio.append(
                        audio=base64.b64encode(frame).decode("ascii")
                    )
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - sanitize SDK/device boundary failures.
            self._fail(LiveSessionError("Live input transport failed"))

    async def _read(self):
        try:
            async for event in self._connection:
                if self._closed and field(event, "type") not in {
                    "session.started",
                    "session.usage.updated",
                    "session.closed",
                }:
                    continue
                self._receive(event)
            if not self._closed:
                self._fail(LiveSessionError("Live transport ended unexpectedly"))
        except asyncio.CancelledError:
            raise
        except LiveSessionError as exc:
            self._fail(exc)
        except asyncio.QueueFull:
            self._fail(LiveSessionError("Live output queue overflow"))
        except Exception:  # noqa: BLE001 - sanitize SDK/device boundary failures.
            self._fail(LiveSessionError("Live transport or event failed"))

    def _receive(self, event):
        kind = field(event, "type")
        if kind == "session.started":
            self.session_started = True
            self._ready.set()
        elif kind == "session.output_audio.delta":
            delta = field(event, "delta")
            if (
                not isinstance(delta, str)
                or len(delta) > self.MAX_OUTPUT_BYTES * 4 // 3
            ):
                raise LiveSessionError("Malformed Live audio")
            pcm = base64.b64decode(delta, validate=True)
            if len(pcm) % 2:
                raise LiveSessionError("Malformed Live audio")
            for offset in range(0, len(pcm), self.FRAME_BYTES):
                self._audio.put_nowait(pcm[offset : offset + self.FRAME_BYTES])
        elif kind in {
            "session.input_transcript.delta",
            "session.output_transcript.delta",
        }:
            delta = field(event, "delta")
            start = _timestamp(field(event, "start_ms"))
            end = _timestamp(field(event, "end_ms"))
            if not isinstance(delta, str) or len(delta) > 16000 or end < start:
                raise LiveSessionError("Malformed Live transcript")
            role = "user" if kind == "session.input_transcript.delta" else "assistant"
            self._output.put_nowait(("transcript", (role, delta, start, end)))
        elif kind == "session.delegation.created":
            delegation = field(event, "delegation")
            identifier = field(delegation, "id")
            if (
                not isinstance(identifier, str)
                or not identifier
                or len(identifier) > 256
            ):
                raise LiveSessionError("Malformed Live delegation")
            if field(delegation, "target") != "client":
                raise LiveSessionError("Unexpected Live delegation target")
            offset = _timestamp(field(event, "offset_ms"))
            self._output.put_nowait(("delegation", (identifier, offset)))
        elif kind in {"session.usage.updated", "session.closed"}:
            seconds = field(field(event, "usage"), "seconds")
            if (
                isinstance(seconds, bool)
                or not isinstance(seconds, (int, float))
                or not math.isfinite(seconds)
                or seconds < 0
            ):
                raise LiveSessionError("Malformed Live usage")
            self.usage_seconds = seconds  # The SDK reports cumulative totals.
            if kind == "session.closed":
                self.finalization_confirmed = True
                self.close_reason = field(event, "reason")
                self._finalized.set()
                self._fail(LiveSessionError("Live session ended"))
        elif kind == "error":
            self._fail(LiveSessionError("Live provider reported an error"))
        # Future event types are deliberately ignored. Audio/transcript fragments
        # do not imply a turn boundary and never synthesize an audio_done event.

    async def _deliver(self):
        callbacks = {"transcript": self.on_transcript, "delegation": self.on_delegation}
        try:
            while not self._closed:
                kind, args = await self._output.get()
                if self._closed:
                    return
                await callbacks[kind](*args)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - sanitize SDK/device boundary failures.
            self._fail(LiveSessionError("Live output callback failed"))

    async def _deliver_audio(self):
        pacer = PCMPacer()
        try:
            while not self._closed:
                pcm = await self._audio.get()
                epoch = self._output_epoch
                await pacer.wait(len(pcm) / 48000)
                if self._closed:
                    return
                if epoch == self._output_epoch:
                    await self.on_audio(pcm)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - sanitize SDK/device boundary failures.
            self._fail(LiveSessionError("Live output callback failed"))

    def discard_output(self):
        """Discard queued and in-flight playback without changing microphone flow."""
        self._output_epoch += 1
        while not self._audio.empty():
            self._audio.get_nowait()

    async def _ceiling(self):
        await asyncio.sleep(self.max_session_seconds)
        self._fail(LiveSessionError("Live session duration limit reached"))

    async def append_result(self, delegation_id, content):
        if (
            not isinstance(delegation_id, str)
            or not delegation_id
            or len(delegation_id) > 256
        ):
            raise ValueError("Invalid delegation identifier")
        await self._append("commentary", content, delegation_id)

    async def append_instruction(self, content):
        await self._append("instructions", content, None)

    async def _append(self, resource, content, delegation_id):
        self._require_ready()
        if (
            not isinstance(content, str)
            or not content.strip()
            or len(content.encode("utf-8")) > self.APPEND_CHAR_LIMIT
        ):
            raise ValueError("Live appended content must be a short nonempty string")
        try:
            async with self._send_lock:
                self._require_ready()
                await getattr(self._connection.session, resource).append(
                    content=content, delegation_id=delegation_id
                )
        except asyncio.CancelledError:
            self._fail(LiveSessionError("Live context append cancelled"))
            await self.close()
            raise
        except Exception:  # noqa: BLE001 - sanitize SDK/device boundary failures.
            self._fail(LiveSessionError("Live context append failed"))
            await self.close()
            raise LiveSessionError("Live context append failed") from None

    async def event(self, event):
        if event.get("type") == "stop":
            await self.stop()

    async def stop(self):
        await self.close()

    def _begin_close(self):
        self._closed = True
        self._ready.set()
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._shutdown())

    def _fail(self, error):
        if not self._closed:
            # Callers supply local, sanitized failures, never provider payloads.
            _LOG.warning(
                "Live session failed: %s (queued audio=%s, events=%s)",
                error,
                self._audio.qsize(),
                self._output.qsize(),
            )
            self._failure = error
            self._begin_close()

    async def close(self):
        self._begin_close()
        # An error callback may close its runtime, which closes this session.
        caller = asyncio.current_task()
        if caller is self._close_task or caller in self._workers:
            # Shutdown cancels and joins workers. A cancelled append inside a
            # callback must not wait for the shutdown that is joining it.
            return
        await asyncio.shield(self._close_task)
        if self._close_failure:
            raise self._close_failure

    async def _shutdown(self):
        tasks = [task for task in self._workers if task is not self._reader]
        if self._setup_task:
            tasks.append(self._setup_task)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._pending_pcm = b""
        for queue in (self._input, self._output, self._audio):
            while not queue.empty():
                queue.get_nowait()
        try:
            if self.session_started and not self.finalization_confirmed:
                try:

                    async def finalize():
                        await self._connection.session.close()
                        if self._reader and not self._reader.done():
                            await self._finalized.wait()

                    await asyncio.wait_for(finalize(), 2.0)
                except Exception:  # noqa: BLE001 - final usage remains explicitly unknown
                    _LOG.warning("Live finalization unconfirmed; releasing transport")
            if self._reader:
                self._reader.cancel()
                await asyncio.gather(self._reader, return_exceptions=True)
            if self._manager is not None:
                await self._manager.__aexit__(None, None, None)
            self.close_confirmed = True
        except Exception:  # noqa: BLE001 - sanitize SDK/device boundary failures.
            self._close_failure = LiveSessionError("Live transport close failed")
            self._failure = self._failure or self._close_failure
        finally:
            if self.close_confirmed:
                self._disconnected_at = time.monotonic()
        if self._failure and self.on_error:
            try:
                await self.on_error(self._failure)
            except Exception:  # noqa: BLE001 - sanitize SDK/device boundary failures.
                # No provider/device exception content enters logs or escapes a
                # background task. The paid transport is already closed.
                _LOG.warning("Live error callback failed")
