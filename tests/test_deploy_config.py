"""Fresh settings publish privately; repeat installation never replaces them."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from scripts.deploy_config import ensure_runtime_config


@pytest.fixture
def inputs(tmp_path):
    destination = tmp_path / "config" / "app.env"
    upload = tmp_path / "upload.env"
    upload.write_text("OPENAI_API_KEY=fresh\nFUTURE=${LITERAL}\n")
    return destination, upload


def test_fresh_private_publication_and_repeat(inputs):
    destination, upload = inputs
    values = ensure_runtime_config(destination, upload)
    assert values == {"OPENAI_API_KEY": "fresh", "FUTURE": "${LITERAL}"}
    assert destination.stat().st_mode & 0o777 == 0o600
    content = destination.read_bytes()
    assert ensure_runtime_config(destination) == values
    assert destination.read_bytes() == content
    assert list(destination.parent.iterdir()) == [destination]


def test_existing_wins_byte_unchanged_and_repairs_permissions(inputs):
    destination, upload = inputs
    destination.parent.mkdir()
    destination.write_text("# preserved comment\nOPENAI_API_KEY=authoritative\n")
    destination.chmod(0o644)
    original = destination.read_bytes()
    values = ensure_runtime_config(destination, upload)
    assert values["OPENAI_API_KEY"] == "authoritative"
    assert destination.read_bytes() == original
    assert destination.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("existing", [True, False])
def test_invalid_configuration_does_not_publish(inputs, existing):
    destination, upload = inputs
    destination.parent.mkdir()
    path = destination if existing else upload
    path.write_text("PRIVATE=do-not-leak\n")
    with pytest.raises(ValueError, match="OPENAI_API_KEY") as error:
        ensure_runtime_config(destination, upload)
    assert "do-not-leak" not in str(error.value)
    assert path.read_text() == "PRIVATE=do-not-leak\n"
    assert destination.exists() is existing
    assert not list(destination.parent.glob(".app-env-*"))


@pytest.mark.parametrize("valid", [True, False])
def test_destination_race_never_overwrites(inputs, monkeypatch, valid):
    destination, upload = inputs
    content = "OPENAI_API_KEY=race-winner\n" if valid else "INVALID=keep-private\n"

    def raced(source, target):
        target.write_text(content)
        raise FileExistsError

    monkeypatch.setattr(os, "link", raced)
    if valid:
        assert (
            ensure_runtime_config(destination, upload)["OPENAI_API_KEY"]
            == "race-winner"
        )
    else:
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            ensure_runtime_config(destination, upload)
    assert destination.read_text() == content
    assert list(destination.parent.iterdir()) == [destination]


@pytest.mark.parametrize("boundary", ["write", "publish"])
def test_interruption_removes_candidate_and_keeps_source(inputs, monkeypatch, boundary):
    destination, upload = inputs
    original = upload.read_bytes()

    def fail(*args):
        raise OSError("interrupted")

    monkeypatch.setattr(os, "fsync" if boundary == "write" else "link", fail)
    with pytest.raises(OSError, match="interrupted"):
        ensure_runtime_config(destination, upload)
    assert list(destination.parent.iterdir()) == []
    assert upload.read_bytes() == original


def test_candidate_owner_and_permissions_before_first_write(inputs, monkeypatch):
    destination, upload = inputs
    original_fdopen = os.fdopen
    seen = []

    class CheckedStream:
        def __init__(self, fd, mode):
            self.stream = original_fdopen(fd, mode)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.stream.close()

        def fileno(self):
            return self.stream.fileno()

        def write(self, value):
            info = os.fstat(self.fileno())
            assert info.st_mode & 0o777 == 0o600
            assert (info.st_uid, info.st_gid) == (os.getuid(), os.getgid())
            seen.append(True)
            return self.stream.write(value)

        def flush(self):
            self.stream.flush()

    monkeypatch.setattr(os, "fdopen", CheckedStream)
    ensure_runtime_config(destination, upload, owner=(os.getuid(), os.getgid()))
    assert seen == [True]


def test_missing_upload_cannot_create_settings(inputs):
    destination, _ = inputs
    with pytest.raises(ValueError, match="Missing app.env"):
        ensure_runtime_config(destination)
    assert not destination.exists()


def test_unreadable_config_error_is_private(inputs):
    destination, upload = inputs
    upload.write_bytes(b"OPENAI_API_KEY=secret\xff")
    with pytest.raises(ValueError) as error:
        ensure_runtime_config(destination, upload)
    assert "secret" not in str(error.value)
    assert not destination.exists()


def test_standalone_staged_helpers_need_only_stdlib(tmp_path):
    for name in ("device_install.py", "deploy_config.py"):
        shutil.copy(
            Path(__file__).resolve().parents[1] / "scripts" / name, tmp_path / name
        )
    result = subprocess.run(
        [sys.executable, "-S", "-c", "import device_install, deploy_config"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
