import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from blooglyblob.ai.announcements import SLEEP_FAREWELL, fixed_announcements
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
        {"max_audio_seconds": 31},
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
    await speech.prepare(SLEEP_FAREWELL)
    create.side_effect = AssertionError("Playback must not wait for the provider")
    output = AsyncMock()
    duration = await speech.speak(SLEEP_FAREWELL, output)
    assert (
        b"".join(call.args[0] for call in output.await_args_list)
        == b"\x01\x00" * 480 + b"\x02\x00" * 40
    )
    assert duration == pytest.approx(1040 / 48000)
    assert create.call_count == 1


@pytest.mark.asyncio
async def test_cancelled_prepared_greeting_stops_before_later_frames():
    speech, _stream, _create = adapter([bytes(960), bytes(960)])
    await speech.prepare(SLEEP_FAREWELL)
    entered = asyncio.Event()
    delivered = []

    async def blocked(pcm):
        delivered.append(pcm)
        entered.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(speech.speak(SLEEP_FAREWELL, blocked))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(delivered) == 1


@pytest.mark.asyncio
async def test_greeting_speed_is_sent_to_provider_and_part_of_cache_key():
    speech, _stream, create = adapter(
        [bytes(960)], announcements=fixed_announcements("Hello!")
    )
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


@pytest.mark.asyncio
async def test_all_four_slots_survive_restart_with_identical_pcm(tmp_path):
    phrases = fixed_announcements("Hello!")
    first, _, create = adapter(
        [b"a" * 960, b"b" * 2], cache_dir=tmp_path, announcements=phrases
    )
    for text, speed in phrases.values():
        await first.prepare(text, speed=speed)
    assert create.call_count == 4
    second, _, restarted = adapter([], cache_dir=tmp_path, announcements=phrases)
    for text, speed in phrases.values():
        audio = AsyncMock()
        assert await second.speak(text, audio, speed=speed) == pytest.approx(
            962 / 48000
        )
        assert (
            b"".join(call.args[0] for call in audio.await_args_list)
            == b"a" * 960 + b"b" * 2
        )
    restarted.assert_not_called()
    assert len(list(tmp_path.iterdir())) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["text", "model", "voice", "instructions", "speed"])
async def test_slot_settings_invalidate_without_accumulating_versions(tmp_path, change):
    phrases = fixed_announcements("Hello!")
    first, _, _ = adapter([bytes(2)], cache_dir=tmp_path, announcements=phrases)
    await first.prepare("Hello!", speed=1.25)
    options = {}
    if change == "text":
        phrases = fixed_announcements("Hello again!")
    elif change == "speed":
        phrases["greeting"] = ("Hello!", 1.0)
    else:
        options[change] = "changed"
    second, _, create = adapter(
        [b"ab"], cache_dir=tmp_path, announcements=phrases, **options
    )
    text, speed = phrases["greeting"]
    audio = AsyncMock()
    await second.speak(text, audio, speed=speed)
    create.assert_called_once()
    audio.assert_awaited_once_with(b"ab")
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_cold_playback_does_not_wait_for_optional_disk_persistence(tmp_path):
    speech, _, create = adapter([b"ab"], cache_dir=tmp_path)
    save = AsyncMock(side_effect=TimeoutError)
    speech._save_slot = save
    audio = AsyncMock()

    assert await speech.speak(SLEEP_FAREWELL, audio) == pytest.approx(2 / 48000)
    audio.assert_awaited_once_with(b"ab")
    save.assert_not_awaited()

    # Background preparation can persist the completed audio without another API call.
    save.side_effect = None
    await speech.prepare(SLEEP_FAREWELL)
    save.assert_awaited_once()
    create.assert_called_once()


@pytest.mark.asyncio
async def test_cold_playback_streams_before_completion_and_preparation_deduplicates(
    tmp_path,
):
    release = asyncio.Event()
    speech, _, create = adapter([bytes(960), release, bytes(2)], cache_dir=tmp_path)
    heard = asyncio.Event()

    async def output(_pcm):
        heard.set()

    playing = asyncio.create_task(speech.speak(SLEEP_FAREWELL, output))
    await heard.wait()
    warming = asyncio.create_task(speech.prepare(SLEEP_FAREWELL))
    await asyncio.sleep(0)
    assert not playing.done()
    release.set()
    await asyncio.gather(playing, warming)
    assert create.call_count == 1


@pytest.mark.asyncio
async def test_cancelled_partial_preparation_is_not_cached(tmp_path):
    release = asyncio.Event()
    speech, stream, create = adapter([bytes(960), release], cache_dir=tmp_path)
    pending = asyncio.create_task(speech.prepare(SLEEP_FAREWELL))
    await stream.entered.wait()
    await asyncio.sleep(0)
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    assert not list(tmp_path.iterdir())
    release.set()
    await speech.prepare(SLEEP_FAREWELL)
    assert create.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "damage", [b"broken", bytes(1500000)], ids=["corrupt", "oversized"]
)
async def test_corrupt_or_oversized_disk_slot_regenerates(tmp_path, damage):
    speech, _, _ = adapter([bytes(2)], cache_dir=tmp_path)
    await speech.prepare(SLEEP_FAREWELL)
    next(tmp_path.iterdir()).write_bytes(damage)
    restarted, _, create = adapter([b"ab"], cache_dir=tmp_path)
    await restarted.prepare(SLEEP_FAREWELL)
    create.assert_called_once()
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_only_registered_four_slots_can_be_prepared(tmp_path):
    speech, _, create = adapter([bytes(2)], cache_dir=tmp_path)
    with pytest.raises(ValueError, match="registered"):
        await speech.prepare("unregistered")
    await speech.speak("unregistered", AsyncMock())
    assert create.call_count == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_speech_stage_logs_source_and_numeric_timings_without_text(caplog):
    caplog.set_level("INFO", logger="blooglyblob.ai.speech")
    speech, _, _ = adapter([bytes(2)])
    await speech.speak(SLEEP_FAREWELL, AsyncMock())
    await speech.speak(SLEEP_FAREWELL, AsyncMock())
    assert "source=provider" in caplog.text
    assert "source=memory" in caplog.text
    assert "stage=request" in caplog.text
    assert "stage=first_pcm" in caplog.text
    assert "elapsed_ms=" in caplog.text
    assert SLEEP_FAREWELL not in caplog.text


