import numpy as np
import pytest

from blooglyblob.audio.resampler import PCMResampler


def convert(pcm, packet_bytes=960):
    converter = PCMResampler(24000, 48000)
    return b"".join(
        [
            *(
                converter.process(pcm[i : i + packet_bytes])
                for i in range(0, len(pcm), packet_bytes)
            ),
            converter.process(b"", last=True),
        ]
    )


@pytest.mark.parametrize("hz", [200, 1000, 4000, 6000, 8000])
def test_speech_band_level_preserved(hz):
    samples = np.rint(12000 * np.sin(2 * np.pi * hz * np.arange(24000) / 24000)).astype(
        "<i2"
    )
    output = np.frombuffer(convert(samples.tobytes()), dtype="<i2")
    assert len(output) == 2 * len(samples)
    # Exclude filter startup/end transients from steady-state level measurement.
    rms_in = np.sqrt(np.mean(samples[2400:-2400].astype(float) ** 2))
    rms_out = np.sqrt(np.mean(output[4800:-4800].astype(float) ** 2))
    assert abs(20 * np.log10(rms_out / rms_in)) < 0.1


def test_packet_boundaries_do_not_change_audio_and_finish_preserves_short_tail():
    pcm = (
        np.random.default_rng(2)
        .integers(-12000, 12000, 10001, dtype=np.int16)
        .tobytes()
    )
    assert convert(pcm) == convert(pcm, 314)
    assert len(convert(b"\x01\x00" * 40)) == 160


def test_silence_stays_silent_and_conversion_does_not_wrap_full_scale():
    assert convert(bytes(960)) == bytes(1920)
    samples = np.full(2400, 32767, dtype="<i2")
    output = np.frombuffer(convert(samples.tobytes()), dtype="<i2")
    assert output.min() > 0


@pytest.mark.parametrize(
    "input_rate,output_rate",
    [(48000, 24000), (24000, 48000), (16000, 48000), (48000, 48000)],
)
def test_conversion_preserves_duration_and_is_independent_of_packets(
    input_rate, output_rate
):
    pcm = (
        np.random.default_rng(7)
        .integers(-12000, 12000, input_rate, dtype=np.int16)
        .tobytes()
    )
    whole = PCMResampler(input_rate, output_rate).process(pcm, last=True)
    split = PCMResampler(input_rate, output_rate)
    packets = b"".join(
        split.process(pcm[i : i + 4096]) for i in range(0, len(pcm), 4096)
    ) + split.process(b"", last=True)
    assert packets == whole
    assert len(whole) == output_rate * 2
    if input_rate == output_rate:
        assert whole is pcm


def test_converter_rejects_partial_samples_and_use_after_finish():
    converter = PCMResampler(48000, 24000)
    with pytest.raises(ValueError):
        converter.process(b"x")
    assert converter.process(b"") == b""
    assert converter.process(b"", last=True) == b""
    with pytest.raises(RuntimeError, match="finished"):
        converter.process(bytes(2))
