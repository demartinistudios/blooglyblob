import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from dotenv import dotenv_values


def load_script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ring_does_not_read_implicit_server_config(monkeypatch, tmp_path):
    from blooglyblob.tools import ring_handler

    monkeypatch.delenv("RING_TOKEN", raising=False)
    monkeypatch.setattr(ring_handler, "__file__", str(tmp_path / "ring_handler.py"))
    (tmp_path / ".env").write_text('RING_TOKEN=\'{"access_token":"unintended"}\'\n')
    assert ring_handler.RingHandler()._load_token() is None


def test_setup_helpers_preserve_settings_in_selected_app_file(monkeypatch, tmp_path):
    config = tmp_path / "app.env"
    config.write_text("OPENAI_API_KEY=keep-me\nBRAIN_PORT=8765\n")
    monkeypatch.setenv("BLOOGLYBLOB_ENV_FILE", str(config))
    monkeypatch.setitem(
        sys.modules,
        "ring_doorbell",
        SimpleNamespace(
            Auth=object,
            AuthenticationError=Exception,
            Requires2FAError=Exception,
        ),
    )
    ring = load_script("setup_ring")
    ring.save_token_to_env({"access_token": "literal-${VALUE}-quote'"})
    roku = load_script("setup_roku")
    roku.update_env_file(str(config), "192.0.2.20")
    values = dotenv_values(config, interpolate=False)
    assert values["OPENAI_API_KEY"] == "keep-me"
    assert values["BRAIN_PORT"] == "8765"
    assert values["ROKU_IP"] == "192.0.2.20"
    assert json.loads(values["RING_TOKEN"])["access_token"] == "literal-${VALUE}-quote'"
    assert config.stat().st_mode & 0o777 == 0o600


def test_setup_helpers_make_private_and_preserve_owner(monkeypatch, tmp_path):
    config = tmp_path / "app.env"
    config.write_text("OPENAI_API_KEY=keep\n")
    config.chmod(0o640)
    original = config.stat()
    monkeypatch.setenv("BLOOGLYBLOB_ENV_FILE", str(config))
    monkeypatch.setitem(
        sys.modules,
        "ring_doorbell",
        SimpleNamespace(
            Auth=object, AuthenticationError=Exception, Requires2FAError=Exception
        ),
    )
    load_script("setup_ring").save_token_to_env({"access_token": "test"})
    load_script("setup_roku").update_env_file(str(config), "192.0.2.1")
    assert config.stat().st_mode & 0o777 == 0o600
    assert (config.stat().st_uid, config.stat().st_gid) == (
        original.st_uid,
        original.st_gid,
    )


def test_helper_replacement_is_private_before_publication(monkeypatch, tmp_path):
    import os
    from scripts.deploy_config import update_env, read_env

    path = tmp_path / "app.env"
    path.write_text("OPENAI_API_KEY=keep\nUNKNOWN=future\n")
    path.chmod(0o644)
    original = path.stat()
    real_replace = os.replace

    def checked_replace(source, destination):
        candidate = source.stat()
        assert candidate.st_mode & 0o777 == 0o600
        assert (candidate.st_uid, candidate.st_gid) == (
            original.st_uid,
            original.st_gid,
        )
        real_replace(source, destination)

    monkeypatch.setattr(os, "replace", checked_replace)
    update_env(path, {"RING_TOKEN": '{"value":"literal $VALUE\\n"}'})
    assert read_env(path)["UNKNOWN"] == "future"


def test_interrupted_helper_preserves_original(monkeypatch, tmp_path):
    import os
    import pytest
    from scripts.deploy_config import update_env

    path = tmp_path / "app.env"
    path.write_text("OPENAI_API_KEY=keep\n")
    before = path.read_bytes()

    def interrupted(*args):
        raise OSError("interrupted")

    monkeypatch.setattr(os, "replace", interrupted)
    with pytest.raises(OSError):
        update_env(path, {"ROKU_IP": "192.0.2.20"})
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]
