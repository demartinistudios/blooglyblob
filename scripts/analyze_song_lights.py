"""Generate spectrum-A dance lighting on the contributor machine, never the Pi.

Usage: python -m scripts.analyze_song_lights songs/dance_song.wav songs/dance_song_lights.json
Keep custom WAV/JSON pairs in the songs directory under BLOOGLYBLOB_MEDIA_DIR.
"""

import argparse
import json
import math
from pathlib import Path
import wave

import numpy as np

from blooglyblob.hardware.music_lights import (
    EDGES,
    FPS,
    WINDOW,
    PARAMETERS,
    MAX_BYTES,
    signature,
    wav_identity,
)


def analyze(path):
    before = signature(path)
    source = wav_identity(path)
    rate, count, channels = source["rate"], source["count"], source["channels"]
    total = math.ceil(count * FPS / rate)
    window = np.hanning(WINDOW)
    frequencies = np.fft.rfftfreq(WINDOW, 1 / rate)
    masks = [
        (frequencies >= lo) & (frequencies < hi) for lo, hi in zip(EDGES, EDGES[1:])
    ]
    raw, rms = np.zeros((total, 8)), np.zeros(total)
    with wave.open(str(path), "rb") as wav:
        for i in range(total):
            center = round(i * rate / FPS)
            start, end = max(0, center - WINDOW // 2), min(count, center + WINDOW // 2)
            wav.setpos(start)
            pcm = wav.readframes(end - start)
            if len(pcm) != (end - start) * channels * 2:
                raise ValueError("Truncated WAV")
            segment = np.zeros((WINDOW, channels))
            offset = start - (center - WINDOW // 2)
            segment[offset : offset + end - start] = (
                np.frombuffer(pcm, "<i2").reshape(-1, channels) / 32768
            )
            power = (
                np.mean(
                    np.abs(np.fft.rfft(segment * window[:, None], axis=0)) ** 2, axis=1
                )
                / np.sum(window**2)
                / WINDOW
            )
            raw[i] = [np.sqrt(2 * np.sum(power[mask])) for mask in masks]
            rms[i] = np.sqrt(np.mean(segment**2))
    db = 20 * np.log10(np.maximum(raw, 1e-9))
    ceiling = np.percentile(db, 98, axis=0)
    floor = np.maximum(-72, ceiling - 26)
    # Bands below the absolute floor stay dark, including an all-silent file.
    span = ceiling - floor
    bands = np.zeros_like(db)
    valid = span > 0
    bands[:, valid] = np.clip((db[:, valid] - floor[valid]) / span[valid], 0, 1) ** 1.65
    previous = np.zeros(8)
    frames = []
    for values, level in zip(bands, rms):
        tau = np.where(values > previous, 0.025, 0.14)
        previous += (values - previous) * (1 - np.exp(-1 / FPS / tau))
        if level < 0.001:
            previous[:] = 0
        frames.append(np.rint(previous * 255).astype(int).tolist())
    if signature(path) != before:
        raise ValueError("WAV changed during analysis")
    return dict(
        schema=1,
        algorithm="spectrum-a",
        source=source,
        fps=FPS,
        origin_seconds=0,
        window=WINDOW,
        edges=list(EDGES),
        parameters=PARAMETERS,
        soundtrack_notice="This data accompanies the source WAV; see LICENSING.md, Project soundtrack: separate terms.",
        frames=frames,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "wav",
        type=Path,
        help="Native mono/stereo PCM16 WAV, 32–192 kHz, up to 10 minutes",
    )
    parser.add_argument(
        "output", type=Path, help="Matching dance_song_lights.json destination"
    )
    args = parser.parse_args()
    if args.wav.resolve() == args.output.resolve():
        parser.error("Output must not overwrite the WAV")
    analysis = analyze(args.wav)
    data = json.dumps(analysis, separators=(",", ":"), allow_nan=False) + "\n"
    if len(data.encode()) > MAX_BYTES:
        parser.error("Analysis exceeds the runtime size limit")
    args.output.write_text(data)
    print(f"Wrote {args.output}: {len(analysis['frames'])} frames at {FPS} fps")


if __name__ == "__main__":
    main()
