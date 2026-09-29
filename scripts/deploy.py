#!/usr/bin/env python3
"""Host-side Pi operations. Requires Python 3.10+, OpenSSH ssh/scp, and Make."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__:
    from .deploy_config import read_env
else:
    from deploy_config import read_env

ROOT = Path(__file__).resolve().parent.parent
KEYS = ("PI_HOST", "PI_USER", "BLOOGLYBLOB_ENV_FILE")
HELPERS = (
    "deploy_config.py",
    "device_install.py",
    "audio_check.py",
    "install_led_driver.py",
)
UNITS = ("blooglyblob.service", "pigpiod.service")
MEDIA = (
    "songs/dance_song.wav",
    "songs/dance_song_beats.json",
    "songs/dance_song_lights.json",
    "sounds/alert_16k.wav",
    "sounds/search_16k.wav",
)
DIAGNOSTICS = (
    "run",
    "servo-fit",
    "check-audio",
    "test-audio",
    "test-mic",
    "test-neopixels",
)
REMOTE_CHECK = """import json, pathlib, platform, os, socket
release = pathlib.Path('/etc/os-release').read_text()
model = pathlib.Path('/proc/device-tree/model')
print(json.dumps(dict(hostname=socket.gethostname(), user=__import__('getpass').getuser(),
    architecture=platform.machine(), python=platform.python_version(), os=release,
    model=model.read_text().strip('\\0') if model.exists() else 'unknown')))
