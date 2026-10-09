"""One explicit runtime source, loaded before settings-consuming modules."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_python(code, tmp_path, **settings):
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env={"PATH": os.defpath, "PYTHONPATH": str(ROOT), **settings},
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_application_ignores_implicit_dotenv(tmp_path):
    (tmp_path / ".env").write_text("OPENAI_API_KEY=unintended\nMIC_GAIN=9000\n")
    result = run_python(
        """import os
from blooglyblob.config import load_runtime_environment
load_runtime_environment()
assert 'OPENAI_API_KEY' not in os.environ
assert 'MIC_GAIN' not in os.environ
assert 'SERVO_CALIBRATION_FILE' not in os.environ
""",
        tmp_path,
    )
    assert result.returncode == 0, result.stderr


def test_explicit_file_preserves_literal_values_and_process_precedence(tmp_path):
    selected = tmp_path / "app.env"
    selected.write_text("OPENAI_API_KEY=${UNSET}$(do-not-run)\nMIC_GAIN=10\n")
    result = run_python(
        """import os
from blooglyblob.config import load_runtime_environment,load_ai_config
load_runtime_environment()
assert load_ai_config().openai_api_key == '${UNSET}$(do-not-run)'
assert os.environ['MIC_GAIN'] == '4'
""",
        tmp_path,
        BLOOGLYBLOB_ENV_FILE=str(selected),
        MIC_GAIN="4",
    )
    assert result.returncode == 0, result.stderr


def test_entry_loads_config_before_application_construction(tmp_path):
    selected = tmp_path / "app.env"
    selected.write_text(
        "OPENAI_API_KEY=test-key\nSERVO_CALIBRATION_FILE=/custom/calibration.json\n"
    )
    result = run_python(
        """import os,sys
from types import SimpleNamespace
from blooglyblob import __main__ as entry
assert 'blooglyblob.application' not in sys.modules

def construct(config):
    assert config.openai_api_key == 'test-key'
    assert os.environ['SERVO_CALIBRATION_FILE'] == '/custom/calibration.json'
    return object()
