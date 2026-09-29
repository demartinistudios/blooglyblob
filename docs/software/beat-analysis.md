# Analyze a dance song

`scripts/analyze_beats.py` estimates tempo and beat times from a local audio
file. The robot uses these timestamps to synchronize dance movements with the
song. Run the helper on your computer when preparing or replacing dance music;
normal Pi operation uses the already generated JSON and needs no analysis library.

## Set up once

From the repository root, use Python 3.13 to create a separate, ignored environment:

```sh
python3.13 -m venv .venv-beats
.venv-beats/bin/python -m pip install 'librosa==1.0.0'
```

This installs the optional [librosa analysis library](https://librosa.org/doc/latest/install.html)
and its dependencies without adding them to the project's development or Pi
environments. The tool reads local audio; it needs no API key or cloud service.
WAV is the recommended input format.

## Run the helper

Check its arguments:

```sh
.venv-beats/bin/python scripts/analyze_beats.py --help
```

Analyze the current song without replacing the committed beat data:

```sh
.venv-beats/bin/python scripts/analyze_beats.py \
  --song songs/dance_song.wav \
  --output /tmp/blooglyblob-beats-preview.json
```

For another song, pass its file path to `--song`. The output parent directory
must already exist. An existing output file is overwritten.

With no arguments, the helper reads `songs/dance_song.wav` and overwrites
`songs/dance_song_beats.json`. If only `--song` is supplied, output is written
beside that file as `<song-name>_beats.json`.

## Understand and use the output

The JSON contains:

- `bpm`: estimated beats per minute, rounded to one decimal place.
- `beats`: beat positions in seconds from the start of the audio, rounded to
  three decimal places.
- `duration`: audio length in seconds, rounded to two decimal places.

Beat detection is an estimate. Listen to the song and check the timing before
accepting it; songs with changing tempo, long introductions, or weak percussion
may need manual corrections. Detection does not edit the audio or clear its
redistribution rights.

The runtime reads `songs/dance_song.wav` and `songs/dance_song_beats.json` as a
pair. When intentionally adopting a new song, put the approved WAV at that
location, generate matching beat data, and review both changes. Update their
sizes, SHA-256 hashes, and provenance in
[`docs/release/asset-manifest.json`](../release/asset-manifest.json).
Then use the normal `make pi-update` workflow to deploy the pair and verify
dance timing on the device. A temporary preview JSON is not deployed.

## Troubleshooting

- `No module named librosa`: use `.venv-beats/bin/python` and run the installation
  command above; the normal development environment does not include this library.
- Missing song: check the path and run from the repository root, or use an
  absolute path to the input file.
- Audio decoding error: supply a valid WAV file rather than relying on support
  for another format.
- Cannot write output: choose an existing, writable directory with `--output`.

The first analysis can take longer while numerical routines initialize. Keep
the original song and beat data until the replacement has been reviewed.
