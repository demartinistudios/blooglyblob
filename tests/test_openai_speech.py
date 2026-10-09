import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from blooglyblob.ai.speech import OpenAISpeech, SpeechError, SpeechTimeout


class Stream:
    def __init__(self, chunks):
        self.chunks = chunks
        self.entered = asyncio.Event()
        self.closed = 0

    async def __aenter__(self):
        self.entered.set()
        return self

    async def __aexit__(self, *args):
        self.closed += 1

    async def iter_bytes(self, chunk_size):
        assert chunk_size == 960
        for chunk in self.chunks:
            if isinstance(chunk, asyncio.Event):
                await chunk.wait()
            elif isinstance(chunk, Exception):
                raise chunk
            else:
                yield chunk


def adapter(chunks, **kwargs):
    stream = Stream(chunks)
    create = Mock(return_value=stream)
    client = SimpleNamespace(
        audio=SimpleNamespace(
            speech=SimpleNamespace(
                with_streaming_response=SimpleNamespace(create=create)
            )
        )
    )
    return OpenAISpeech(client=client, **kwargs), stream, create


@pytest.mark.asyncio
async def test_odd_network_boundaries_preserve_all_samples_and_share_voice_instructions(
    monkeypatch,
):
    waits = AsyncMock()
    monkeypatch.setattr(
        "blooglyblob.ai.speech.PCMPacer", lambda: SimpleNamespace(wait=waits)
    )
    speech, stream, create = adapter([b"a", b"b" * 960, b"c" * 961])
    audio = AsyncMock()
    duration = await speech.speak("Hello!", audio)
    assert [len(call.args[0]) for call in audio.await_args_list] == [960, 960, 2]
    assert (
        b"".join(call.args[0] for call in audio.await_args_list)
        == b"a" + b"b" * 960 + b"c" * 961
    )
    assert duration == pytest.approx(1922 / 48000)
    assert [call.args[0] for call in waits.await_args_list] == [0.02, 0.02, 2 / 48000]
    assert stream.closed == 1
    options = create.call_args.kwargs
    assert options["model"] == "gpt-4o-mini-tts"
    assert options["voice"] == "ballad"
    assert options["response_format"] == "pcm"
    assert options["instructions"]


@pytest.mark.asyncio
async def test_cancelled_stream_closes_without_delivering_later_audio():
    speech, stream, _ = adapter([asyncio.Event(), bytes(960)])
    audio = AsyncMock()
    task = asyncio.create_task(speech.speak("Hi", audio))
    await stream.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert stream.closed == 1
    audio.assert_not_awaited()


@pytest.mark.asyncio
async def test_total_timeout_covers_waiting_for_audio_and_closes():
    speech, stream, _ = adapter([asyncio.Event()], timeout_seconds=0.01)
    with pytest.raises(SpeechTimeout):
        await speech.speak("Hi", AsyncMock())
    assert stream.closed == 1


@pytest.mark.asyncio
async def test_total_timeout_covers_slow_device_callback():
    speech, stream, _ = adapter([bytes(960)], timeout_seconds=0.01)

    async def blocked(_pcm):
        await asyncio.Event().wait()

    with pytest.raises(SpeechTimeout):
        await speech.speak("Hi", blocked)
    assert stream.closed == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "chunks", [[], [b"x"], [RuntimeError("private provider details")]]
)
async def test_invalid_or_failed_stream_is_never_success(chunks):
    speech, stream, _ = adapter(chunks)
    with pytest.raises(SpeechError) as error:
        await speech.speak("Hi", AsyncMock())
    assert "private provider details" not in str(error.value)
    assert stream.closed == 1


@pytest.mark.asyncio
async def test_duration_overflow_closes_before_delivering_excess():
    speech, stream, _ = adapter([bytes(960), bytes(2)], max_audio_seconds=0.02)
    audio = AsyncMock()
    with pytest.raises(SpeechError, match="duration"):
        await speech.speak("Hi", audio)
    audio.assert_awaited_once_with(bytes(960))
    assert stream.closed == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", "   ", "x" * 1001, None])
