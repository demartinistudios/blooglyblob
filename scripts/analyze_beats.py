#!/usr/bin/env python3
"""
Beat analysis script for dance mode.

Extracts beat timestamps from a song using librosa.
Run on the builder's computer, not on the Pi. Install the optional librosa
dependency separately; see docs/software/beat-analysis.md for setup and usage.

Usage:
    python scripts/analyze_beats.py [--song songs/dance_song.wav]
"""

import argparse
import json
from pathlib import Path

import librosa


def analyze_beats(song_path: Path, output_path: Path | None = None) -> dict:
    """Analyze a song and extract beat timestamps.

    Args:
        song_path: Path to the audio file (WAV recommended)
        output_path: Path to write JSON output (defaults to same dir as song)

    Returns:
        Dict with bpm, beats (timestamps in seconds), and duration
    """
    print(f"Loading {song_path}...")
    y, sr = librosa.load(song_path, sr=None)

    duration = librosa.get_duration(y=y, sr=sr)
    print(f"Duration: {duration:.2f}s, Sample rate: {sr}Hz")

    print("Detecting beats...")
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)

    # Convert beat frames to timestamps
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)

    # Tempo might be an array in newer librosa versions
    bpm = float(tempo) if isinstance(tempo, (int, float)) else float(tempo[0])

    print(f"Detected BPM: {bpm:.1f}")
    print(f"Found {len(beat_times)} beats")

    result = {
        "bpm": round(bpm, 1),
        "beats": [round(float(t), 3) for t in beat_times],
        "duration": round(duration, 2),
    }

    # Write output
    if output_path is None:
        output_path = song_path.with_suffix("").with_name(
            song_path.stem + "_beats.json"
        )

    print(f"Writing to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)

    print("Done!")
    return result


def main():
    parser = argparse.ArgumentParser(description="Analyze beats in a song")
    parser.add_argument(
        "--song",
        type=Path,
        default=Path("songs/dance_song.wav"),
        help="Path to the song file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path (default: <song>_beats.json)",
    )
    args = parser.parse_args()

    if not args.song.exists():
        print(f"Error: Song file not found: {args.song}")
        print(
            "Provide a local audio file with --song; see docs/software/beat-analysis.md"
        )
        return 1

    analyze_beats(args.song, args.output)
    return 0


if __name__ == "__main__":
    exit(main())
