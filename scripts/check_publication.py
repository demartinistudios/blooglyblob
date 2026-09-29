"""Check the Git index's public boundary without exposing matched credentials.

This scans the staged Git index, including force-added ignored files. Stage the
intended changes first; unstaged edits and untracked files are not scanned.
It is a guard against common mistakes, not a complete privacy or secret audit.
The existing 3MF validator checks account metadata; native CAD is not sanitized.
"""

import argparse
import io
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from xml.parsers.expat import ExpatError
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PREFIXES = (
    "hardware/records/",
    "hardware/printing/operations/",
    "docs/plans/",
    "docs/investigations/",
    "hardware/.work/",
    "hardware/build-guide/dist/",
    "hardware/build-guide/.guide-previous/",
    "hardware/build-guide/.guide-stage-",
    "data/",
)
PRIVATE_FILES = {
    ".codex/config.toml",
    ".compound-engineering/config.local.yaml",
    "hardware/cad/design-control/deliveries/R23-cleanup-20260925.json",
    "hardware/rendering/r23-mesh-composition.json",
    *(
        f"hardware/cad/design-control/releases/{name}.json"
        for name in (
            "R24-base-simplification-20260926",
            "R25-jetpack-root-reinforcement-20260927",
            "R26-audio-tape-cradle-20260927",
            "R27-base-nut-slots-20260928",
            "R28-straight-row-20260928",
        )
    ),
    "hardware/cad/design-control/promotion-lock.json",
    "hardware/cad/design-control/publication-in-progress.json",
    *(
        f"hardware/rendering/r{revision}-visible-meshes.json.gz"
        for revision in range(23, 28)
    ),
}
PRIVATE_PARTS = {
    ".ssh",
    ".aws",
    ".venv",
    ".venv-beats",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
    ".envrc",
}
# Require credential-shaped tokens rather than assignments or documentation words.
SECRET_PATTERNS = (
    re.compile(rb"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    re.compile(rb"\bAKIA[0-9A-Z]{16}\b"),
)


def private_path(name):
    path = PurePosixPath(name)
    env_file = (
        path.name == ".env"
        or path.name.startswith(".env.")
        or path.name.endswith(".env")
    ) and not (path.name == ".env.example" or path.name.endswith(".env.example"))
    return (
        name.startswith(PRIVATE_PREFIXES)
        or name in PRIVATE_FILES
        or bool(set(path.parts) & PRIVATE_PARTS)
        or env_file
        or path.name.endswith((".log", ".publication-tmp"))
    )


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def check_repository(root):
    # Direct script invocation starts with scripts/ on sys.path, not the repo root.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from hardware.tools.printing.privacy import check_project

    failures = []
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        metadata, raw_name = entry.split(b"\t", 1)
        mode, object_id, stage = metadata.decode("ascii").split()
        name = raw_name.decode("utf-8", errors="replace")
        if private_path(name):
            failures.append(f"{name}: local-only path is tracked")
            continue
        if stage != "0" or mode not in {"100644", "100755"}:
            failures.append(f"{name}: unresolved or non-file index entry")
            continue
        data = git(root, "cat-file", "blob", object_id)
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            failures.append(f"{name}: credential-shaped content (value withheld)")
        if name.lower().endswith(".3mf"):
            try:
                check_project(io.BytesIO(data))
            except (ValueError, OSError, zipfile.BadZipFile, ExpatError, RuntimeError):
                # XML/ZIP errors can quote content. Only expose the file and category.
                failures.append(
                    f"{name}: 3MF account metadata or archive validation failed"
                )
    return failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=ROOT, help="Git checkout to inspect"
    )
    args = parser.parse_args()
    try:
        failures = check_repository(args.root)
    except (OSError, subprocess.CalledProcessError):
        print("Publication boundary: could not read the Git index or its blobs.")
        return 1
    if failures:
        print("Publication boundary: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Publication boundary: PASS (indexed files; not a complete privacy audit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
