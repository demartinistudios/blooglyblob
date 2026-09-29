"""Public snapshots exclude local state, secrets and private print metadata."""

import io
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from scripts.check_publication import check_repository


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repository(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def stage(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    subprocess.run(["git", "add", "-f", "--", name], cwd=root, check=True)


def project_xml(value):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "3D/3dmodel.model",
            '<model><metadata name="DesignerUserId">' + value + "</metadata></model>",
        )
    return buffer.getvalue()


def test_valid_public_tree_ignores_untracked_private_files(repository):
    stage(repository, "README.md", b"A community build. Contact builder@example.com")
    stage(repository, "hardware/cad/design-control/releases/R23-current.json", b"{}")
    stage(repository, "hardware/cad/design-control/releases/R28-current.json", b"{}")
    stage(repository, "hardware/cad/design-control/deliveries/current.json", b"{}")
    stage(repository, ".env.example", b"OPENAI_API_KEY=replace-me\n")
    stage(repository, "hardware/printing/current/project.3mf", project_xml(""))
    private = repository / "hardware/records/private.md"
    private.parent.mkdir(parents=True)
    private.write_text("Private local notes")
    assert check_repository(repository) == []


@pytest.mark.parametrize(
    "name",
    [
        "hardware/records/guide/current-review.json",
        "hardware/printing/operations/stock.json",
        "docs/plans/experiment.md",
        "docs/investigations/private.md",
        "hardware/.work/private.md",
        "hardware/build-guide/.guide-previous/index.html",
        "hardware/build-guide/.guide-stage-trial/index.html",
        "hardware/cad/design-control/deliveries/R23-cleanup-20260925.json",
        "hardware/rendering/r27-visible-meshes.json.gz",
        "hardware/rendering/r23-mesh-composition.json",
        "hardware/cad/design-control/releases/R28-straight-row-20260928.json",
        "config/app.env",
        ".env.production",
        ".ssh/id_ed25519",
        ".codex/config.toml",
        ".compound-engineering/config.local.yaml",
    ],
)
def test_force_added_ignored_paths_are_rejected(repository, name):
    stage(repository, ".gitignore", b"*\n")
    stage(repository, name, b"local state")
    failures = check_repository(repository)
    assert any(name in failure for failure in failures)


def test_scans_staged_content_even_when_worktree_was_sanitized(repository):
    secret = b"sk-" + b"proj-" + b"aB12" * 16
    stage(repository, "settings.py", b"KEY=" + secret)
    (repository / "settings.py").write_text("KEY=placeholder")
    failures = check_repository(repository)
    assert any("settings.py" in failure for failure in failures)
    assert secret.decode() not in "\n".join(failures)


@pytest.mark.parametrize(
    "secret",
    [
        b"gh" + b"p_" + b"aB12" * 9,
        b"github_" + b"pat_" + b"aB12" * 20,
        b"-----BEGIN " + b"OPENSSH PRIVATE KEY-----",
    ],
)
def test_high_confidence_credentials_are_rejected(repository, secret):
    stage(repository, "settings.txt", secret)
    assert check_repository(repository)


def test_cli_never_prints_secret(repository):
    secret = "sk-" + "proj-" + "aB12" * 16
    stage(repository, "settings.txt", secret.encode())
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/check_publication.py"),
            "--root",
            str(repository),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "settings.txt" in result.stdout
    assert secret not in result.stdout + result.stderr


def test_print_project_metadata_is_rejected_without_printing_account(repository):
    account = "private-account-marker"
    stage(repository, "hardware/printing/current/project.3mf", project_xml(account))
    failures = check_repository(repository)
    assert any("3MF" in failure for failure in failures)
    assert account not in "\n".join(failures)


def test_malformed_print_project_fails_closed(repository):
    stage(repository, "hardware/printing/current/project.3mf", b"not a ZIP")
    assert check_repository(repository)


def test_symlink_cannot_publish_a_private_target(repository, tmp_path):
    target = tmp_path / "private-value"
    target.write_text("private marker")
    link = repository / "public-link"
    link.symlink_to(target)
    subprocess.run(["git", "add", "--", "public-link"], cwd=repository, check=True)
    failures = check_repository(repository)
    assert any("non-file" in failure for failure in failures)
    assert "private marker" not in "\n".join(failures)
