"""Scanner mixing preserves speech and leaves device I/O to its caller."""

import wave

import numpy as np
import pytest

from blooglyblob.audio.background import BackgroundSound


RATE = 48000


def pcm(samples):
    return np.asarray(samples, dtype="<i2").tobytes()


def samples(data):
    return np.frombuffer(data, dtype="<i2").astype(np.int32)


def silence(seconds):
    return bytes(round(RATE * seconds) * 2)


def rms(data):
    return np.sqrt(np.mean(samples(data).astype(float) ** 2))


def test_actual_speech_ducks_scanner_then_hold_and_silence_restore_it():
    effect = BackgroundSound(pcm(np.full(RATE, 10000)))
    effect.mix(silence(0.2))
    normal = rms(effect.mix(silence(0.02)))
    voice = pcm(6000 * np.sin(2 * np.pi * 400 * np.arange(4800) / RATE))
    ducked = samples(effect.mix(voice)) - samples(voice)
    assert normal == pytest.approx(1200, abs=1)
    assert np.sqrt(np.mean(ducked[-960:].astype(float) ** 2)) == pytest.approx(
        180, abs=1
    )
    assert rms(effect.mix(silence(0.1))) == pytest.approx(180, abs=1)
    effect.mix(silence(0.5))
    assert rms(effect.mix(silence(0.02))) == pytest.approx(normal, abs=1)


def test_silent_packets_do_not_trigger_ducking():
    effect = BackgroundSound(pcm([10000]))
    effect.mix(silence(0.2))
    assert rms(effect.mix(silence(0.2))) == pytest.approx(1200, abs=1)


def test_clip_loops_continuously_across_packet_boundaries():
    effect = BackgroundSound(pcm([1000, -2000, 3000]))
    effect.mix(silence(0.2))
    first = samples(effect.mix(bytes(8)))
    second = samples(effect.mix(bytes(8)))
    np.testing.assert_array_equal(
        np.concatenate([first, second]), [120, -240, 360, 120, -240, 360, 120, -240]
    )


def test_start_and_stop_are_smooth_and_finished_preserves_voice_exactly():
    effect = BackgroundSound(pcm([10000]))
    output = samples(effect.mix(silence(0.15)))
    assert output[0] <= 1
    assert max(abs(np.diff(output))) <= 1
    effect.stop()
    tail = samples(effect.mix(silence(0.05)))
    assert abs(tail[0] - output[-1]) <= 1
    assert max(abs(np.diff(tail))) <= 1
    assert not tail[-480:].any()
    assert effect.finished
    voice = pcm([-32768, -1000, 0, 1000, 32767])
    assert effect.mix(voice) == voice
    effect.stop()
    assert effect.mix(voice) == voice


@pytest.mark.parametrize("clip", [[32767], [-32768]])
def test_only_effect_contribution_is_limited_to_speech_headroom(clip):
    effect = BackgroundSound(pcm(clip))
    effect.mix(silence(0.2))
    voice = pcm([-32768, -32767, -100, 0, 100, 32766, 32767])
    output = samples(effect.mix(voice))
    delta = output - samples(voice)
    assert output.min() >= -32768 and output.max() <= 32767
    if clip[0] > 0:
        assert (delta >= 0).all()
        assert output[-1] == 32767
    else:
        assert (delta <= 0).all()
        assert output[0] == -32768


def test_stop_duration_is_independent_of_packet_size():
    effect = BackgroundSound(pcm([10000]))
    effect.mix(silence(0.2))
    effect.stop()
    effect.mix(silence(0.02))
    assert not effect.finished
    effect.stop()  # repeated requests do not extend the fade
    effect.mix(silence(0.02))
    assert effect.finished


def test_wav_is_loaded_and_resampled_once(tmp_path):
    path = tmp_path / "scanner.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(pcm([10000] * 1600))
    effect = BackgroundSound.from_wav(path)
    path.unlink()  # all subsequent playback is in memory
    effect.mix(silence(0.2))
    assert rms(effect.mix(silence(0.02))) == pytest.approx(1200, abs=1)


@pytest.mark.parametrize(
    "channels,width,frames", [(2, 2, 10), (1, 1, 10), (1, 2, 0), (1, 2, 16000 * 61)]
)
def test_invalid_wav_is_rejected(tmp_path, channels, width, frames):
    path = tmp_path / "invalid.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setparams((channels, width, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(bytes(frames * channels * width))
    with pytest.raises(ValueError):
        BackgroundSound.from_wav(path)


@pytest.mark.parametrize("data", [b"", b"\x00", bytes((RATE * 60 + 1) * 2)])
def test_invalid_native_clip_is_rejected(data):
    with pytest.raises(ValueError):
        BackgroundSound(data)


def test_stop_during_startup_fades_from_current_volume_without_rising():
    effect = BackgroundSound(pcm([10000]))
    opening = samples(effect.mix(silence(0.01)))
    effect.stop()
    ending = samples(effect.mix(silence(0.04)))
    assert ending[0] <= opening[-1]
    assert (np.diff(ending) <= 0).all()
    assert effect.finished


def test_empty_frames_do_not_advance_loop_or_fades():
    effect = BackgroundSound(pcm([10000]))
    assert effect.mix(b"") == b""
    effect.stop()
    assert effect.mix(b"") == b""
    assert not effect.finished
    with pytest.raises(ValueError):
        effect.mix(b"\x00")


def test_truncated_or_non_wav_recording_is_rejected(tmp_path):
    path = tmp_path / "broken.wav"
    path.write_bytes(b"not a WAV recording")
    with pytest.raises(ValueError):
        BackgroundSound.from_wav(path)
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(bytes(100))
    path.write_bytes(path.read_bytes()[:-4])
    with pytest.raises(ValueError, match="truncated"):
        BackgroundSound.from_wav(path)


def test_fresh_shares_read_only_clip_and_resets_all_playback_state():
    template = BackgroundSound(pcm([1000, -2000, 3000]))
    expected = BackgroundSound(pcm([1000, -2000, 3000]))
    template.mix(pcm([6000] * 4801))  # Advance phase, duck, hold and start fade.
    template.stop()
    template.mix(silence(0.04))
    assert template.finished

    fresh = template.fresh()
    other = fresh.fresh()
    assert fresh._clip is template._clip
    assert not fresh._clip.flags.writeable
    with pytest.raises(ValueError):
        fresh._clip[0] = 0
    assert not fresh.finished
    opening = silence(0.12)
    assert fresh.mix(opening) == expected.mix(opening)
    fresh.stop()
    fresh.mix(silence(0.04))
    assert fresh.finished
    assert not other.finished
    assert other.mix(opening) == BackgroundSound(pcm([1000, -2000, 3000])).mix(opening)


def test_loaded_template_can_create_fresh_playback_without_file_or_resampling(
    tmp_path, monkeypatch
):
    path = tmp_path / "scanner.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        stream.writeframes(pcm([10000] * 1600))
    template = BackgroundSound.from_wav(path)
    path.unlink()

    def unexpected(*args, **kwargs):
        pytest.fail("fresh playback must not load or resample the recording")

    monkeypatch.setattr("blooglyblob.audio.background.PCMResampler", unexpected)
    monkeypatch.setattr("blooglyblob.audio.background.wave.open", unexpected)
    fresh = template.fresh()
    fresh.mix(silence(0.2))
    assert rms(fresh.mix(silence(0.02))) == pytest.approx(1200, abs=1)
