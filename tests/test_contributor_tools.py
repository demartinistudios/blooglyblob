"""Offline check failure propagation and shared dependency-pin protection."""

import os
from pathlib import Path
import subprocess

import pytest

from scripts.update_dev_constraints import development_pins

ROOT = Path(__file__).resolve().parents[1]


def test_shared_pins_are_reused_and_conflicts_rejected():
    report = {
        "install": [
            {"metadata": {"name": "typing_extensions", "version": "4.16.0"}},
            {"metadata": {"name": "Dev.Tool", "version": "1.2"}},
        ]
    }
    assert (
        development_pins(report, {"typing-extensions": "4.16.0"}) == "dev-tool==1.2\n"
    )
    with pytest.raises(ValueError, match="typing-extensions"):
        development_pins(report, {"typing-extensions": "0"})


@pytest.mark.parametrize(
    "failure, expected",
    [
        ("scripts/check_publication.py", ["scripts/check_publication.py"]),
        (
            "-m ruff format --check blooglyblob scripts tests",
            [
                "scripts/check_publication.py",
                "-m ruff format --check blooglyblob scripts tests",
            ],
        ),
    ],
)
def test_full_check_stops_at_failure_without_installing_or_building(
    tmp_path, failure, expected
):
    log = tmp_path / "invocations"
    python = tmp_path / "python"
    python.write_text(
        '#!/bin/sh\nif [ "$1" = "-c" ]; then exit 0; fi\n'
        'echo "$*" >> "$CHECK_LOG"\n'
        'if [ "$*" = "$FAIL_COMMAND" ]; then exit 7; fi\nexit 0\n'
    )
    python.chmod(0o755)
    result = subprocess.run(
        ["make", "check", f"DEV_PYTHON={python}", f"HOST_PYTHON={python}"],
        cwd=ROOT,
        env={**os.environ, "CHECK_LOG": str(log), "FAIL_COMMAND": failure},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert log.read_text().splitlines() == expected


def test_missing_python_has_setup_guidance(tmp_path):
    result = subprocess.run(
        ["sh", str(ROOT / "scripts/check.sh")],
        env={**os.environ, "DEV_PYTHON": str(tmp_path / "missing")},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "make dev-setup" in result.stderr
