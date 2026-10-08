"""Wi-Fi provisioning uses private files and never drops the active connection."""

import json
from pathlib import Path
import subprocess

import pytest

from scripts import wifi_persistence as wifi

UUID = "12345678-1234-1234-1234-123456789abc"
PROFILE = f"""[connection]
id=netplan-wlan0-Example
uuid={UUID}
type=wifi
interface-name=wlan0

[wifi]
ssid=Example\\snetwork
mode=infrastructure

[wifi-security]
key-mgmt=wpa-psk
psk=example%secret\\svalue

[ipv4]
method=manual
address1=192.0.2.5/24,192.0.2.1
dns=192.0.2.1;

[ipv6]
method=auto
""".encode()


@pytest.fixture
def network(tmp_path, monkeypatch):
    for name in ("RUNTIME", "PERSISTENT", "NETPLAN", "BACKUPS"):
        directory = tmp_path / name.lower()
        directory.mkdir(mode=0o700)
        monkeypatch.setattr(wifi, name, directory)
    source = wifi.RUNTIME / "netplan-wlan0-Example.nmconnection"
    source.write_bytes(PROFILE)
    yaml = wifi.NETPLAN / f"90-NM-{UUID}.yaml"
    yaml.write_text("private original YAML\n")
    model = {
        "network": {
            "version": 2,
            "wifis": {
                "NM-" + UUID: {
                    "renderer": "NetworkManager",
                    "networkmanager": {"uuid": UUID},
                    "access-points": {"Example network": {"password": "example"}},
                }
            },
        }
    }
    calls = []
    destination = wifi.PERSISTENT / f"blooglyblob-wifi-{UUID}.nmconnection"

    def command(*args):
        calls.append(args)
        if args[0] == "/usr/bin/python3":
            return json.dumps(model)
        if args == ("nmcli", "-g", "UUID", "connection", "show", "--active"):
            return UUID
        if args[:3] == ("nmcli", "connection", "load"):
            return "loaded"
        if args == (
            "nmcli",
            "-t",
            "--escape",
            "no",
            "-f",
            "UUID,FILENAME",
            "connection",
            "show",
        ):
            return f"{UUID}:{destination}"
        raise AssertionError(args)

    monkeypatch.setattr(wifi, "command", command)
    return source, yaml, destination, model, calls


def test_migration_preserves_settings_and_private_backups_without_reconnect(network):
    source, yaml, destination, _, calls = network
    wifi.configure()
    assert destination.read_bytes() == PROFILE.replace(
        b"id=netplan-wlan0-Example", f"id=blooglyblob-wifi-{UUID}".encode()
    )
    assert destination.stat().st_mode & 0o777 == 0o600
    backup = wifi.BACKUPS / UUID
    assert backup.stat().st_mode & 0o777 == 0o700
    assert (backup / "profile.nmconnection").read_bytes() == PROFILE
    assert (backup / "netplan.yaml").read_text() == "private original YAML\n"
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in backup.iterdir())
    assert not source.exists() and not yaml.exists()
    assert not any(
        "up" in c or "down" in c or "reload" in c or "systemctl" in c for c in calls
    )
    calls.clear()
    wifi.configure()
    assert calls == []


@pytest.mark.parametrize(
    "case",
    [
        "second-profile",
        "extra-yaml",
        "ethernet",
        "wrong-uuid",
        "two-wifis",
        "missing-secret",
        "destination-collision",
        "symlink",
    ],
)
def test_ambiguous_or_unsupported_inputs_are_untouched(network, case):
    source, yaml, destination, model, _ = network
    if case == "second-profile":
        (wifi.RUNTIME / "netplan-other.nmconnection").write_bytes(PROFILE)
    elif case == "extra-yaml":
        (wifi.NETPLAN / "other.yml").write_text("other interface")
    elif case == "ethernet":
        model["network"]["ethernets"] = {"eth0": {"dhcp4": True}}
    elif case == "wrong-uuid":
        model["network"]["wifis"]["NM-" + UUID]["networkmanager"]["uuid"] = "other"
    elif case == "two-wifis":
        model["network"]["wifis"]["other"] = {}
    elif case == "missing-secret":
        source.write_bytes(
            PROFILE.replace(b"psk=example%secret\\svalue", b"psk-flags=1")
        )
    elif case == "destination-collision":
        destination.write_bytes(b"unrelated")
    elif case == "symlink":
        saved = source.with_suffix(".saved")
        source.rename(saved)
        source.symlink_to(saved)
    before = yaml.read_bytes()
    with pytest.raises(RuntimeError, match="Wi-Fi"):
        wifi.configure()
    assert yaml.read_bytes() == before and source.exists()
    assert not list(wifi.BACKUPS.iterdir())