sys.modules['blooglyblob.application'] = SimpleNamespace(Application=construct,SHUTDOWN_SECONDS=15)
entry.run_application = lambda *a,**kw: None
entry.main()
""",
        tmp_path,
        BLOOGLYBLOB_ENV_FILE=str(selected),
    )
    assert result.returncode == 0, result.stderr


def test_missing_explicit_file_fails_clearly(tmp_path):
    result = run_python(
        "from blooglyblob.config import load_runtime_environment; load_runtime_environment()",
        tmp_path,
        BLOOGLYBLOB_ENV_FILE=str(tmp_path / "missing.env"),
    )
    assert result.returncode != 0
    assert "BLOOGLYBLOB_ENV_FILE must name an existing file" in result.stderr


@pytest.mark.parametrize("command", ["check-audio", "test-audio", "test-mic"])
def test_audio_diagnostic_uses_shared_selection_and_unchanged_pcm(
    monkeypatch, tmp_path, command
):
    from unittest.mock import Mock, call
    from types import SimpleNamespace
    import time
    from scripts import audio_check

    monkeypatch.setattr(os, "environ", dict(os.environ))
    selected = tmp_path / "app.env"
    selected.write_text(
        "AUDIO_INPUT_DEVICE=selected mic\nAUDIO_OUTPUT_DEVICE=selected speaker\n"
    )
    monkeypatch.setenv("BLOOGLYBLOB_ENV_FILE", str(selected))
    for key in ("AUDIO_INPUT_DEVICE", "AUDIO_OUTPUT_DEVICE"):
        monkeypatch.delenv(key, raising=False)
    pa = Mock()
    devices = [
        {"name": "USB decoy", "maxInputChannels": 1, "maxOutputChannels": 2},
        {"name": "USB selected speaker", "maxInputChannels": 0, "maxOutputChannels": 2},
        {"name": "USB selected mic", "maxInputChannels": 1, "maxOutputChannels": 0},
    ]
    pa.get_device_count.return_value = len(devices)
    pa.get_device_info_by_index.side_effect = devices.__getitem__
    pa.open.return_value.read.return_value = b"\x01\x02" * 1600
    monkeypatch.setitem(
        sys.modules, "pyaudio", SimpleNamespace(PyAudio=lambda: pa, paInt16=8)
    )
    monkeypatch.setattr(time, "sleep", pa.pause)
    audio_check.main(command)
    pa.terminate.assert_called_once()
    if command == "check-audio":
        pa.open.assert_not_called()
    else:
        for opened in pa.open.call_args_list:
            assert opened.kwargs["rate"] == 48000
            assert opened.kwargs["channels"] == 1
        assert pa.open.call_args.kwargs["output_device_index"] == 1
        samples = pa.open.return_value.write.call_args.args[0]
        if command == "test-mic":
            from array import array

            assert len(pa.open.call_args_list) == 3
            assert pa.open.call_args_list[0].kwargs["output_device_index"] == 1
            assert pa.open.call_args_list[1].kwargs["input_device_index"] == 2
            cue = pa.open.return_value.write.call_args_list[0].args[0]
            assert len(cue) == 9600 * 2  # 200 ms, mono 16-bit at 48 kHz
            assert 0 < max(abs(x) for x in array("h", cue)) <= 1500
            calls = pa.mock_calls
            cue_write = calls.index(call.open().write(cue))
            assert calls[cue_write + 1 : cue_write + 4] == [
                call.open().stop_stream(),
                call.open().close(),
                call.pause(0.3),
            ]
            assert calls[cue_write + 4].kwargs.get("input") is True
            assert pa.open.return_value.read.call_count == 150
            assert samples == b"\x01\x02" * 48000 * 5
        else:
            from array import array

            assert len(samples) == 48000 * 2
            assert max(array("h", samples)) == 1500


def test_audio_diagnostic_lists_candidates_even_when_selection_fails(
    monkeypatch, tmp_path, capsys
):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from scripts import audio_check

    monkeypatch.setattr(os, "environ", {"AUDIO_INPUT_DEVICE": "missing"})
    pa = Mock()
    pa.get_device_count.return_value = 2
    pa.get_device_info_by_index.side_effect = [
        {"name": "USB Candidate Mic", "maxInputChannels": 1, "maxOutputChannels": 0},
        {
            "name": "USB Candidate Speaker",
            "maxInputChannels": 0,
            "maxOutputChannels": 2,
        },
    ]
    monkeypatch.setitem(sys.modules, "pyaudio", SimpleNamespace(PyAudio=lambda: pa))
    with pytest.raises(RuntimeError, match="AUDIO_INPUT_DEVICE"):
        audio_check.main("check-audio")
    output = capsys.readouterr().out
    assert "[0] USB Candidate Mic (in=1, out=0)" in output
    assert "[1] USB Candidate Speaker (in=0, out=2)" in output
    pa.open.assert_not_called()
    pa.terminate.assert_called_once()


def test_microphone_does_not_record_when_start_cue_fails(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from scripts import audio_check

    monkeypatch.setattr(
        os,
        "environ",
        {"AUDIO_INPUT_DEVICE": "USB audio", "AUDIO_OUTPUT_DEVICE": "USB audio"},
    )
    pa = Mock()
    pa.get_device_count.return_value = 1
    pa.get_device_info_by_index.return_value = {
        "name": "USB audio",
        "maxInputChannels": 1,
        "maxOutputChannels": 2,
    }
    pa.open.return_value.write.side_effect = RuntimeError("cue playback failed")
    monkeypatch.setitem(
        sys.modules, "pyaudio", SimpleNamespace(PyAudio=lambda: pa, paInt16=8)
    )
    with pytest.raises(RuntimeError, match="cue playback failed"):
        audio_check.main("test-mic")
    pa.open.assert_called_once()
    assert pa.open.call_args.kwargs["output"] is True
    pa.open.return_value.read.assert_not_called()
    pa.open.return_value.close.assert_called_once()
    pa.terminate.assert_called_once()
