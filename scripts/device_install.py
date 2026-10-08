#!/usr/bin/env python3
"""Pi-side installer and owned service controls; invoked through scripts/deploy.py."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
from typing import TYPE_CHECKING
import urllib.request

if TYPE_CHECKING or __package__:
    from .deploy_config import read_env, ensure_runtime_config
    from .wifi_persistence import configure as configure_wifi
else:
    from deploy_config import read_env, ensure_runtime_config
    from wifi_persistence import configure as configure_wifi

APP = Path("/opt/blooglyblob/app")
VENV = Path("/opt/blooglyblob/venv")
CONFIG = Path("/etc/blooglyblob")
STATE = Path("/var/lib/blooglyblob")
SYSTEMD = Path("/etc/systemd/system")
LOCK = Path("/run/lock/blooglyblob.lock")
GPIO_BLACKLIST = Path("/etc/modprobe.d/blooglyblob-audio.conf")
MODULES = Path("/proc/modules")
GPIO_BLACKLIST_CONTENT = "# GPIO18 PWM LEDs require onboard analogue audio disabled.\nblacklist snd_bcm2835\n"
SERVICES = ("blooglyblob.service",)
# Shared with the application and systemd's RestartPreventExitStatus. Keep this
# bootstrap helper stdlib-only so it can run before runtime dependencies exist.
OWNERSHIP_UNCERTAIN_EXIT = 73
PACKAGES = (
    "ca-certificates",
    "python3-venv",
    "python3-dev",
    "python3-yaml",
    "build-essential",
    "portaudio19-dev",
    "alsa-utils",
    "libasound2-dev",
    "libsndfile1",
)
# Upstream v79: https://github.com/joan2937/pigpio/releases/tag/v79
PIGPIO_COMMIT = "c33738a320a3e28824af7807edafda440952c05d"
PIGPIOD = Path("/usr/local/bin/pigpiod")
OWNED_DIRS = (
    "blooglyblob",
    "tool_configs",
    "sounds",
    "songs",
    "requirements",
    "scripts",
    "systemd",
    "LICENSES",
)
ROOT_FILES = ("pyproject.toml", "README.md", "LICENSE", "LICENSING.md")
DIAGNOSTICS = {
    "run": "blooglyblob",
    "servo-fit": "blooglyblob.hardware.servo_fit",
    "test-neopixels": "blooglyblob.hardware.test_neopixels",
}


def run(command, **kwargs):
    return subprocess.run([str(item) for item in command], check=True, **kwargs)


@contextmanager
def installation_lock():
    with LOCK.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError(
                "Another installation or hardware diagnostic owns the lock; wait for it to finish"
            ) from None
        yield


def validate_platform():
    release = read_env(Path("/etc/os-release"))
    model = Path("/proc/device-tree/model").read_text().strip("\0")
    if platform.machine() not in ("aarch64", "arm64") or not model.startswith(
        "Raspberry Pi 3 Model"
    ):
        raise RuntimeError("Use the documented Raspberry Pi 3 / 64-bit image")
    if release.get("VERSION_CODENAME") != "trixie" or sys.version_info[:2] != (3, 13):
        raise RuntimeError("Use Raspberry Pi OS Lite Trixie with Python 3.13")


def configure_gpio(mode):
    """Keep GPIO18 PWM LEDs separate from the onboard analogue audio driver."""
    if mode == "provision":
        GPIO_BLACKLIST.write_text(GPIO_BLACKLIST_CONTENT)
    elif (
        not GPIO_BLACKLIST.is_file()
        or GPIO_BLACKLIST.read_text() != GPIO_BLACKLIST_CONTENT
    ):
        raise RuntimeError(
            "GPIO audio prerequisite needs repair: run make pi-provision"
        )
    if any(
        line.startswith("snd_bcm2835 ") for line in MODULES.read_text().splitlines()
    ):
        raise RuntimeError(
            "Onboard audio is loaded and conflicts with GPIO18 LEDs. "
            "Reboot the Pi, then rerun make pi-provision; no application files were changed"
        )


def missing_packages():
    missing = []
    for package in PACKAGES:
        result = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", package],
            text=True,
            capture_output=True,
        )
        if result.returncode or result.stdout.strip() != "install ok installed":
            missing.append(package)
    return missing


def pigpio_installed():
    if not PIGPIOD.is_file():
        return False
    result = subprocess.run([str(PIGPIOD), "-v"], text=True, capture_output=True)
    return result.returncode == 0 and result.stdout.strip() == "79"


def extract(archive: Path, destination: Path):
    """Only regular files/directories; reject links and path traversal."""
    with tarfile.open(archive) as source:
        members = source.getmembers()
        for member in members:
            path = Path(member.name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or not (member.isfile() or member.isdir())
            ):
                raise RuntimeError("Unsafe archive member")
        source.extractall(destination, members=members, filter="data")


def install_pigpio():
    if pigpio_installed():
        return
    with tempfile.TemporaryDirectory(prefix="blooglyblob-pigpio-") as temporary:
        directory = Path(temporary)
        archive = directory / "pigpio.tar.gz"
        with urllib.request.urlopen(
            f"https://github.com/joan2937/pigpio/archive/{PIGPIO_COMMIT}.tar.gz",
            timeout=30,
        ) as response:
            with archive.open("wb") as output:
                shutil.copyfileobj(response, output)
        extract(archive, directory)
        source = directory / f"pigpio-{PIGPIO_COMMIT}"
        # Limit parallel compilation on the 512 MB reference board.
        run(["make", "-j1", "pigpiod"], cwd=source)
        # Upstream `make install` also runs global setup.py (distutils), which
        # is unsuitable on Python 3.13. Install only the daemon and its library;
        # the Python client is installed into our venv from requirements/hardware.txt.
        run(["install", "-d", "/usr/local/bin", "/usr/local/lib"])
        run(
            [
                "install",
                "-m",
                "0755",
                source / "libpigpio.so.1",
                "/usr/local/lib/libpigpio.so.1",
            ]
        )
        run(["install", "-m", "0755", source / "pigpiod", PIGPIOD])
        run(["ldconfig"])
    if not pigpio_installed():
        raise RuntimeError("pigpio v79 installation did not verify")


def create_state():
    # Existing directories, files, ownership and custom paths remain intact.
    if not STATE.exists():
        STATE.mkdir(parents=True, mode=0o700)
        os.chown(STATE, 0, 0)
    for component in ("brain", "device"):
        destination = STATE / component
        if not destination.exists():
            destination.mkdir(parents=True, mode=0o700)
            os.chown(destination, 0, 0)


def unit_property(name, property_name):
    try:
        result = run(
            ["systemctl", "show", name, "--property=" + property_name, "--value"],
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as error:
        # Some manager versions return 1 for a missing unit while still giving
        # its requested default properties. Only accept those exact defaults.
        value = (error.stdout or "").strip()
        expected = {"LoadState": "not-found", "ActiveState": "inactive"}
        if error.returncode == 1 and value == expected.get(property_name):
            return value
        raise RuntimeError(f"Cannot inspect {property_name} for {name}") from None


def stop_confirmed(names):
    if not names:
        return
    run(["systemctl", "stop", *names])
    for name in names:
        state = unit_property(name, "ActiveState")
        if state not in {"inactive", "failed"}:
            raise RuntimeError(f"Service release unconfirmed: {name}")


def payload_paths(source):
    return [path for path in source.rglob("*") if path.is_file()]


def validate_application_paths(source, values):
    """Reject destination links/collisions while the existing app still runs."""
    paths = payload_paths(source)
    for path in paths:
        relative = path.relative_to(source)
        if (
            relative.parts[0] not in OWNED_DIRS
            and relative.as_posix() not in ROOT_FILES
        ):
            raise RuntimeError(f"Unexpected runtime payload: {relative}")
    for relative in (path.relative_to(source) for path in paths):
        destination = APP / relative
        for path in (destination, *destination.parents):
            if path.is_symlink():
                raise RuntimeError(f"Runtime destination is a symlink: {relative}")
            if path == APP:
                break
    # Preserve custom state in place, rejecting paths that are managed software.
    managed = {APP / path.relative_to(source) for path in paths}
    for key in ("SERVO_CALIBRATION_FILE", "BLOOGLYBLOB_STATE_DIR"):
        if key in values and Path(values[key]) in managed:
            raise ValueError(f"Conflicting {key}; selected path is managed software")


def replace_application(source: Path):
    APP.mkdir(parents=True, exist_ok=True)
    # Copy the allowlisted payload file by file. A recursive directory deletion
    # would erase selected calibration, timer or media paths inside the app.
    for path in payload_paths(source):
        destination = APP / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    if not (VENV / "bin/python").exists():
        run([sys.executable, "-m", "venv", VENV])
    run([VENV / "bin/python", APP / "scripts/install_led_driver.py"])
    constraints = APP / "requirements/pi-py313.txt"
    arguments = ["-c", str(constraints)] if constraints.exists() else []
    run(
        [
            VENV / "bin/python",
            "-m",
            "pip",
            "install",
            *arguments,
            "-r",
            APP / "requirements/runtime.txt",
            "-r",
            APP / "requirements/hardware.txt",
        ]
    )
    # A reused source tree can retain build/lib modules from the old package.
    # Build only the fresh payload so setuptools cannot rebundle that residue.
    run([VENV / "bin/python", "-m", "pip", "install", "--no-deps", source])
    run([VENV / "bin/python", "-m", "pip", "check"])


def install_units(source):
    for name in (*SERVICES, "pigpiod.service"):
        temporary = SYSTEMD / (name + ".tmp")
        temporary.write_bytes((source / "systemd" / name).read_bytes())
        temporary.chmod(0o644)
        temporary.replace(SYSTEMD / name)
    run(["systemctl", "daemon-reload"])
    run(["systemctl", "enable", "pigpiod.service", *SERVICES])


def health():
    # Type=notify makes the preceding blocking systemctl start wait for local
    # readiness; no extra process/listener or paid conversation is needed.
    for service in SERVICES:
        run(["systemctl", "is-active", service])


def runtime_environment():
    environment = os.environ.copy()
    environment["BLOOGLYBLOB_ENV_FILE"] = str(CONFIG / "app.env")
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def install(mode: str, stage: Path):
    validate_platform()
    if mode == "update":
        if (
            missing_packages()
            or not pigpio_installed()
            or not (VENV / "bin/python").exists()
        ):
            raise RuntimeError(
                "System prerequisites need repair: run make pi-provision before pi-update"
            )
    configure_gpio(mode)
    # Refresh metadata after interrupted installs without changing process state.
    run(["systemctl", "daemon-reload"])
    with tempfile.TemporaryDirectory(prefix="blooglyblob-install-") as temporary:
        source = Path(temporary)
        extract(stage / "app.tar.gz", source)
        for name in (
            "pyproject.toml",
            "LICENSE",
            "LICENSING.md",
            "LICENSES/CC0-1.0.txt",
            "blooglyblob/__main__.py",
            "blooglyblob/application.py",
            "blooglyblob/ai/persona.json",
            "blooglyblob/ai/voice_profile.json",
            "requirements/runtime.txt",
            "requirements/hardware.txt",
            "scripts/audio_check.py",
            "scripts/install_led_driver.py",
            "scripts/wifi_persistence.py",
            "systemd/blooglyblob.service",
            "systemd/pigpiod.service",
        ):
            if not (source / name).is_file():
                raise RuntimeError(f"Incomplete runtime payload: {name}")
        values = ensure_runtime_config(
            CONFIG / "app.env",
            stage / "app.env" if mode == "provision" else None,
            owner=(0, 0),
        )
        validate_application_paths(source, values)
        if mode == "provision":
            run(["apt-get", "-o", "APT::Update::Error-Mode=any", "update"])
            run(["apt-get", "install", "-y", "--no-install-recommends", *PACKAGES])
            install_pigpio()
            configure_wifi()
        installed = [
            name
            for name in SERVICES
            if unit_property(name, "LoadState") != "not-found"
            or unit_property(name, "ActiveState") not in {"inactive", "failed"}
        ]
        stop_confirmed(installed)
        if mode == "provision" and (SYSTEMD / "pigpiod.service").exists():
            stop_confirmed(["pigpiod.service"])
        create_state()
        replace_application(source)
        install_units(source)
        run(["systemctl", "start", "pigpiod.service"])
        run(["systemctl", "reset-failed", *SERVICES])
        run(["systemctl", "start", *SERVICES])
        health()
    print("Installation complete; the application reached local readiness.")


def release_child(child):
    """Only a completed wait proves that a diagnostic no longer owns devices."""
    if child.poll() is not None:
        return child.wait()
    child.terminate()
    try:
        return child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        try:
            return child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                "Diagnostic release unconfirmed; application remains stopped"
            ) from None


def diagnostic(command):
    active = unit_property(SERVICES[0], "ActiveState") == "active"
    stop_confirmed(list(SERVICES))
    child = None
    confirmed = True
    code = None
    try:
        args = (
            ["-m", DIAGNOSTICS[command]]
            if command in DIAGNOSTICS
            else [str(APP / "scripts/audio_check.py"), command]
        )
        child = subprocess.Popen(
            [str(VENV / "bin/python"), *args], cwd=APP, env=runtime_environment()
        )
        confirmed = False
        code = child.wait()
        confirmed = True
        if code:
            raise subprocess.CalledProcessError(code, args)
    finally:
        # A second signal must not bypass the finite terminate/kill/wait path.
        handlers = {
            sig: signal.signal(sig, signal.SIG_IGN)
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
        }
        try:
            if child is not None and not confirmed:
                code = release_child(child)
                confirmed = True
            if (
                command != "servo-fit"
                and active
                and confirmed
                and code != OWNERSHIP_UNCERTAIN_EXIT
            ):
                run(["systemctl", "start", *SERVICES])
        finally:
            for sig, handler in handlers.items():
                signal.signal(sig, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "provision",
            "update",
            "start",
            "stop",
            "restart",
            *DIAGNOSTICS,
            "check-audio",
            "test-audio",
            "test-mic",
        ),
    )
    parser.add_argument("--stage", type=Path)
    args = parser.parse_args(argv)
    if os.geteuid() != 0:
        parser.error("Run this helper through make pi-* (sudo is required)")

    # Ensure interrupted diagnostics restore their previous service state.
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    try:
        with installation_lock():
            if args.command in ("provision", "update"):
                if args.stage is None:
                    raise RuntimeError(
                        "Installation requires a temporary upload directory"
                    )
                install(args.command, args.stage)
            elif args.command in ("start", "stop", "restart"):
                run(["systemctl", args.command, *SERVICES])
            else:
                diagnostic(args.command)
        return 0
    except (
        RuntimeError,
        ValueError,
        OSError,
        subprocess.CalledProcessError,
        KeyboardInterrupt,
    ) as exc:
        print(f"Failed: {exc or 'interrupted'}", file=sys.stderr)
        subprocess.run(["systemctl", "status", *SERVICES, "--no-pager", "--lines=0"])
        print(
            "No automatic rollback. Inspect make pi-logs, repair the failed step, and rerun "
            "make pi-provision or pi-update. Settings and state are preserved.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
