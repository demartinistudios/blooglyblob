#!/usr/bin/env python3
"""Generate an original 1.5-second alert using mathematical tones only.

No recordings, external samples, cloud services, or third-party libraries.
Run from the repository root:
    python3 scripts/generate_alert_sound.py --output /tmp/blooglyblob-alert-preview.wav

The output is mono, 16 kHz, signed 16-bit PCM, suitable for the Pi alert player.
An existing output file is overwritten; its parent directory must exist.
"""

import argparse
import math
import struct
import wave
from pathlib import Path


SAMPLE_RATE = 16000
DURATION = 1.5


def render_alert() -> bytes:
    """Render two ascending, softly struck notes with smooth fades."""
    notes = ((0.02, 659.255, 0.58), (0.44, 880.0, 1.00))
    samples = bytearray()
    for index in range(round(SAMPLE_RATE * DURATION)):
        time = index / SAMPLE_RATE
        value = 0.0
        for onset, frequency, length in notes:
            age = time - onset
            if not 0 <= age < length:
                continue
            attack = 0.5 - 0.5 * math.cos(math.pi * min(age / 0.012, 1.0))
            release = 0.5 - 0.5 * math.cos(math.pi * min((length - age) / 0.08, 1.0))
            envelope = attack * release * math.exp(-3.5 * age)
            phase = 2 * math.pi * frequency * age
            tone = math.sin(phase) + 0.12 * math.sin(2 * phase)
            value += 0.32 * envelope * tone
        samples.extend(struct.pack("<h", round(value * 32767)))
    return bytes(samples)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="Output WAV path")
    args = parser.parse_args()
    with wave.open(str(args.output), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(SAMPLE_RATE)
        output.writeframes(render_alert())
    print(f"Wrote {args.output}: {DURATION}s, mono, {SAMPLE_RATE} Hz, 16-bit PCM")


if __name__ == "__main__":
    main()
