import json
import wave
import numpy as np
import pytest

from scripts.analyze_song_lights import analyze
from blooglyblob.hardware.music_lights import load_lights


def wav(path, samples, rate=44100):
    with wave.open(str(path), "wb") as f:
        f.setparams((samples.shape[1], 2, rate, 0, "NONE", ""))
        f.writeframes(samples.astype("<i2").tobytes())


def test_silence_stays_dark_and_antiphase_stereo_keeps_energy(tmp_path):
    path = tmp_path / "song.wav"
    wav(path, np.zeros((4410, 2)))
    silent = analyze(path)
    assert not any(v for row in silent["frames"] for v in row)
    t = np.arange(44100) / 44100
    tone = 16000 * np.sin(2 * np.pi * 1800 * t)
    wav(path, np.column_stack([tone, -tone]))
    data = analyze(path)
    assert len(data["frames"]) == 30
    assert sum(row[4] for row in data["frames"]) > 0
    sidecar = tmp_path / "lights.json"
    sidecar.write_text(json.dumps(data))
    lights = load_lights(path, sidecar)
    assert lights is not None
    assert len(lights.at(0.5)) == 8
    assert lights.at(1) == (0.0,) * 8
    assert lights.matches(path)
    wav(path, np.zeros((44100, 2)))
    assert not lights.matches(path)
    assert load_lights(path, sidecar) is None


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema=99),
        lambda d: d.update(fps=float("nan")),
        lambda d: d.update(frames=[[256] * 8]),
        lambda d: d.update(frames=[[True] * 8]),
        lambda d: d.update(frames=[[1] * 7]),
        lambda d: d.update(frames=[]),
    ],
)
def test_bad_sidecar_disables_only_lights(tmp_path, mutation):
    path = tmp_path / "song.wav"
    wav(path, np.zeros((4410, 1)))
    data = analyze(path)
    mutation(data)
    sidecar = tmp_path / "lights.json"
    sidecar.write_text(json.dumps(data))
    assert load_lights(path, sidecar) is None


def test_missing_oversized_and_non_object_sidecar(tmp_path):
    source, sidecar = tmp_path / "song.wav", tmp_path / "lights.json"
    wav(source, np.zeros((4410, 1)))
    assert load_lights(source, sidecar) is None
    sidecar.write_bytes(b" " * (1024 * 1024 + 1))
    assert load_lights(source, sidecar) is None
    sidecar.write_text("[]")
    assert load_lights(source, sidecar) is None
