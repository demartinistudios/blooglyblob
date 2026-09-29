#!/usr/bin/env python3
"""Regenerate development-only pins with pip 25.3 in a disposable environment."""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import venv

ROOT = Path(__file__).resolve().parents[1]


def normalized(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def development_pins(report, shared):
    pins = {}
    for entry in report["install"]:
        metadata = entry["metadata"]
        name, version = normalized(metadata["name"]), metadata["version"]
        if name in shared:
            if shared[name] != version:
                raise ValueError(f"Resolution conflicts with shared constraint: {name}")
        else:
            pins[name] = version
    return "".join(f"{name}=={version}\n" for name, version in sorted(pins.items()))


def main():
    if sys.version_info[:2] not in ((3, 12), (3, 13)):
        raise SystemExit(
            "Use Python 3.12 or 3.13 to regenerate development constraints."
        )
    shared = {}
    for line in (ROOT / "requirements/pi-py313.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, version = line.strip().split("==")
            shared[normalized(name)] = version
    with tempfile.TemporaryDirectory(prefix="blooglyblob-dev-lock-") as directory:
        path = Path(directory)
        venv.create(path / "venv", with_pip=True)
        python = path / "venv/bin/python"
        subprocess.run([str(python), "-m", "pip", "install", "pip==25.3"], check=True)
        report = path / "resolution.json"
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--dry-run",
                "--ignore-installed",
                "--report",
                str(report),
                "-r",
                str(ROOT / "requirements-dev.txt"),
            ],
            check=True,
        )
        pins = development_pins(json.loads(report.read_text()), shared)
    output = ROOT / "requirements/dev.txt"
    output.write_text(
        "# Generated with pip 25.3; do not edit individual transitive pins.\n"
        "# Regenerate: python3.12 scripts/update_dev_constraints.py\n"
        "# Shared runtime pins remain in pi-py313.txt (included by requirements-dev.txt).\n"
        + pins
    )
    print(
        f"Wrote {output.relative_to(ROOT)}; validate Python 3.12/3.13 before adoption."
    )


if __name__ == "__main__":
    main()