@pytest.mark.asyncio
async def test_cancelled_disk_staging_cannot_publish_after_worker_finishes(
    tmp_path, monkeypatch
):
    import threading
    import os

    fsync = os.fsync
    entered, release = threading.Event(), threading.Event()

    def slow_fsync(fd):
        entered.set()
        assert release.wait(2)
        fsync(fd)

    monkeypatch.setattr("blooglyblob.ai.speech.os.fsync", slow_fsync)
    workers = []

    async def work(operation):
        task = asyncio.create_task(asyncio.to_thread(operation))
        workers.append(task)
        return await asyncio.shield(task)

    speech, _, create = adapter([bytes(2)], cache_dir=tmp_path, work=work)
    pending = asyncio.create_task(speech.prepare(SLEEP_FAREWELL))
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    finally:
        release.set()
        await asyncio.gather(*workers)
    assert not list(tmp_path.iterdir())
    await speech.prepare(SLEEP_FAREWELL)
    assert create.call_count == 2


@pytest.mark.asyncio
async def test_bad_cache_directory_keeps_successful_audio_in_memory(tmp_path):
    cache_path = tmp_path / "not-a-directory"
    cache_path.write_bytes(b"existing data")
    speech, _, create = adapter([bytes(2)], cache_dir=cache_path)
    await speech.prepare(SLEEP_FAREWELL)
    await speech.speak(SLEEP_FAREWELL, AsyncMock())
    assert create.call_count == 1
    assert cache_path.read_bytes() == b"existing data"


@pytest.mark.asyncio
async def test_other_slot_playback_does_not_wait_for_slow_warmup():
    from blooglyblob.ai.announcements import DANCE_INTRODUCTION

    release = asyncio.Event()
    speech, slow_stream, create = adapter([release, bytes(2)])
    create.side_effect = [slow_stream, Stream([bytes(2)])]
    warming = asyncio.create_task(speech.prepare(SLEEP_FAREWELL))
    await slow_stream.entered.wait()
    await asyncio.wait_for(speech.speak(DANCE_INTRODUCTION, AsyncMock()), 0.1)
    assert not warming.done()
    release.set()
    await warming
    assert create.call_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "chunks",
    [[bytes(960), b"x"], [bytes(960), RuntimeError("private")]],
    ids=["partial", "provider_failure"],
)
async def test_failed_cold_delivery_is_not_cached(tmp_path, chunks):
    speech, _, create = adapter(chunks, cache_dir=tmp_path)
    with pytest.raises(SpeechError):
        await speech.speak(SLEEP_FAREWELL, AsyncMock())
    assert not list(tmp_path.iterdir())
    create.return_value = Stream([bytes(2)])
    await speech.prepare(SLEEP_FAREWELL)
    assert create.call_count == 2


@pytest.mark.asyncio
async def test_valid_header_with_altered_pcm_is_rejected(tmp_path):
    speech, _, _ = adapter([b"ab"], cache_dir=tmp_path)
    await speech.prepare(SLEEP_FAREWELL)
    path = next(tmp_path.iterdir())
    data = path.read_bytes()
    path.write_bytes(data[:-2] + b"cd")
    restarted, _, create = adapter([b"ef"], cache_dir=tmp_path)
    audio = AsyncMock()
    await restarted.speak(SLEEP_FAREWELL, audio)
    create.assert_called_once()
    audio.assert_awaited_once_with(b"ef")


@pytest.mark.asyncio
async def test_retired_disk_worker_cannot_damage_a_later_same_slot_save(
    tmp_path, monkeypatch
):
    import os
    import threading

    fsync = os.fsync
    entered, release, second_staging = (
        threading.Event(),
        threading.Event(),
        asyncio.Event(),
    )
    writes = 0

    def slow_first_fsync(fd):
        nonlocal writes
        writes += 1
        if writes == 1:
            entered.set()
            assert release.wait(2)
        fsync(fd)

    monkeypatch.setattr("blooglyblob.ai.speech.os.fsync", slow_first_fsync)
    workers = []
    submitted = 0

    async def work(operation):
        nonlocal submitted
        submitted += 1
        task = asyncio.create_task(asyncio.to_thread(operation))
        workers.append(task)
        if submitted == 4:  # Each attempt reads, synthesizes, then stages.
            second_staging.set()
        return await asyncio.shield(task)

    speech, _, create = adapter([b"aa"], cache_dir=tmp_path, work=work)
    first = asyncio.create_task(speech.prepare(SLEEP_FAREWELL))
    second = None
    try:
        assert await asyncio.to_thread(entered.wait, 1)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        create.return_value = Stream([b"bb"])
        second = asyncio.create_task(speech.prepare(SLEEP_FAREWELL))
        await asyncio.wait_for(second_staging.wait(), 1)
        assert not second.done()
    finally:
        release.set()
        if second is not None:
            await second
        await asyncio.gather(*workers)
    restarted, _, provider = adapter([], cache_dir=tmp_path)
    output = AsyncMock()
    await restarted.speak(SLEEP_FAREWELL, output)
    provider.assert_not_called()
    output.assert_awaited_once_with(b"bb")
    assert len(list(tmp_path.iterdir())) == 1
