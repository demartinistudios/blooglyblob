"""Credential validation and absence of retired runtime dependencies."""

import os
import subprocess
import sys
from pathlib import Path
import pytest
from blooglyblob.config import AIConfigError, load_ai_config


def test_key_is_hidden_and_stale_provider_settings_have_no_effect():
    config = load_ai_config(
        {
            "OPENAI_API_KEY": "private-test-value",
            "TTS_PROVIDER": "invalid",
            "AI_MODE": "legacy",
        }
    )
    assert config.openai_api_key == "private-test-value"
    assert "private-test-value" not in repr(config)


@pytest.mark.parametrize("key", ["", "  "])
def test_missing_key_fails(key):
    with pytest.raises(AIConfigError, match="OPENAI_API_KEY"):
        load_ai_config({"OPENAI_API_KEY": key})


def test_runtime_import_needs_no_retired_dependencies():
    code = """
import sys
class BlockRetired:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'voicebox', 'torch', 'anthropic', 'mlx', 'hume', 'pvporcupine', 'local', 'server', 'client', 'pi'}:
            raise AssertionError('Forbidden import: ' + fullname)
sys.meta_path.insert(0, BlockRetired())
from blooglyblob import application, conversation, __main__
from blooglyblob.audio import controller
from blooglyblob.hardware import controller
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        env={"PATH": os.defpath},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_minimum_python_version(monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 9))
    with pytest.raises(AIConfigError, match="Python 3.12"):
        load_ai_config({}, require_credentials=False)
