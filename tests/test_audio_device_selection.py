"""Independent capture/playback selection without relying on ALSA card order."""

import sys
from types import SimpleNamespace

import pytest

from blooglyblob.audio.driver import select_input_device, select_output_device


def audio(monkeypatch, devices):
    monkeypatch.setitem(sys.modules, "pyaudio", SimpleNamespace())
    result = SimpleNamespace(
        p=SimpleNamespace(
            get_device_count=lambda: len(devices),
            get_device_info_by_index=lambda i: devices[i],
        )
    )
    return result


def test_explicit_independent_names_win_over_card_order(monkeypatch):
    monkeypatch.setenv("AUDIO_INPUT_DEVICE", "dedicated mic")
    monkeypatch.setenv("AUDIO_OUTPUT_DEVICE", "speaker dongle")
    devices = [
        {"name": "USB wrong", "maxInputChannels": 1, "maxOutputChannels": 2},
        {"name": "USB speaker dongle", "maxInputChannels": 1, "maxOutputChannels": 2},
        {"name": "USB dedicated mic", "maxInputChannels": 1, "maxOutputChannels": 0},
    ]
    selected = audio(monkeypatch, devices)
    assert (select_input_device(selected.p), select_output_device(selected.p)) == (2, 1)


def test_missing_configured_device_does_not_fall_back(monkeypatch):
    monkeypatch.setenv("AUDIO_INPUT_DEVICE", "missing")
    selected = audio(
        monkeypatch,
        [
            {
                "name": "USB PnP Sound Device",
                "maxInputChannels": 1,
                "maxOutputChannels": 2,
            },
        ],
    )
    with pytest.raises(RuntimeError, match="AUDIO_INPUT_DEVICE"):
        select_input_device(selected.p)


@pytest.mark.parametrize(
    "names", [[], ["USB selected speaker", "USB selected speaker duplicate"]]
)
def test_output_selection_rejects_missing_or_ambiguous_explicit_name(
    monkeypatch, names
):

    monkeypatch.setenv("AUDIO_OUTPUT_DEVICE", "selected speaker")
    selected = audio(
        monkeypatch,
        [
            {"name": name, "maxInputChannels": 0, "maxOutputChannels": 2}
            for name in ["USB wrong hw:2", *names]
        ],
    )
    with pytest.raises(RuntimeError, match="AUDIO_OUTPUT_DEVICE"):
        select_output_device(selected.p)


def test_unconfigured_output_preserves_first_usb_baseline(monkeypatch):

    monkeypatch.delenv("AUDIO_OUTPUT_DEVICE", raising=False)
    selected = audio(
        monkeypatch,
        [
            {"name": "built-in hw:2", "maxInputChannels": 0, "maxOutputChannels": 2},
            {"name": "USB speaker", "maxInputChannels": 0, "maxOutputChannels": 2},
            {
                "name": "USB second speaker",
                "maxInputChannels": 0,
                "maxOutputChannels": 2,
            },
        ],
    )
    assert select_output_device(selected.p) == 1
