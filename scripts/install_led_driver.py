#!/usr/bin/env python3
"""Install the pinned upstream LED driver with additive Pi 3A+ rev 1.1 support.

Upstream fix (not in the published Python 5.0.0 package):
https://github.com/jgarff/rpi_ws281x/commit/09f4ef2b12b448ff1bd7d461b7b557139c8f2109
Retain upstream license files in the source build. Remove this backport when a
qualified Python release includes it; never follow an unpinned upstream branch.
"""

from importlib.metadata import PackageNotFoundError, version
import ctypes
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

VERSION = "5.0.0+bgb.1"
SOURCE_URL = (
    "https://files.pythonhosted.org/packages/c0/1e/"
    "642208a685c5e96d38323f42c75d9b24f95e2d1b8390dd104e04a712f29e/"
    "rpi_ws281x-5.0.0.tar.gz"
)
SOURCE_SHA256 = "00ce6db771436b778d0930245cf8ea2aae11008cc5fd67d57789c5422af3ee55"
OLD_ENTRY = """    {
        .hwver  = 0x9020e0,
        .type = RPI_HWVER_TYPE_PI2,
        .periph_base = PERIPH_BASE_RPI2,
        .videocore_base = VIDEOCORE_BASE_RPI2,
        .desc = "Model 3 A+",
    }"""


def unpack_source(data: bytes, directory: Path) -> Path:
    if hashlib.sha256(data).hexdigest() != SOURCE_SHA256:
        raise RuntimeError("LED driver source SHA256 mismatch; nothing installed")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        archive.extractall(directory, filter="data")
    return directory / "rpi_ws281x-5.0.0"


def patch_source(source: Path) -> None:
    hardware = source / "lib/rpihw.c"
    text = hardware.read_text()
    setup = source / "setup.py"
    metadata = setup.read_text()
    old_version = "version           = '5.0.0'"
    if (
        text.count(OLD_ENTRY) != 1
        or "0x9020e1" in text
        or metadata.count(old_version) != 1
    ):
        raise RuntimeError("Unexpected LED driver source; refusing to patch")
    # Exact upstream addition: preserve every existing revision and its mapping.
    addition = OLD_ENTRY.replace("0x9020e0", "0x9020e1")
    hardware.write_text(text.replace(OLD_ENTRY, OLD_ENTRY + ",\n" + addition))
    setup.write_text(metadata.replace(old_version, f"version           = '{VERSION}'"))


def verify_board() -> None:
    # This exported C function only reads the board revision/table. It does not
    # allocate a strip, register exit cleanup, open GPIO or emit LED data.
    import _rpi_ws281x

    native = ctypes.CDLL(_rpi_ws281x.__file__)
    detect = native.rpi_hw_detect
    detect.argtypes = []
    detect.restype = ctypes.c_void_p
    if not detect():
        raise RuntimeError("Installed LED driver does not recognize this Pi revision")
    print("LED driver recognizes this Pi revision.", flush=True)


def install() -> None:
    try:
        current = version("rpi-ws281x")
    except PackageNotFoundError:
        current = None
    if current != VERSION:
        print("Installing LED driver with Pi 3A+ revision support.", flush=True)
        with tempfile.TemporaryDirectory(prefix="blooglyblob-led-") as temporary:
            with urllib.request.urlopen(SOURCE_URL, timeout=60) as response:
                data = response.read(5 * 1024 * 1024 + 1)
            source = unpack_source(data, Path(temporary))
            patch_source(source)
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--no-deps", str(source)],
                check=True,
            )
    verify_board()


if __name__ == "__main__":
    install()
