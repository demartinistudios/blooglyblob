"""Deployment proofs use a private filesystem and an in-memory systemd manager."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import io
import json
import os
import signal
import subprocess
import tarfile

import pytest

from scripts import deploy, device_install as remote
from scripts.deploy_config import read_env


def test_dotenv_is_data_and_precedence(tmp_path):
    (tmp_path / ".env").write_text(
        'PI_HOST=saved.local\nPI_USER=saved\nEXAMPLE="$(touch /tmp/nope)"\n'
    )
    values = deploy.settings(tmp_path, {"PI_HOST": "exported.local"})
    assert values["PI_HOST"] == "exported.local"
    assert values["PI_USER"] == "saved"
    assert values["EXAMPLE"] == "$(touch /tmp/nope)"
    assert read_env(tmp_path / ".env")["EXAMPLE"] == "$(touch /tmp/nope)"


def test_bad_env_error_never_contains_secret(tmp_path):
    path = tmp_path / "app.env"
    path.write_text('OPENAI_API_KEY="secret-value\n')
    with pytest.raises(ValueError, match="line 1") as error:
        read_env(path)
    assert "secret-value" not in str(error.value)


def test_config_parser_matches_dotenv_literal_single_line_values(tmp_path):
    from dotenv import dotenv_values, set_key

    path = tmp_path / "app.env"
    path.touch()
    set_key(
        path,
        "RING_REFRESH_TOKEN",
        json.dumps({"token": "abc'quote\\backslash", "literal": "${NAME}"}),
    )
    set_key(path, "NAME", "a # comment-like literal")
    with path.open("a") as file:
        file.write('PLAIN=some unquoted value # comment\nDOUBLE="escaped\\nnewline"\n')
    assert read_env(path) == dotenv_values(path, interpolate=False)


def test_explicit_user_and_ssh_alias(monkeypatch):
    assert (
        deploy.target({"PI_HOST": "kitchen.local", "PI_USER": "alex"})
        == "alex@kitchen.local"
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(
            return_value=SimpleNamespace(
                stdout=f"hostname kitchen.local\nuser {os.environ.get('USER', 'alex')}\n"
            )
        ),
    )
    assert deploy.target({"PI_HOST": "robot"}) == "robot"
    subprocess.run.assert_called_once_with(
        ["ssh", "-G", "robot"], check=True, text=True, capture_output=True
    )
    subprocess.run.return_value.stdout = "hostname kitchen.local\nuser local-default\n"
    with pytest.raises(ValueError, match="Set PI_USER"):
        deploy.target({"PI_HOST": "kitchen.local"})
    for malicious in ("-oProxyCommand=bad", "host;bad", "user@host", "host $(bad)"):
        with pytest.raises(ValueError):
            deploy.target({"PI_HOST": malicious, "PI_USER": "alex"})


def test_make_override_and_saved_values(tmp_path):
    # Run the real Makefile against a harmless fake deployment entrypoint.
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/deploy.py").write_text(
        'import os,json;print(json.dumps({k:v for k,v in os.environ.items() if k in ("PI_HOST","PI_USER")}))'
    )
    makefile = Path(__file__).resolve().parents[1] / "Makefile"
    result = subprocess.run(
        ["make", "-s", "-f", str(makefile), "pi-check", "PI_HOST=chosen.local"],
        cwd=tmp_path,
        env={**os.environ, "PI_HOST": "export.local"},
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["PI_HOST"] == "chosen.local"
    result = subprocess.run(
        ["make", "-s", "-f", str(makefile), "pi-check"],
        cwd=tmp_path,
        env={key: value for key, value in os.environ.items() if key not in deploy.KEYS},
        check=True,
        capture_output=True,
        text=True,
    )
    assert "PI_HOST" not in json.loads(
        result.stdout
    )  # absent exports cannot erase saved .env


def test_payload_excludes_everything_outside_runtime_allowlist(tmp_path):
    names = {str(path.relative_to(deploy.ROOT)) for path in deploy.payload_files()}
    assert {
        "blooglyblob/__main__.py",
        "blooglyblob/application.py",
        "blooglyblob/ai/persona.json",
        "blooglyblob/ai/voice_profile.json",
        "tool_configs/setTimer.json",
        *deploy.MEDIA,
    } <= names
    assert {"LICENSE", "LICENSING.md", "LICENSES/CC0-1.0.txt"} <= names
    assert all(not name.endswith(".env") for name in names)
    assert "pi/servo_calibration.json" not in names
    assert not any(
        name.startswith(("docs/", "local/", "models/", ".git/", "build-guide"))
        for name in names
    )
    archive = tmp_path / "payload.tar.gz"
    deploy.create_payload(archive)
    with tarfile.open(archive) as source:
        assert set(source.getnames()) == names


def test_payload_rejects_symlink(tmp_path):
    for source in deploy.payload_files():
        target = tmp_path / source.relative_to(deploy.ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
    (tmp_path / "README.md").unlink()
    (tmp_path / "README.md").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="regular file inside the repository"):
        deploy.payload_files(tmp_path)


@pytest.mark.parametrize("mode", ["provision", "update"])
def test_host_uploads_credentials_only_when_explicit_provision_inputs_selected(
    tmp_path, monkeypatch, mode
):
    runtime_input = tmp_path / "runtime input.env"
    runtime_input.write_text("OPENAI_API_KEY=secret-input\n")
    calls = []

    def fake_ssh(destination, command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(stdout="/tmp/blooglyblob-deploy-test123\n")

    monkeypatch.setattr(deploy, "check", lambda destination: None)
    monkeypatch.setattr(deploy, "ssh", fake_ssh)
    mock_subprocess = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(deploy.subprocess, "run", mock_subprocess)
    deploy.install(
        "alex@2001:db8::123", mode, {"BLOOGLYBLOB_ENV_FILE": str(runtime_input)}
    )
    transfers = [call.args[0] for call in mock_subprocess.call_args_list]
    assert all(call[0] == "scp" for call in transfers)
    assert all(call[-1].startswith("alex@[2001:db8::123]:/tmp/") for call in transfers)
    assert any(call[-1].endswith("/app.env") for call in transfers) is (
        mode == "provision"
    )
    assert calls[-2][0][:3] == [
        "sudo",
        "python3",
        "-B",
    ]  # no root-owned bytecode in user upload dir
    assert calls[-2][1]["tty"] is True
    assert calls[-1][0] == ["rm", "-rf", "--", "/tmp/blooglyblob-deploy-test123"]
    assert not any("secret-input" in str(call) for call in calls + transfers)


def test_ssh_preserves_normal_host_key_verification(monkeypatch):
    execute = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(deploy.subprocess, "run", execute)
    deploy.ssh("alex@robot.local", ["python3", "-c", "print('hello')"])
    command = execute.call_args.args[0]
    assert command[0] == "ssh"
    assert "StrictHostKeyChecking=no" not in command
    assert "UserKnownHostsFile=/dev/null" not in command


def test_pigpio_build_installs_daemon_without_global_python(monkeypatch):
    calls = []
    present = iter([False, True])
    monkeypatch.setattr(remote, "pigpio_installed", lambda: next(present))

    def download(url, timeout):
        assert timeout == 30
        calls.append(["download", url])
        return io.BytesIO(b"test archive")

    monkeypatch.setattr(remote.urllib.request, "urlopen", download)
    monkeypatch.setattr(remote, "extract", lambda *args: None)
    monkeypatch.setattr(
        remote,
        "run",
        lambda command, **kwargs: calls.append([str(item) for item in command]),
    )
    remote.install_pigpio()
    assert calls[0][1].endswith(remote.PIGPIO_COMMIT + ".tar.gz")
    assert ["make", "-j1", "pigpiod"] in calls
    assert ["make", "install"] not in calls
    assert not any("setup.py" in str(call) for call in calls)
    assert calls[-1] == ["ldconfig"]


@pytest.mark.parametrize(
    "name,kind", [("../../outside", tarfile.REGTYPE), ("linked", tarfile.SYMTYPE)]
)
def test_extract_rejects_traversal_and_links(tmp_path, name, kind):
    archive = tmp_path / "bad.tar"
    with tarfile.open(archive, "w") as writer:
        entry = tarfile.TarInfo(name)
        entry.type = kind
        entry.linkname = "/etc/passwd"
        writer.addfile(entry, io.BytesIO(b""))
    with pytest.raises(RuntimeError, match="Unsafe"):
        remote.extract(archive, tmp_path / "out")


def test_gpio_setup_requires_reboot_before_starting_with_loaded_onboard_audio(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(remote, "GPIO_BLACKLIST", tmp_path / "blacklist.conf")
    monkeypatch.setattr(remote, "MODULES", tmp_path / "modules")
    remote.MODULES.write_text("snd_bcm2835 28672 1 - Live 0x000\n")
    with pytest.raises(RuntimeError, match="Reboot"):
        remote.configure_gpio("provision")
    assert remote.GPIO_BLACKLIST.read_text() == remote.GPIO_BLACKLIST_CONTENT
    remote.MODULES.write_text("snd_usb_audio 1234 1 - Live 0x000\n")
    remote.configure_gpio("provision")
    remote.configure_gpio("update")
    remote.GPIO_BLACKLIST.unlink()
    with pytest.raises(RuntimeError, match="pi-provision"):
        remote.configure_gpio("update")


@pytest.mark.parametrize(
    "key", ["OPENAI_INACTIVITY_SECONDS", "OPENAI_SESSION_MAX_SECONDS"]
)
@pytest.mark.parametrize("value", ["0", "-1"])
def test_session_limits_fail_preflight_before_stop(key, value):
    from scripts.deploy_config import validate_runtime_config
    from blooglyblob.config import validate_settings

    values = {"OPENAI_API_KEY": "test-key", key: value}
    for validator in (validate_runtime_config, validate_settings):
        with pytest.raises(ValueError, match=key):
            validator(values)


class Systemd:
    """Persist process state independently of cached fragment metadata."""

    def __init__(self, roots):
        self.roots = roots
        self.active = {name: "active" for name in remote.SERVICES}
        self.calls = []
        self.metadata = {}
        self.failure = lambda command: None
        self.reload()

    def reload(self):
        for name in remote.SERVICES:
            fragment = next(
                (root / name for root in self.roots if (root / name).exists()), None
            )
            self.metadata[name] = {"LoadState": "loaded" if fragment else "not-found"}

    def run(self, command, **kwargs):
        command = list(map(str, command))
        self.calls.append(command)
        self.failure(command)
        output = ""
        if command[:2] == ["systemctl", "daemon-reload"]:
            self.reload()
        elif command[:2] == ["systemctl", "show"]:
            name = command[2]
            if "--property=ActiveState" in command:
                output = self.active.get(name, "inactive")
            elif "--property=LoadState" in command:
                output = self.metadata[name]["LoadState"]
            else:
                output = "\n".join(f"{k}={v}" for k, v in self.metadata[name].items())
        elif command[:2] == ["systemctl", "stop"]:
            for name in command[2:]:
                self.active[name] = "inactive"
        elif command[:2] == ["systemctl", "start"]:
            for name in command[2:]:
                self.active[name] = "active"
        elif command[:2] == ["systemctl", "is-active"]:
            if self.active.get(command[2]) != "active":
                raise subprocess.CalledProcessError(3, command)
        elif "venv" in command:
            (remote.VENV / "bin").mkdir(parents=True, exist_ok=True)
            (remote.VENV / "bin/python").touch()
        return SimpleNamespace(returncode=0, stdout=output)


@pytest.fixture
def installed(tmp_path, monkeypatch):
    for name in ("APP", "VENV", "CONFIG", "STATE", "SYSTEMD"):
        path = tmp_path / name.lower()
        path.mkdir()
        monkeypatch.setattr(remote, name, path)
    monkeypatch.setattr(remote, "LOCK", tmp_path / "install.lock")
    monkeypatch.setattr(remote, "validate_platform", lambda: None)
    monkeypatch.setattr(remote, "configure_gpio", lambda mode: None)
    monkeypatch.setattr(remote, "missing_packages", lambda: [])
    monkeypatch.setattr(remote, "pigpio_installed", lambda: True)
    monkeypatch.setattr(os, "chown", lambda *args: None)
    monkeypatch.setattr(os, "fchown", lambda *args: None)
    (remote.VENV / "bin").mkdir()
    (remote.VENV / "bin/python").touch()
    (remote.CONFIG / "app.env").write_text(
        "# preserved comment\nOPENAI_API_KEY=secret-existing\nMIC_GAIN=10\n"
    )
    (remote.SYSTEMD / "blooglyblob.service").write_bytes(
        (deploy.ROOT / "systemd/blooglyblob.service").read_bytes()
    )
    (remote.SYSTEMD / "pigpiod.service").write_text("[Service]\n")
    manager = Systemd((remote.SYSTEMD,))
    monkeypatch.setattr(remote, "run", manager.run)
    stage = tmp_path / "stage"
    stage.mkdir()
    deploy.create_payload(stage / "app.tar.gz")
    return stage, manager


def stopped(manager):
    return [c for c in manager.calls if c[:2] == ["systemctl", "stop"]]


def test_current_install_and_repeat_preserve_settings_state_and_licenses(installed):
    stage, manager = installed
    (stage / "app.env").write_text("OPENAI_API_KEY=must-not-win\n")
    remote.create_state()
    calibration = remote.STATE / "device/servo_calibration.json"
    calibration.write_bytes(b'{"keep":"calibration"}')
    timers = remote.STATE / "brain/timers.json"
    timers.write_bytes(b'{"keep":"timers"}')
    initial = (remote.CONFIG / "app.env").read_bytes()
    remote.install("provision", stage)
    assert (remote.CONFIG / "app.env").read_bytes() == initial
    remote.install("update", stage)
    assert (remote.CONFIG / "app.env").read_bytes() == initial
    assert read_env(remote.CONFIG / "app.env")["OPENAI_API_KEY"] == "secret-existing"
    assert calibration.read_bytes() == b'{"keep":"calibration"}'
    assert timers.read_bytes() == b'{"keep":"timers"}'
    assert (remote.CONFIG / "app.env").stat().st_mode & 0o777 == 0o600
    assert stopped(manager)[0] == ["systemctl", "stop", *remote.SERVICES]
    assert stopped(manager)[1] == ["systemctl", "stop", "pigpiod.service"]
    assert stopped(manager)[2] == ["systemctl", "stop", *remote.SERVICES]
    assert not any(
        c[0] == "useradd" or any(x in c for x in ("amixer", "alsactl", "upgrade"))
        for c in manager.calls
    )
    assert not any("protocol_check" in " ".join(c) for c in manager.calls)
    assert manager.calls[-1] == ["systemctl", "is-active", "blooglyblob.service"]
    for name in ("LICENSE", "LICENSING.md", "LICENSES/CC0-1.0.txt"):
        assert (remote.APP / name).read_bytes() == (deploy.ROOT / name).read_bytes()


@pytest.mark.parametrize("mode", ["provision", "update"])
def test_dependency_failure_stays_stopped_then_repairs(installed, mode):
    stage, manager = installed

    def fail(command):
        if "pip" in command:
            raise subprocess.CalledProcessError(1, command)

    manager.failure = fail
    with pytest.raises(subprocess.CalledProcessError):
        remote.install(mode, stage)
    assert stopped(manager)
    assert not any(c[:2] == ["systemctl", "start"] for c in manager.calls)
    assert read_env(remote.CONFIG / "app.env")["OPENAI_API_KEY"] == "secret-existing"
    manager.failure = lambda command: None
    remote.install(mode, stage)
    assert manager.active["blooglyblob.service"] == "active"


@pytest.mark.parametrize(
    "failure",
    [
        "missing-package",
        "bad-config",
        "bad-payload",
        "state-collision",
        "apt-failure",
        "stop-failure",
        "stop-still-active",
    ],
)
def test_preflight_or_stop_failure_never_replaces_code(installed, monkeypatch, failure):
    stage, manager = installed
    (remote.APP / "sentinel").write_bytes(b"unchanged")
    replace = Mock(side_effect=AssertionError("must not replace code"))
    monkeypatch.setattr(remote, "replace_application", replace)
    mode = "update"
    if failure == "missing-package":
        monkeypatch.setattr(remote, "missing_packages", lambda: ["portaudio19-dev"])
    elif failure == "bad-config":
        (remote.CONFIG / "app.env").write_text(
            "OPENAI_API_KEY=test-key\nOPENAI_SESSION_MAX_SECONDS=0\n"
        )
    elif failure == "bad-payload":
        with tarfile.open(stage / "app.tar.gz", "w:gz"):
            pass
    elif failure == "state-collision":
        (remote.CONFIG / "app.env").write_text(
            f"OPENAI_API_KEY=test-key\nSERVO_CALIBRATION_FILE={remote.APP / 'blooglyblob/application.py'}\n"
        )
    elif failure == "apt-failure":
        mode = "provision"
        manager.failure = lambda command: (
            (_ for _ in ()).throw(subprocess.CalledProcessError(1, command))
            if command[0] == "apt-get"
            else None
        )
    elif failure == "stop-failure":
        manager.failure = lambda command: (
            (_ for _ in ()).throw(subprocess.CalledProcessError(1, command))
            if command[:2] == ["systemctl", "stop"]
            else None
        )
    else:
        oldrun = manager.run

        def no_stop(command, **kwargs):
            result = oldrun(command, **kwargs)
            if "--property=ActiveState" in command:
                result.stdout = "deactivating"
            return result

        monkeypatch.setattr(remote, "run", no_stop)
    with pytest.raises((ValueError, RuntimeError, subprocess.CalledProcessError)):
        remote.install(mode, stage)
    replace.assert_not_called()
    assert (remote.APP / "sentinel").read_bytes() == b"unchanged"
    if not failure.startswith("stop-"):
        assert not stopped(manager)
    assert not list(remote.CONFIG.glob(".app-env-*"))


def test_update_does_not_touch_os_packages_or_uninstall_dependencies(installed):
    stage, manager = installed
    remote.install("update", stage)
    assert not any(c[0] in ("apt-get", "make", "ldconfig") for c in manager.calls)
    assert not any("uninstall" in c for c in manager.calls)


def test_package_build_uses_fresh_payload_not_previous_build_output(installed):
    stage, manager = installed
    stale = remote.APP / "build/lib/server/brain.py"
    stale.parent.mkdir(parents=True)
    stale.write_text("# Retired build output must not enter a new wheel.\n")
    builds = []

    def inspect_build(command):
        if "pip" in command and "--no-deps" in command:
            source = Path(command[-1])
            assert source != remote.APP
            assert (source / "blooglyblob/__main__.py").is_file()
            assert not (source / "build").exists()
            assert not (source / "server").exists()
            builds.append(source)

    manager.failure = inspect_build
    remote.install("update", stage)
    assert len(builds) == 1
    assert (remote.APP / "blooglyblob/__main__.py").is_file()


def test_fresh_provision_and_rerun(installed):
    import shutil

    stage, manager = installed
    for directory in (remote.VENV, remote.CONFIG, remote.STATE):
        shutil.rmtree(directory)
    for unit in remote.SYSTEMD.iterdir():
        unit.unlink()
    manager.active.clear()
    (stage / "app.env").write_text("OPENAI_API_KEY=first-key\n")
    remote.install("provision", stage)
    assert not stopped(manager)
    assert read_env(remote.CONFIG / "app.env") == {"OPENAI_API_KEY": "first-key"}
    for directory in ("brain", "device"):
        assert (remote.STATE / directory).stat().st_mode & 0o777 == 0o700
    first = (remote.CONFIG / "app.env").read_bytes()
    (stage / "app.env").write_text("OPENAI_API_KEY=must-not-replace\n")
    remote.install("provision", stage)
    assert (remote.CONFIG / "app.env").read_bytes() == first
    assert not any(c[0] == "useradd" for c in manager.calls)


@pytest.mark.parametrize("boundary", ["published", "package", "unit"])
def test_interrupted_boundaries_are_repairable(installed, monkeypatch, boundary):
    stage, manager = installed
    attribute = {
        "published": "ensure_runtime_config",
        "package": "replace_application",
        "unit": "install_units",
    }[boundary]
    owner = remote
    original = getattr(owner, attribute)

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("simulated interruption")

    monkeypatch.setattr(owner, attribute, interrupted)
    with pytest.raises(OSError, match="interruption"):
        remote.install("update", stage)
    assert not list(remote.CONFIG.glob(".app-env-*"))
    monkeypatch.setattr(owner, attribute, original)
    remote.install("update", stage)
    assert read_env(remote.CONFIG / "app.env")["OPENAI_API_KEY"] == "secret-existing"
    assert manager.active["blooglyblob.service"] == "active"


def test_cached_missing_fragment_refreshes_before_inspection(installed):
    stage, manager = installed
    (remote.SYSTEMD / "blooglyblob.service").unlink()
    assert manager.metadata["blooglyblob.service"]["LoadState"] == "loaded"
    manager.active["blooglyblob.service"] = "inactive"
    remote.install("update", stage)
    assert manager.calls[0] == ["systemctl", "daemon-reload"]


def test_removed_fragment_with_live_process_must_still_stop(installed):
    stage, manager = installed
    (remote.SYSTEMD / "blooglyblob.service").unlink()
    remote.install("update", stage)
    assert ["systemctl", "stop", "blooglyblob.service"] in manager.calls


def test_readiness_failure_aborts_without_protocol_probe_and_reruns(installed):
    stage, manager = installed

    def fail(command):
        if command == ["systemctl", "start", "blooglyblob.service"]:
            raise subprocess.CalledProcessError(1, command)

    manager.failure = fail
    with pytest.raises(subprocess.CalledProcessError):
        remote.install("update", stage)
    assert manager.active["blooglyblob.service"] == "inactive"
    manager.failure = lambda command: None
    remote.install("update", stage)
    assert manager.calls[-1] == ["systemctl", "is-active", "blooglyblob.service"]


def test_lock_is_exclusive(installed):
    with remote.installation_lock():
        with pytest.raises(RuntimeError, match="owns the lock"):
            with remote.installation_lock():
                pytest.fail("concurrent owner")


@pytest.fixture(params=["defaults", "explicit_paths"])
def diagnostic_environment(monkeypatch, request):
    ambient = (
        {}
        if request.param == "defaults"
        else {
            "HOME": "/custom/operator-home",
            "BLOOGLYBLOB_STATE_DIR": "/custom/timers",
            "SERVO_CALIBRATION_FILE": "/custom/calibration.json",
            "BLOOGLYBLOB_MEDIA_DIR": "/custom/media",
        }
    )
    monkeypatch.setattr(os, "environ", dict(ambient))
    # Pytest adds its current-test marker after fixture setup; include that
    # ambient value while still asserting exact preservation of custom paths.
    return os.environ


@pytest.mark.parametrize("active", [True, False])
@pytest.mark.parametrize("command", ["run", "servo-fit"])
@pytest.mark.parametrize(
    "outcome", ["success", "error", "interrupt", "terminate-kill", "uncertain"]
)
def test_diagnostic_waits_for_child_before_restoration(
    installed, monkeypatch, active, command, outcome, diagnostic_environment
):
    _, manager = installed
    manager.active["blooglyblob.service"] = "active" if active else "inactive"
    events = []
    child = Mock()
    child.poll.return_value = None
    if outcome == "success":
        child.wait.side_effect = [0]
    elif outcome == "error":
        child.wait.side_effect = [2]
    else:
        child.wait.side_effect = [
            KeyboardInterrupt,
            *(
                [subprocess.TimeoutExpired("diagnostic", 5)]
                if outcome in ("terminate-kill", "uncertain")
                else []
            ),
            *(
                [subprocess.TimeoutExpired("diagnostic", 5)]
                if outcome == "uncertain"
                else [-15]
            ),
        ]
    real_wait = child.wait

    def wait(*args, **kwargs):
        value = real_wait(*args, **kwargs)
        events.append("child-exited")
        return value

    child.wait = wait

    def popen(command, **kwargs):
        assert command[-2:] == ["-m", module]
        assert kwargs["env"] == diagnostic_environment | {
            "BLOOGLYBLOB_ENV_FILE": str(remote.CONFIG / "app.env"),
            "PYTHONUNBUFFERED": "1",
        }
        return child

    monkeypatch.setattr(remote.subprocess, "Popen", popen)
    module = "blooglyblob" if command == "run" else "blooglyblob.hardware.servo_fit"
    oldrun = manager.run

    def run(command, **kwargs):
        if command[:2] == ["systemctl", "start"]:
            assert events == ["child-exited"]
        return oldrun(command, **kwargs)

    monkeypatch.setattr(remote, "run", run)
    if outcome == "success":
        remote.diagnostic(command)
    else:
        with pytest.raises(
            (KeyboardInterrupt, RuntimeError, subprocess.CalledProcessError)
        ):
            remote.diagnostic(command)
    restored = ["systemctl", "start", "blooglyblob.service"] in manager.calls
    assert restored is (command != "servo-fit" and active and outcome != "uncertain")
    if outcome in ("interrupt", "terminate-kill", "uncertain"):
        child.terminate.assert_called_once()
    if outcome in ("terminate-kill", "uncertain"):
        child.kill.assert_called_once()


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGHUP, signal.SIGTERM])
def test_diagnostic_signal_restores_after_confirmed_exit(installed, monkeypatch, sig):
    _, manager = installed
    child = Mock()
    child.poll.return_value = None
    calls = 0

    def waiting(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            os.kill(os.getpid(), sig)
        return -sig

    child.wait.side_effect = waiting
    monkeypatch.setattr(remote.subprocess, "Popen", Mock(return_value=child))

    def interrupted(*args):
        raise KeyboardInterrupt

    prior = signal.signal(sig, interrupted)
    try:
        with pytest.raises(KeyboardInterrupt):
            remote.diagnostic("run")
    finally:
        signal.signal(sig, prior)
    assert calls == 2
    assert manager.calls[-1] == ["systemctl", "start", "blooglyblob.service"]


@pytest.mark.parametrize("outcome", ["direct", "already-exited", "terminate", "kill"])
def test_diagnostic_ownership_failure_leaves_service_stopped(
    installed, monkeypatch, outcome
):
    _, manager = installed
    manager.active["blooglyblob.service"] = "active"
    child = Mock()
    child.poll.return_value = 73 if outcome == "already-exited" else None
    waits = [73] if outcome == "direct" else [KeyboardInterrupt, 73]
    if outcome == "kill":
        waits.insert(1, subprocess.TimeoutExpired("diagnostic", 5))
    child.wait.side_effect = waits
    monkeypatch.setattr(remote.subprocess, "Popen", Mock(return_value=child))

    expected_error = (
        subprocess.CalledProcessError if outcome == "direct" else KeyboardInterrupt
    )
    with pytest.raises(expected_error):
        remote.diagnostic("run")

    assert ["systemctl", "start", "blooglyblob.service"] not in manager.calls
    assert manager.active["blooglyblob.service"] == "inactive"
    assert child.wait.call_count == (
        1 if outcome == "direct" else 3 if outcome == "kill" else 2
    )
    assert child.terminate.call_count == (1 if outcome in ("terminate", "kill") else 0)
    assert child.kill.call_count == (1 if outcome == "kill" else 0)


@pytest.mark.parametrize("failure", ["stop-error", "still-active"])
def test_fit_never_starts_child_without_confirmed_service_stop(monkeypatch, failure):
    monkeypatch.setattr(remote, "unit_property", Mock(return_value="active"))
    run = Mock()
    if failure == "stop-error":
        run.side_effect = subprocess.CalledProcessError(1, ["systemctl", "stop"])
    monkeypatch.setattr(remote, "run", run)
    child = Mock()
    monkeypatch.setattr(remote.subprocess, "Popen", child)
    with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
        remote.diagnostic("servo-fit")
    child.assert_not_called()
    assert all(
        call.args[0][:2] != ["systemctl", "start"] for call in run.call_args_list
    )


def test_fit_lock_conflict_prevents_device_work(tmp_path, monkeypatch):
    monkeypatch.setattr(remote, "LOCK", tmp_path / "operation.lock")
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    # main's failure report must also remain on the simulated system boundary.
    monkeypatch.setattr(remote.subprocess, "run", Mock())
    operation = Mock()
    monkeypatch.setattr(remote, "diagnostic", operation)
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP)}
    try:
        with remote.installation_lock():
            assert remote.main(["servo-fit"]) == 1
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    operation.assert_not_called()


def test_make_fit_dispatches_through_supported_host_command(tmp_path, monkeypatch):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/deploy.py").write_text("import sys; print(sys.argv[1])")
    makefile = deploy.ROOT / "Makefile"
    result = subprocess.run(
        ["make", "-s", "-f", str(makefile), "pi-servo-fit"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "servo-fit"
    monkeypatch.setattr(
        deploy, "settings", lambda: {"PI_HOST": "pi.local", "PI_USER": "builder"}
    )
    monkeypatch.setattr(deploy.shutil, "which", lambda _: "/usr/bin/tool")
    connection = Mock()
    monkeypatch.setattr(deploy, "ssh", connection)
    assert deploy.main(["servo-fit"]) == 0
    assert connection.call_args.args == (
        "builder@pi.local",
        [
            "sudo",
            "python3",
            "/opt/blooglyblob/app/scripts/device_install.py",
            "servo-fit",
        ],
    )


@pytest.mark.parametrize("command", ["test-servos", "calibrate-servos"])
def test_retired_servo_commands_are_not_exposed(command):
    assert command not in deploy.DIAGNOSTICS
    assert command not in remote.DIAGNOSTICS
    result = subprocess.run(
        ["make", "-n", "-f", str(deploy.ROOT / "Makefile"), f"pi-{command}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    names = {str(path.relative_to(deploy.ROOT)) for path in deploy.payload_files()}
    assert "blooglyblob/hardware/" + command.replace("-", "_") + ".py" not in names


def test_single_service_has_truthful_readiness_and_fault_restart_policy():
    from blooglyblob.application import OWNERSHIP_UNCERTAIN_EXIT

    assert remote.OWNERSHIP_UNCERTAIN_EXIT == OWNERSHIP_UNCERTAIN_EXIT == 73
    source = deploy.ROOT / "systemd/blooglyblob.service"
    text = source.read_text()
    for line in (
        "Type=notify",
        "NotifyAccess=main",
        "TimeoutStartSec=30",
        "TimeoutStopSec=20",
        "Restart=on-failure",
        "RestartPreventExitStatus=73",
        "User=root",
        "Group=root",
        "ExecStart=/opt/blooglyblob/venv/bin/python -m blooglyblob",
    ):
        assert line in text.splitlines()
    assert "blooglyblob-brain" not in text and "EnvironmentFile=" not in text


def test_custom_state_calibration_and_media_inside_app_tree_survive(installed):
    stage, _ = installed
    state = remote.APP / "custom/data"
    state.mkdir(parents=True)
    timers = state / "timers.json"
    timers.write_bytes(b"keep timers")
    calibration = remote.APP / "custom/servo_calibration.json"
    calibration.write_bytes(b"keep calibration")
    media = remote.APP / "sounds/custom"
    media.mkdir(parents=True)
    (media / "personal.wav").write_bytes(b"keep media")
    (remote.CONFIG / "app.env").write_text(
        f"OPENAI_API_KEY=secret-existing\nBLOOGLYBLOB_STATE_DIR={state}\n"
        f"SERVO_CALIBRATION_FILE={calibration}\nBLOOGLYBLOB_MEDIA_DIR={media}\n"
    )
    remote.install("update", stage)
    assert timers.read_bytes() == b"keep timers"
    assert calibration.read_bytes() == b"keep calibration"
    assert (media / "personal.wav").read_bytes() == b"keep media"
    assert read_env(remote.CONFIG / "app.env")["BLOOGLYBLOB_MEDIA_DIR"] == str(media)


def test_runtime_symlink_destination_aborts_before_stop(installed):
    stage, manager = installed
    (remote.APP / "blooglyblob").symlink_to(stage, target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink"):
        remote.install("update", stage)
    assert not stopped(manager)


def test_failed_prerequisite_download_keeps_running_application(installed, monkeypatch):
    stage, manager = installed
    monkeypatch.setattr(remote, "pigpio_installed", lambda: False)

    def timeout(*args, **kwargs):
        raise TimeoutError("source unavailable")

    monkeypatch.setattr(remote.urllib.request, "urlopen", timeout)
    with pytest.raises(TimeoutError, match="source unavailable"):
        remote.install("provision", stage)
    assert not stopped(manager)
    assert read_env(remote.CONFIG / "app.env")["OPENAI_API_KEY"] == "secret-existing"


def test_missing_unit_property_output_survives_systemctl_nonzero(
    installed, monkeypatch
):
    stage, manager = installed
    (remote.SYSTEMD / "blooglyblob.service").unlink()
    manager.active["blooglyblob.service"] = "inactive"
    original = manager.run

    def systemctl(command, **kwargs):
        result = original(command, **kwargs)
        if (
            command[:2] == ["systemctl", "show"]
            and "--value" in command
            and result.stdout in ("not-found", "inactive")
        ):
            raise subprocess.CalledProcessError(1, command, output=result.stdout)
        return result

    monkeypatch.setattr(remote, "run", systemctl)
    remote.install("update", stage)
    assert manager.active["blooglyblob.service"] == "active"


def test_current_service_dropin_is_preserved_without_flattening(installed):
    stage, manager = installed
    dropdir = remote.SYSTEMD / "blooglyblob.service.d"
    dropdir.mkdir()
    override = dropdir / "settings.conf"
    contents = "[Service]\nEnvironment=MIC_GAIN=4\n"
    override.write_text(contents)
    remote.install("update", stage)
    assert override.read_text() == contents
    assert read_env(remote.CONFIG / "app.env")["MIC_GAIN"] == "10"
    assert not list(remote.CONFIG.glob("recovery-*"))


@pytest.mark.parametrize("mode", ["provision", "update"])
def test_install_uses_service_audio_settings_for_readiness(installed, mode):
    stage, manager = installed
    with (remote.CONFIG / "app.env").open("a") as config:
        config.write("AUDIO_OUTPUT_DEVICE=disconnected-speaker\n")
    dropdir = remote.SYSTEMD / "blooglyblob.service.d"
    dropdir.mkdir()
    override = dropdir / "audio.conf"
    contents = "[Service]\nEnvironment=AUDIO_OUTPUT_DEVICE=connected-speaker\n"
    override.write_text(contents)

    def effective_settings(command):
        if command[-1] == "check-audio":
            # A standalone probe receives app.env, not systemd's override.
            raise RuntimeError("Selected output device is unavailable")
        if command == ["systemctl", "start", "blooglyblob.service"]:
            assert override.read_text() == contents

    manager.failure = effective_settings
    remote.install(mode, stage)
    assert manager.active["blooglyblob.service"] == "active"
    assert manager.calls[-1] == ["systemctl", "is-active", "blooglyblob.service"]


def test_led_driver_patch_preserves_old_revision_and_adds_new_revision(tmp_path):
    from scripts import install_led_driver as led

    # The upstream board entry is additive: old boards retain the same mapping.
    old = """    {
        .hwver  = 0x9020e0,
        .type = RPI_HWVER_TYPE_PI2,
        .periph_base = PERIPH_BASE_RPI2,
        .videocore_base = VIDEOCORE_BASE_RPI2,
        .desc = "Model 3 A+",
    }"""
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/rpihw.c").write_text("before\n" + old + "\n};\nafter\n")
    (tmp_path / "setup.py").write_text("version           = '5.0.0',\n")
    led.patch_source(tmp_path)
    assert (tmp_path / "lib/rpihw.c").read_text() == (
        "before\n" + old + ",\n" + old.replace("9020e0", "9020e1") + "\n};\nafter\n"
    )
    assert led.VERSION in (tmp_path / "setup.py").read_text()
    with pytest.raises(RuntimeError, match="Unexpected"):
        led.patch_source(tmp_path)


def test_led_driver_rejects_changed_archive_before_extraction(tmp_path):
    from scripts import install_led_driver as led

    with pytest.raises(RuntimeError, match="SHA256"):
        led.unpack_source(b"unexpected download", tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("installed_version", [None, "5.0.0", "5.0.0+bgb.1"])
def test_led_driver_install_is_repeatable_and_checks_board(
    tmp_path, monkeypatch, installed_version
):
    from scripts import install_led_driver as led

    def version(name):
        if installed_version is None:
            raise led.PackageNotFoundError(name)
        return installed_version

    monkeypatch.setattr(led, "version", version)
    response = io.BytesIO(b"test archive")
    fetch = Mock(return_value=response)
    monkeypatch.setattr(led.urllib.request, "urlopen", fetch)
    unpack = Mock(return_value=tmp_path)
    monkeypatch.setattr(led, "unpack_source", unpack)
    patch = Mock()
    monkeypatch.setattr(led, "patch_source", patch)
    run = Mock()
    monkeypatch.setattr(led.subprocess, "run", run)
    verify = Mock()
    monkeypatch.setattr(led, "verify_board", verify)
    led.install()
    verify.assert_called_once_with()
    if installed_version == led.VERSION:
        fetch.assert_not_called()
        run.assert_not_called()
    else:
        fetch.assert_called_once()
        patch.assert_called_once_with(tmp_path)
        assert "--no-deps" in run.call_args.args[0]
        assert run.call_args.kwargs["check"] is True


def test_led_driver_install_failure_does_not_claim_board_ready(tmp_path, monkeypatch):
    from scripts import install_led_driver as led

    monkeypatch.setattr(led, "version", lambda name: "5.0.0")
    monkeypatch.setattr(led.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"x"))
    monkeypatch.setattr(led, "unpack_source", lambda *a: tmp_path)
    monkeypatch.setattr(led, "patch_source", lambda *a: None)
    monkeypatch.setattr(
        led.subprocess, "run", Mock(side_effect=subprocess.CalledProcessError(1, "pip"))
    )
    verify = Mock()
    monkeypatch.setattr(led, "verify_board", verify)
    with pytest.raises(subprocess.CalledProcessError):
        led.install()
    verify.assert_not_called()


@pytest.mark.parametrize("mode", ["provision", "update"])
def test_install_checks_led_revision_before_starting_app(installed, mode):
    stage, manager = installed
    remote.install(mode, stage)
    driver = [
        c for c in manager.calls if any(x.endswith("/install_led_driver.py") for x in c)
    ]
    assert len(driver) == 1
    assert manager.calls.index(driver[0]) < manager.calls.index(
        ["systemctl", "start", *remote.SERVICES]
    )
    assert "scripts/install_led_driver.py" in {
        str(p.relative_to(deploy.ROOT)) for p in deploy.payload_files()
    }


@pytest.mark.parametrize("recognized", [False, True])
def test_led_board_probe_fails_before_gpio_for_unknown_revision(
    monkeypatch, recognized
):
    from scripts import install_led_driver as led
    import sys

    monkeypatch.setitem(
        sys.modules, "_rpi_ws281x", SimpleNamespace(__file__="driver.so")
    )
    detect = Mock(return_value=1234 if recognized else None)
    monkeypatch.setattr(
        led.ctypes, "CDLL", lambda path: SimpleNamespace(rpi_hw_detect=detect)
    )
    if recognized:
        led.verify_board()
    else:
        with pytest.raises(RuntimeError, match="does not recognize"):
            led.verify_board()
    detect.assert_called_once_with()
    assert detect.argtypes == []
    assert detect.restype == led.ctypes.c_void_p


def test_led_driver_failure_leaves_application_stopped(installed):
    stage, manager = installed

    def fail(command):
        if any(x.endswith("/install_led_driver.py") for x in command):
            raise subprocess.CalledProcessError(1, command)

    manager.failure = fail
    with pytest.raises(subprocess.CalledProcessError):
        remote.install("update", stage)
    assert stopped(manager)
    assert not any(c[:2] == ["systemctl", "start"] for c in manager.calls)


def test_service_can_show_local_unavailable_state_before_network_is_online():
    from pathlib import Path

    service = (
        Path(__file__).resolve().parents[1] / "systemd/blooglyblob.service"
    ).read_text()
    assert "network-online.target" not in service
    assert "After=network.target sound.target pigpiod.service" in service
    assert "Requires=pigpiod.service" in service
