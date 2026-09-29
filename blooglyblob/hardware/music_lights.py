"""Bounded precomputed dance lighting; invalid data never prevents playback."""

from dataclasses import dataclass
import hashlib
import json
import logging
import math
from pathlib import Path
import wave

FPS = 30
WINDOW = 2048
EDGES = (40, 100, 250, 500, 1000, 2000, 4000, 8000, 16000)
MAX_BYTES = 1024 * 1024
PARAMETERS = {
    "range_db": 26,
    "exponent": 1.65,
    "attack_seconds": 0.025,
    "release_seconds": 0.14,
    "silence_dbfs": -60,
    "percentile": 98,
}
log = logging.getLogger(__name__)


def signature(path):
    stat = Path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def wav_identity(path):
    with wave.open(str(path), "rb") as source:
        rate, count, channels, width = (
            source.getframerate(),
            source.getnframes(),
            source.getnchannels(),
            source.getsampwidth(),
        )
        if not (
            32000 <= rate <= 192000
            and 0 < count <= rate * 600
            and channels in (1, 2)
            and width == 2
        ):
            raise ValueError(
                "Lighting analysis requires at most ten minutes of mono/stereo PCM16 at 32–192 kHz"
            )
    with Path(path).open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return dict(sha256=digest, rate=rate, count=count, channels=channels, width=width)


@dataclass(frozen=True)
class MusicLights:
    frames: bytes
    duration: float
    source_signature: tuple[int, ...]

    def matches(self, path):
        try:
            return signature(path) == self.source_signature
        except OSError:
            return False

    def at(self, seconds):
        if not math.isfinite(seconds) or not 0 <= seconds < self.duration:
            return (0.0,) * 8
        index = int(seconds * FPS) * 8
        return tuple(v / 255 for v in self.frames[index : index + 8])


def load_lights(source, sidecar):
    try:
        before = signature(source)
        with Path(sidecar).open("rb") as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Lighting sidecar is too large")
        data = json.loads(raw)
        if (
            not isinstance(data, dict)
            or type(data.get("schema")) is not int
            or data["schema"] != 1
            or data.get("algorithm") != "spectrum-a"
            or data.get("fps") != FPS
            or data.get("window") != WINDOW
            or data.get("edges") != list(EDGES)
            or data.get("parameters") != PARAMETERS
            or data.get("origin_seconds") != 0
        ):
            raise ValueError("Unsupported lighting analysis")
        identity = wav_identity(source)
        if data.get("source") != identity or signature(source) != before:
            raise ValueError("Lighting analysis does not match selected WAV")
        rows = data.get("frames")
        count = math.ceil(identity["count"] * FPS / identity["rate"])
        if not isinstance(rows, list) or len(rows) != count:
            raise ValueError("Invalid lighting frame count")
        frames = bytearray()
        for row in rows:
            if (
                not isinstance(row, list)
                or len(row) != 8
                or any(type(v) is not int or not 0 <= v <= 255 for v in row)
            ):
                raise ValueError("Invalid lighting drives")
            frames.extend(row)
        return MusicLights(bytes(frames), identity["count"] / identity["rate"], before)
    except (
        OSError,
        ValueError,
        TypeError,
        OverflowError,
        RecursionError,
        wave.Error,
        EOFError,
    ):
        log.warning("Dance mouth disabled: missing, invalid or stale lighting analysis")
        return None