def test_inactive_wifi_is_not_migrated(network, monkeypatch):
    source, yaml, destination, _, _ = network
    original = wifi.command
    monkeypatch.setattr(
        wifi, "command", lambda *a: "" if "--active" in a else original(*a)
    )
    with pytest.raises(RuntimeError, match="active"):
        wifi.configure()
    assert source.exists() and yaml.exists() and not destination.exists()


def test_load_failure_keeps_originals_and_retry_completes(network, monkeypatch):
    source, yaml, destination, _, _ = network
    original = wifi.command

    def fail(*a):
        if "load" in a:
            raise RuntimeError("Wi-Fi profile load failed")
        return original(*a)

    monkeypatch.setattr(wifi, "command", fail)
    with pytest.raises(RuntimeError, match="load"):
        wifi.configure()
    assert source.exists() and yaml.exists() and destination.exists()
    monkeypatch.setattr(wifi, "command", original)
    wifi.configure()
    assert not source.exists() and not yaml.exists()


def test_unverified_load_never_removes_originals(network, monkeypatch):
    source, yaml, _, _, _ = network
    original = wifi.command
    monkeypatch.setattr(
        wifi, "command", lambda *a: "" if "UUID,FILENAME" in a else original(*a)
    )
    with pytest.raises(RuntimeError, match="verify"):
        wifi.configure()
    assert source.exists() and yaml.exists()


def test_interrupted_retirement_can_be_repeated(network, monkeypatch):
    source, yaml, _, _, _ = network
    original = Path.unlink

    def interrupt(path, *a, **kw):
        if path == source:
            raise OSError("simulated interruption")
        return original(path, *a, **kw)

    monkeypatch.setattr(Path, "unlink", interrupt)
    with pytest.raises(OSError):
        wifi.configure()
    assert not yaml.exists() and source.exists()
    monkeypatch.setattr(Path, "unlink", original)
    wifi.configure()
    assert not source.exists()


def test_subprocess_errors_do_not_expose_settings(monkeypatch):
    def fail(*a, **kw):
        assert kw["capture_output"] and kw["timeout"] == 30
        raise subprocess.CalledProcessError(
            1, a[0], output="example%secret", stderr="example%secret"
        )

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(RuntimeError) as error:
        wifi.command("nmcli", "connection", "load", "private-profile")
    assert "example%secret" not in str(error.value)


def test_brackets_in_connection_label_do_not_corrupt_keyfile(network):
    source, _, destination, _, _ = network
    unusual = PROFILE.replace(b"netplan-wlan0-Example", b"netplan-wlan0-Example[guest]")
    source.write_bytes(unusual)
    wifi.configure()
    assert destination.read_bytes() == unusual.replace(
        b"id=netplan-wlan0-Example[guest]", f"id=blooglyblob-wifi-{UUID}".encode()
    )


def test_ap_level_identity_in_pi_generated_yaml_is_supported(network):
    _, _, _, model, _ = network
    node = model["network"]["wifis"]["NM-" + UUID]
    node["access-points"]["Example network"]["networkmanager"] = node.pop(
        "networkmanager"
    )
    wifi.configure()


def test_external_change_during_load_is_not_deleted(network, monkeypatch):
    source, yaml, _, _, _ = network
    original = wifi.command

    def change(*args):
        if "load" in args:
            yaml.write_text("changed by someone else")
        return original(*args)

    monkeypatch.setattr(wifi, "command", change)
    with pytest.raises(RuntimeError, match="changed during migration"):
        wifi.configure()
    assert yaml.read_text() == "changed by someone else" and source.exists()


def test_existing_native_and_ethernet_profiles_remain_unchanged(network):
    source, _, destination, _, _ = network
    source.write_bytes(PROFILE.replace(b"type=wifi", b"type=ethernet"))
    native = wifi.PERSISTENT / "existing.nmconnection"
    native.write_bytes(b"leave untouched")
    wifi.configure()
    assert native.read_bytes() == b"leave untouched" and source.exists()
    assert not destination.exists()


def test_private_backup_directory_required(network):
    source, yaml, destination, _, _ = network
    wifi.BACKUPS.chmod(0o755)
    with pytest.raises(RuntimeError, match="private"):
        wifi.configure()
    assert source.exists() and yaml.exists() and not destination.exists()
