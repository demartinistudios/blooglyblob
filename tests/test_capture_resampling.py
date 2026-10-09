"""Exercise the real capture processing worker without opening a microphone."""

import queue
import time

import numpy as np
import pytest

from blooglyblob.audio.driver import AudioDriver


def capture(pcm, packet_samples, *, gain=1):
    driver = AudioDriver()
    packets = iter(
        pcm[i : i + packet_samples * 2] for i in range(0, len(pcm), packet_samples * 2)
    )
    received = []

    class Input:
        def get(self, timeout):
            try:
                return time.monotonic(), next(packets)
            except StopIteration:
                driver._stop.set()
                raise queue.Empty

        def qsize(self):
            return 0

    def failed(reason):
        raise AssertionError(reason)

    driver._raw = Input()
    driver._gain = gain
    driver._on_input = received.append
    driver._on_failure = failed
    driver._capture()
    return b"".join(received)


def tone(hz, seconds=1):
    return (
        np.rint(10000 * np.sin(2 * np.pi * hz * np.arange(48000 * seconds) / 48000))
        .astype("<i2")
        .tobytes()
    )


def test_capture_produces_24khz_without_per_packet_timing_loss():
    pcm = tone(1000, 16)
    output = capture(pcm, 2048)
    # A live filter may retain a short tail until more input; never whole seconds.
    assert 16 * 24000 - 2400 <= len(output) // 2 <= 16 * 24000
    assert output == capture(pcm, 48000 * 16)


def test_capture_filters_frequencies_above_the_new_nyquist_limit():
    output = np.frombuffer(capture(tone(20000), 2048), dtype="<i2").astype(float)
    assert np.sqrt(np.mean(output[1000:-1000] ** 2)) < 10


def test_capture_retains_configured_gain_without_integer_wrap():
    pcm = tone(1000)
    unity = np.frombuffer(capture(pcm, 2048), dtype="<i2").astype(np.int32)
    amplified = np.frombuffer(capture(pcm, 2048, gain=4), dtype="<i2")
    np.testing.assert_array_equal(amplified, np.clip(unity * 4, -32767, 32767))


@pytest.mark.parametrize("hz", [1000, 4000, 8000])
def test_capture_preserves_speech_band_energy(hz):
    output = np.frombuffer(capture(tone(hz), 2048), dtype="<i2").astype(float)
    rms = np.sqrt(np.mean(output[1000:-1000] ** 2))
    assert abs(20 * np.log10(rms / (10000 / np.sqrt(2)))) < 0.1