"""


def settings(root: Path = ROOT, environ=None) -> dict[str, str]:
    result = read_env(root / ".env") if (root / ".env").exists() else {}
    environment = os.environ if environ is None else environ
    result.update({key: environment[key] for key in KEYS if key in environment})
    return result


def target(config: dict[str, str]) -> str:
    """Use an explicit user, or an SSH alias with a configured HostName/User."""
    host = config.get("PI_HOST", "").strip()
    user = config.get("PI_USER", "").strip()
    if not host or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]*", host):
        raise ValueError("Set PI_HOST to a hostname, IP address, or SSH alias")
    if user:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", user):
            raise ValueError("PI_USER must be an SSH username")
        return f"{user}@{host}"
    resolved = subprocess.run(
        ["ssh", "-G", host], check=True, text=True, capture_output=True
    )
    fields = dict(
        line.split(None, 1) for line in resolved.stdout.splitlines() if " " in line
    )
    # OpenSSH's default local username is not evidence of a chosen Pi account.
    # A HostName mapping proves that this is a configured alias; let OpenSSH
    # apply its User (including one equal to the local username) and other rules.
    if fields.get("hostname") == host or not fields.get("user"):
        raise ValueError(
            "Set PI_USER, or use an SSH alias with HostName and User configured"
        )
    return host


def ssh(destination: str, command: list[str], *, tty=False, capture=False):
    argv = ["ssh", "-o", "ConnectTimeout=10"]
    if tty:
        argv.append("-tt")
    argv += [destination, shlex.join(command)]
    return subprocess.run(argv, check=True, text=True, capture_output=capture)


def check(destination: str):
    import json

    report = json.loads(
        ssh(destination, ["python3", "-c", REMOTE_CHECK], capture=True).stdout
    )
    print(
        f"Requested: {destination}; authenticated: {report['user']}@{report['hostname']}"
    )
    print(f"{report['model']}; {report['architecture']}; Python {report['python']}")
    print(report["os"].strip())
    if report["architecture"] not in ("aarch64", "arm64"):
        raise ValueError("Use Raspberry Pi OS Lite 64-bit, not a 32-bit image")
    if not report["model"].startswith("Raspberry Pi 3 Model"):
        raise ValueError(
            "This deployment profile currently supports Raspberry Pi 3 only"
        )
    if "VERSION_CODENAME=trixie" not in report["os"] or not report["python"].startswith(
        "3.13."
    ):
        raise ValueError(
            "Use the documented Raspberry Pi OS Lite Trixie / Python 3.13 image"
        )


def payload_files(root: Path = ROOT) -> list[Path]:
    """Explicit runtime allowlist. Never recursively copy a checkout."""
    names = [
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "LICENSING.md",
        "LICENSES/CC0-1.0.txt",
        "blooglyblob/ai/persona.json",
        "blooglyblob/ai/voice_profile.json",
    ]
    for package in (
        "blooglyblob",
        "blooglyblob/ai",
        "blooglyblob/audio",
        "blooglyblob/hardware",
        "blooglyblob/tools",
        "tool_configs",
        "sounds",
        "songs",
    ):
        names.extend(
            str(path.relative_to(root)) for path in (root / package).glob("*.py")
        )
    names.extend(
        str(path.relative_to(root)) for path in (root / "tool_configs").glob("*.json")
    )
    names.extend(
        str(path.relative_to(root)) for path in (root / "requirements").glob("*.txt")
    )
    names.extend(MEDIA)
    names.extend("scripts/" + name for name in HELPERS)
    names.extend("systemd/" + name for name in UNITS)
    files = []
    for name in sorted(set(names)):
        path = root / name
        if path.is_symlink() or root.resolve() not in path.resolve().parents:
            raise ValueError(
                f"Payload path must be a regular file inside the repository: {name}"
            )
        if not path.is_file():
            raise ValueError(f"Required runtime file missing: {name}")
        files.append(path)
    return files


def create_payload(output: Path, root: Path = ROOT):
    with tarfile.open(output, "w:gz") as archive:
        for path in payload_files(root):
            archive.add(path, arcname=str(path.relative_to(root)), recursive=False)


def install(destination: str, mode: str, config: dict[str, str]):
    check(destination)
    # Input files are optional on repairs: existing remote configuration wins.
    inputs = {}
    if mode == "provision":
        for key, name in (("BLOOGLYBLOB_ENV_FILE", "app.env"),):
            if config.get(key):
                path = (ROOT / Path(config[key]).expanduser()).resolve()
                read_env(path)  # syntax only; never print credentials
                inputs[name] = path
    with tempfile.TemporaryDirectory(prefix="blooglyblob-payload-") as temporary:
        archive = Path(temporary) / "app.tar.gz"
        create_payload(archive)
        stage = ssh(
            destination,
            ["mktemp", "-d", "/tmp/blooglyblob-deploy-XXXXXXXX"],
            capture=True,
        ).stdout.strip()
        if not re.fullmatch(r"/tmp/blooglyblob-deploy-[A-Za-z0-9]+", stage):
            raise ValueError("Unexpected remote staging path")
        try:
            transfers = [
                (archive, "app.tar.gz"),
                (ROOT / "scripts/device_install.py", "device_install.py"),
                (ROOT / "scripts/deploy_config.py", "deploy_config.py"),
                *[(p, n) for n, p in inputs.items()],
            ]
            for source, name in transfers:
                user, separator, host = destination.rpartition("@")
                address = host if separator else destination
                scp_host = f"[{address}]" if ":" in address else address
                scp_target = f"{user}@{scp_host}" if separator else scp_host
                subprocess.run(
                    ["scp", "-q", str(source), f"{scp_target}:{stage}/{name}"],
                    check=True,
                )
            # A single TTY/sudo session supports a normal interactive sudo password.
            # Never store a password or depend on sudo credentials from another SSH session.
            ssh(
                destination,
                [
                    "sudo",
                    "python3",
                    "-B",
                    f"{stage}/device_install.py",
                    mode,
                    "--stage",
                    stage,
                ],
                tty=True,
            )
        finally:
            try:
                ssh(destination, ["rm", "-rf", "--", stage])
            except subprocess.CalledProcessError:
                print(
                    f"Could not remove temporary upload directory: {stage}",
                    file=sys.stderr,
                )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=(
            "check",
            "payload",
            "provision",
            "update",
            "ssh",
            "logs",
            "status",
            "start",
            "stop",
            "restart",
            *DIAGNOSTICS,
        ),
    )
    args = parser.parse_args(argv)
    try:
        if args.command == "payload":
            for path in payload_files():
                print(path.relative_to(ROOT))
            return 0
        if not shutil.which("ssh") or not shutil.which("scp"):
            raise ValueError(
                "Install OpenSSH ssh/scp on this computer before deploying"
            )
        config = settings()
        destination = target(config)
        if args.command == "check":
            check(destination)
        elif args.command in ("provision", "update"):
            install(destination, args.command, config)
        elif args.command == "ssh":
            subprocess.run(["ssh", destination], check=True)
        elif args.command == "logs":
            ssh(
                destination,
                ["sudo", "journalctl", "-u", "blooglyblob", "-n", "100", "-f"],
                tty=True,
            )
        elif args.command == "status":
            ssh(destination, ["systemctl", "status", "blooglyblob", "--no-pager"])
        else:
            ssh(
                destination,
                [
                    "sudo",
                    "python3",
                    "/opt/blooglyblob/app/scripts/device_install.py",
                    args.command,
                ],
                tty=True,
            )
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Deployment failed: {exc}", file=sys.stderr)
        print(
            "Check PI_HOST/PI_USER, SSH keys/known hosts, and the step above. "
            "Use make pi-status / pi-logs; repair the cause and rerun. No rollback was performed.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
