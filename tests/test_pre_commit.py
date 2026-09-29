"""Exercise the optional hook against disposable indexes and real Ruff checks."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


HOOK_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pre_commit.py"
CONFIG = """[tool.ruff]
target-version = "py312"
[tool.ruff.format]
exclude = ["blooglyblob/hardware/**"]
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F"]
"""


def git(repo, *args):
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True
    ).stdout


def write(repo, name, content):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Hook test")
    git(tmp_path, "config", "user.email", "hook@example.invalid")
    write(tmp_path, "pyproject.toml", CONFIG)
    write(tmp_path, "tests/example.py", "value = 1\n")
    git(tmp_path, "add", "pyproject.toml", "tests/example.py")
    git(tmp_path, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "baseline")
    return tmp_path


def run_hook(repo, action="check", **environment):
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT), action],
        cwd=repo,
        env={**os.environ, "DEV_PYTHON": sys.executable, **environment},
        capture_output=True,
        text=True,
    )


def state(repo):
    return (
        (repo / ".git/index").read_bytes(),
        {
            str(path.relative_to(repo)): path.read_bytes()
            for path in repo.rglob("*")
            if path.is_file() and ".git" not in path.relative_to(repo).parts
        },
    )


@pytest.mark.parametrize(
    ("staged", "working", "passes"),
    [
        ("value = 2\n", "value=missing\n", True),
        ("value=2\n", "value = 2\n", False),
        ("value = missing\n", "value = 2\n", False),
    ],
)
def test_checks_staged_content_without_changing_index_or_worktree(
    repo, staged, working, passes
):
    write(repo, "tests/example.py", staged)
    git(repo, "add", "tests/example.py")
    write(repo, "tests/example.py", working)
    before = state(repo)
    result = run_hook(repo)
    assert (result.returncode == 0) is passes, result.stdout + result.stderr
    assert "Pre-commit: Ruff" in result.stdout
    if not passes:
        assert "reformatted" in result.stdout or "F821" in result.stdout
    assert state(repo) == before


def test_uses_staged_configuration(repo):
    write(repo, "pyproject.toml", CONFIG + 'ignore = ["F821"]\n')
    write(repo, "tests/example.py", "value = missing\n")
    git(repo, "add", "pyproject.toml", "tests/example.py")
    write(repo, "pyproject.toml", CONFIG)
    result = run_hook(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_format_excludes_hardware_but_lint_still_checks_it(repo):
    write(repo, "blooglyblob/hardware/part.py", "value=1\n")
    git(repo, "add", "blooglyblob/hardware/part.py")
    assert run_hook(repo).returncode == 0
    write(repo, "blooglyblob/hardware/part.py", "value=missing\n")
    git(repo, "add", "blooglyblob/hardware/part.py")
    result = run_hook(repo)
    assert result.returncode != 0
    assert "F821" in result.stdout + result.stderr


def test_rename_with_spaces_checks_destination_and_ignores_unstaged_errors(repo):
    git(repo, "mv", "tests/example.py", "tests/new name.py")
    write(repo, "tests/new name.py", "value=missing\n")
    result = run_hook(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    git(repo, "add", "tests/new name.py")
    assert run_hook(repo).returncode != 0


def test_deletions_and_out_of_scope_files_need_no_tools(repo):
    git(repo, "rm", "tests/example.py")
    write(repo, "hardware/broken.py", "value=missing\n")
    git(repo, "add", "hardware/broken.py")
    result = run_hook(repo, DEV_PYTHON="/missing/python")
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_interpreter_has_setup_guidance(repo):
    write(repo, "tests/example.py", "value = 2\n")
    git(repo, "add", "tests/example.py")
    result = run_hook(repo, DEV_PYTHON="/missing/python")
    assert result.returncode != 0
    assert "make dev-setup" in result.stderr
    assert "DEV_PYTHON" in result.stderr


def test_install_is_idempotent_and_installed_hook_uses_override(repo):
    write(repo, "scripts/pre_commit.py", HOOK_SCRIPT.read_text())
    result = run_hook(repo, "install")
    assert result.returncode == 0, result.stderr
    hook = repo / ".git/hooks/pre-commit"
    assert os.access(hook, os.X_OK)
    before = hook.read_bytes()
    assert run_hook(repo, "install").returncode == 0
    assert hook.read_bytes() == before
    write(repo, "tests/example.py", "value=2\n")
    git(repo, "add", "tests/example.py")
    result = subprocess.run(
        [str(hook)],
        cwd=repo,
        env={**os.environ, "DEV_PYTHON": sys.executable},
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "reformatted" in result.stdout + result.stderr


def test_install_preserves_existing_hook(repo):
    hook = repo / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\necho existing\n")
    before = hook.read_bytes()
    result = run_hook(repo, "install")
    assert result.returncode != 0
    assert "existing" in result.stderr.lower()
    assert hook.read_bytes() == before


def test_install_preserves_configured_hooks_path(repo):
    git(repo, "config", "core.hooksPath", "custom hooks")
    result = run_hook(repo, "install")
    assert result.returncode != 0
    assert "core.hooksPath" in result.stderr
    assert git(repo, "config", "--get", "core.hooksPath") == b"custom hooks\n"
    assert not (repo / "custom hooks").exists()
    assert not (repo / ".git/hooks/pre-commit").exists()


def test_install_preserves_symlink_hook(repo):
    target = repo / "my-hook"
    target.write_text("#!/bin/sh\nexit 0\n")
    hook = repo / ".git/hooks/pre-commit"
    hook.symlink_to(target)
    before = target.read_bytes(), target.stat().st_mode
    result = run_hook(repo, "install")
    assert result.returncode != 0
    assert hook.is_symlink()
    assert (target.read_bytes(), target.stat().st_mode) == before


def test_missing_ruff_has_setup_guidance(repo):
    import venv

    venv.EnvBuilder(with_pip=False).create(repo / "empty-env")
    write(repo, "tests/example.py", "value = 2\n")
    git(repo, "add", "tests/example.py")
    result = run_hook(repo, DEV_PYTHON=str(repo / "empty-env/bin/python"))
    assert result.returncode != 0
    assert "Ruff is unavailable" in result.stderr
    assert "make dev-setup" in result.stderr


def test_respects_staged_lint_exclusions_and_never_fixes(repo):
    write(
        repo,
        "pyproject.toml",
        CONFIG.replace(
            "[tool.ruff]\n",
            '[tool.ruff]\nfix = true\nextend-exclude = ["scripts/ignored.py"]\n',
        ),
    )
    write(repo, "scripts/ignored.py", "value=missing\n")
    git(repo, "add", "pyproject.toml", "scripts/ignored.py")
    assert run_hook(repo).returncode == 0
    write(repo, "tests/example.py", "import os\n")
    git(repo, "add", "tests/example.py")
    before = state(repo)
    result = run_hook(repo)
    assert result.returncode != 0
    assert "F401" in result.stdout
    assert state(repo) == before