async def test_input_rejected_before_provider_call(text):
    speech, _stream, create = adapter([])
    with pytest.raises(ValueError):
        await speech.speak(text, AsyncMock())
    create.assert_not_called()


@pytest.mark.parametrize(
    "options",
    [
        {"timeout_seconds": 0},
        {"timeout_seconds": float("nan")},
        {"max_audio_seconds": float("inf")},
        {"max_audio_seconds": True},
        {"max_input_chars": 4097},
        {"max_input_chars": 1.5},
    ],
)
def test_invalid_limits_rejected(options):
    with pytest.raises(ValueError):
        adapter([], **options)


@pytest.mark.asyncio
async def test_audio_callback_failure_closes_provider_without_claiming_success():
    speech, stream, _ = adapter([bytes(1920)])
    audio = AsyncMock(side_effect=ConnectionError("device disconnected"))
    with pytest.raises(SpeechError, match="delivery failed"):
        await speech.speak("Hi", audio)
    audio.assert_awaited_once()
    assert stream.closed == 1


@pytest.mark.asyncio
async def test_explicit_model_voice_and_style_are_forwarded():
    speech, _stream, create = adapter(
        [bytes(2)], model="speech-snapshot", voice="cedar", instructions="Speak softly."
    )
    await speech.speak("Hi", AsyncMock())
    assert create.call_args.kwargs["model"] == "speech-snapshot"
    assert create.call_args.kwargs["voice"] == "cedar"
    assert create.call_args.kwargs["instructions"] == "Speak softly."


@pytest.mark.asyncio
async def test_prepared_greeting_replays_identical_pcm_without_a_provider_call():
    speech, _stream, create = adapter([b"\x01\x00" * 480, b"\x02\x00" * 40])
    await speech.prepare("Hello!")
    create.side_effect = AssertionError("Playback must not wait for the provider")
    output = AsyncMock()
    duration = await speech.speak("Hello!", output)
    assert (
        b"".join(call.args[0] for call in output.await_args_list)
        == b"\x01\x00" * 480 + b"\x02\x00" * 40
    )
    assert duration == pytest.approx(1040 / 48000)
    assert create.call_count == 1


@pytest.mark.asyncio
async def test_cancelled_prepared_greeting_stops_before_later_frames():
    speech, _stream, _create = adapter([bytes(960), bytes(960)])
    await speech.prepare("Hello!")
    entered = asyncio.Event()
    delivered = []

    async def blocked(pcm):
        delivered.append(pcm)
        entered.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(speech.speak("Hello!", blocked))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(delivered) == 1


@pytest.mark.asyncio
async def test_greeting_speed_is_sent_to_provider_and_part_of_cache_key():
    speech, _stream, create = adapter([bytes(960)])
    await speech.prepare("Hello!", speed=1.25)
    assert create.call_args.kwargs["speed"] == 1.25
    await speech.speak("Hello!", AsyncMock(), speed=1.25)
    assert create.call_count == 1
    await speech.speak("Hello!", AsyncMock())
    assert create.call_count == 2
    assert create.call_args.kwargs["speed"] == 1.0


@pytest.mark.asyncio
@pytest.mark.parametrize("speed", [True, 0, 4.1, float("nan"), float("inf")])
async def test_invalid_speed_never_calls_provider(speed):
    speech, _stream, create = adapter([bytes(960)])
    with pytest.raises(ValueError, match="speed"):
        await speech.speak("Hello!", AsyncMock(), speed=speed)
    create.assert_not_called()


@pytest.mark.asyncio
async def test_speech_preserves_network_category_without_exposing_provider_text():
    import httpx2
    from openai import APIConnectionError
    from blooglyblob.connectivity import failure_category

    error = APIConnectionError(
        message="private provider detail",
        request=httpx2.Request("GET", "https://example.com"),
    )
    speech, _, _ = adapter([error])
    with pytest.raises(SpeechError) as caught:
        await speech.speak("Hello", AsyncMock())
    assert "private" not in str(caught.value)
    assert failure_category(caught.value) == "network"
