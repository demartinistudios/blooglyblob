"""Opt-in, check-only Ruff hook using index contents in a temporary directory."""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


WRAPPER = """#!/bin/sh
# Blooglyblob optional staged Python checks; installed by scripts/pre_commit.py.
set -eu
cd "$(git rev-parse --show-toplevel)"
python="${DEV_PYTHON:-.venv/bin/python}"
if ! command -v "$python" >/dev/null 2>&1; then
    echo "Pre-commit: run make dev-setup or set DEV_PYTHON to a development Python." >&2
    exit 1
fi
exec "$python" scripts/pre_commit.py check
"""


def git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True
    ).stdout


def install(root: Path) -> int:
    configured = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"], cwd=root, capture_output=True
    )
    if configured.returncode == 0:
        raise RuntimeError(
            "core.hooksPath is configured; installation left it unchanged. "
            "Add a call to scripts/pre_commit.py check from your existing hook "
            "using the development Python, or deliberately remove that configuration "
            "before installing."
        )
    if configured.returncode != 1:
        raise RuntimeError("Could not inspect core.hooksPath; no hook was installed.")
    hook = (
        root
        / os.fsdecode(git(root, "rev-parse", "--git-path", "hooks/pre-commit")).strip()
    )
    if hook.is_symlink() or hook.exists():
        if (
            hook.is_symlink()
            or not hook.is_file()
            or hook.read_bytes() != WRAPPER.encode()
        ):
            raise RuntimeError(
                f"Existing hook at {hook} was preserved. Add a call to "
                "scripts/pre_commit.py check using the development Python yourself, "
                "or move the existing hook aside before installing."
            )
    else:
        hook.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation never overwrites a hook installed concurrently.
        with hook.open("x") as stream:
            stream.write(WRAPPER)
    hook.chmod(hook.stat().st_mode | 0o111)
    print(f"Installed optional pre-commit checks: {hook}")
    return 0


def check(root: Path) -> int:
    names = git(root, "diff", "--cached", "--name-only", "--diff-filter=ACMRTU", "-z")
    paths = [
        os.fsdecode(name)
        for name in names.split(b"\0")
        if name.endswith(b".py")
        and name.split(b"/", 1)[0] in {b"blooglyblob", b"scripts", b"tests"}
    ]
    if not paths:
        return 0

    python = os.environ.get("DEV_PYTHON") or str(root / ".venv/bin/python")
    # Resolve relative overrides before changing to the temporary snapshot.
    executable = shutil.which(python)
    if executable is None:
        raise RuntimeError(
            "Development Python is missing; run make dev-setup or set DEV_PYTHON."
        )
    executable = os.path.abspath(executable)
    available = subprocess.run(
        [executable, "-m", "ruff", "--version"], cwd=root, capture_output=True
    )
    if available.returncode:
        raise RuntimeError(
            "Ruff is unavailable in the development Python; run make dev-setup "
            "or set DEV_PYTHON to an environment with requirements-dev.txt installed."
        )

    with tempfile.TemporaryDirectory(prefix="blooglyblob-pre-commit-") as directory:
        snapshot = Path(directory)
        # Read the index directly: never stash, checkout, fix, stage or refresh it.
        for name in ["pyproject.toml", *paths]:
            target = snapshot / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git(root, "show", f":{name}"))

        failed = False
        for command in [("format", "--check"), ("check", "--no-fix")]:
            print(f"Pre-commit: Ruff {' '.join(command)} on staged Python", flush=True)
            result = subprocess.run(
                [
                    executable,
                    "-m",
                    "ruff",
                    *command,
                    "--no-cache",
                    "--force-exclude",
                    "--config",
                    str(snapshot / "pyproject.toml"),
                    "--",
                    *paths,
                ],
                cwd=snapshot,
            )
            failed |= result.returncode != 0
    if failed:
        print(
            "Pre-commit failed. Fix the reported files, then stage the intended "
            "changes and retry. The index and working tree were left unchanged.",
            file=sys.stderr,
        )
    return int(failed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=("check", "install"), default="check", nargs="?"
    )
    args = parser.parse_args()
    try:
        root = Path(
            os.fsdecode(git(Path.cwd(), "rev-parse", "--show-toplevel")).strip()
        )
        return install(root) if args.action == "install" else check(root)
    except subprocess.CalledProcessError as error:
        print(
            "Pre-commit: could not read Git state or staged configuration/content: "
            + os.fsdecode(error.stderr).strip(),
            file=sys.stderr,
        )
    except (OSError, RuntimeError) as error:
        print(f"Pre-commit: {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
