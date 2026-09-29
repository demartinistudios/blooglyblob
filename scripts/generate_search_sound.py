"""Generate the accepted 30-second scanner loop from mathematical tones only.

No external samples or dependencies. Run from the repository root:
    python3 scripts/generate_search_sound.py --output sounds/search_16k.wav

Output: mono, 16 kHz, signed 16-bit PCM. Overwrites the specified file.
"""

import argparse
import math
import random
import struct
import wave
from pathlib import Path

RATE = 16000
DURATION = 30.0


def render_search() -> bytes:
    rng = random.Random(20260921)
    events = []
    onset = 0.08
    frequencies = (783.99, 880.0, 1046.5, 1174.66, 1318.51, 1567.98)
    while onset < DURATION - 0.2:
        length = rng.uniform(0.065, 0.12)
        frequency = rng.choice(frequencies)
        sweep = rng.choice((-0.04, 0.04, 0.08)) * frequency
        events.append((onset, length, frequency, sweep, rng.uniform(0.075, 0.12)))
        onset += rng.uniform(0.105, 0.17)
    samples = [0.0] * round(RATE * DURATION)
    for onset, length, frequency, sweep, gain in events:
        start = round(onset * RATE)
        for offset in range(round(length * RATE)):
            age = offset / RATE
            position = age / length
            envelope = math.sin(math.pi * position) ** 2
            phase = 2 * math.pi * (frequency * age + 0.5 * sweep * age * age / length)
            tone = math.sin(phase + 0.10 * math.sin(2 * math.pi * 18 * age))
            samples[start + offset] += gain * envelope * tone
    pcm = bytearray()
    for index, value in enumerate(samples):
        time = index / RATE
        # Gentle boundary fades; no low drone beneath the brighter pulses.
        edge = min(time / 0.3, (DURATION - time) / 0.3, 1.0)
        fade = 0.5 - 0.5 * math.cos(math.pi * max(edge, 0.0))
        pcm.extend(struct.pack("<h", round(32767 * fade * value)))
    return bytes(pcm)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="Output WAV path")
    args = parser.parse_args()
    pcm = render_search()
    with wave.open(str(args.output), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes(pcm)
    print(f"Wrote {args.output}: {DURATION}s, mono, {RATE} Hz, 16-bit PCM")


if __name__ == "__main__":
    main()
