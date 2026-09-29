import asyncio
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock

import numpy as np
import pytest
from tests.support.conversation import session

from blooglyblob.audio.voice_effects import RingModulator
from blooglyblob.ai.voice_profile import output_effect_factory


def signal():
    return np.array(
        [-32768, -16000, -1, 0, 1, 16000, 32767] * 401, dtype="<i2"
    ).tobytes()


def test_effect_is_independent_of_packet_boundaries_and_preserves_duration():
    pcm = signal()
    expected = RingModulator(mix=0.55).process(pcm)
    effect = RingModulator(mix=0.55)
    boundaries = [0, 2, 38, 960, 1458, len(pcm)]
    actual = b"".join(
        effect.process(pcm[a:b]) for a, b in zip(boundaries, boundaries[1:])
    )
    assert actual == expected
    assert len(actual) == len(pcm)
    assert actual != pcm
    assert effect.process(b"") == b""  # No buffered tail on end/cancel.


def test_effect_cannot_amplify_or_wrap_full_scale_samples():
    pcm = signal()
    source = np.frombuffer(pcm, dtype="<i2").astype(np.int32)
    for mix in (0.25, 0.55, 1):
        output = np.frombuffer(RingModulator(mix=mix).process(pcm), dtype="<i2").astype(
            np.int32
        )
        assert np.all(np.abs(output) <= np.abs(source))
    negative_full_scale = np.full(2400, -32768, dtype="<i2").tobytes()
    inverted = np.frombuffer(
        RingModulator(mix=1).process(negative_full_scale), dtype="<i2"
    )
    assert inverted[1200] == 32767  # Saturate positive full scale; never wrap.


def test_disabled_effect_is_bit_exact_and_silence_stays_silent():
    pcm = signal()
    assert RingModulator().process(pcm) is pcm
    assert RingModulator(mix=0.55).process(bytes(960)) == bytes(960)


def test_shipped_effect_preserves_pcm_and_finishes_without_a_tail():
    effect = output_effect_factory()()
    pcm = signal()
    assert effect.process(pcm) is pcm
    assert effect.process(bytes(960)) == bytes(960)
    assert effect.finish() is None
    assert effect.finish() is None
    with pytest.raises(ValueError, match="finished"):
        effect.process(pcm)


@pytest.mark.parametrize(
    "settings",
    [
        {"mix": -0.1},
        {"mix": 1.1},
        {"mix": float("nan")},
        {"mix": True},
        {"carrier_hz": 0},
        {"carrier_hz": 401},
        {"carrier_hz": 70.5},
    ],
)
def test_invalid_effect_settings_fail_closed(settings):
    with pytest.raises(ValueError):
        RingModulator(**settings)


@pytest.mark.parametrize("pcm", [b"x", bytearray(2), None])
def test_invalid_pcm_rejected_even_when_disabled(pcm):
    with pytest.raises(ValueError):
        RingModulator().process(pcm)


@pytest.mark.asyncio
@pytest.mark.parametrize("activity", ["conversation", "sleep"])
async def test_live_and_speech_apply_effect_and_reset_for_next_generation(activity):
    pcm = signal()[:960]

    async def speak(text, output):
        await output(pcm)
        await output(pcm)

    host, hardware, _ = session(
        speech=SimpleNamespace(speak=speak),
        voice_effect_factory=partial(RingModulator, mix=0.55),
    )
    hardware.execute = AsyncMock(return_value="Going to sleep")
    host.media.audio = AsyncMock()
    try:
        for _ in range(2):
            host._request_activity(activity)
            if activity == "conversation":

                async def ready():
                    while host.live is None or host.media.generation is None:
                        await asyncio.sleep(0)

                await asyncio.wait_for(ready(), 1)
                output = host.live.callbacks["on_audio"]
                await output(pcm)
                await output(pcm)
                host.request(False)
                await asyncio.wait_for(host._runner, 1)
                await output(pcm)  # Old generation must not emit more audio.
            else:
                await asyncio.wait_for(host._runner, 1)
        delivered = [call.args[1] for call in host.media.audio.await_args_list]
        effect = RingModulator(mix=0.55)
        expected = [effect.process(pcm), effect.process(pcm)]
        assert delivered == expected * 2
    finally:
        await host.close()
